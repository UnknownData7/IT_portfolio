import pandas as pd
import geopandas as gpd
import numpy as np
from scipy.spatial import cKDTree
from sklearn.preprocessing import LabelEncoder
import logging
from config.config import config

logger = logging.getLogger(__name__)


class FeatureEngineer:
    """
    Комплексный Feature Engineering для геоданных.
    """

    def __init__(self):
        self.label_encoders = {}
        self.stats = {}
        self.neighbors_tree = None
        self.neighbors_data = None

    def extract_all_features(self, gdf: gpd.GeoDataFrame,
                             is_train: bool = False,
                             gdf_all: gpd.GeoDataFrame = None) -> gpd.GeoDataFrame:
        """
        Извлекает все признаки для модели.
        """
        logger.info("Feature Engineering: генерация признаков")
        gdf = gdf.copy()

        #Геометрические признаки
        gdf = self._add_geometry_features(gdf)

        # Пространственные признаки
        gdf = self._add_spatial_features(gdf)

        #Признаки окружения
        if gdf_all is not None and len(gdf_all) > 0:
            gdf = self._add_neighborhood_features(gdf, gdf_all)
        else:
            logger.warning("gdf_all не предоставлен, пропускаем признаки окружения")

        #Категориальные признаки
        gdf = self._add_categorical_features(gdf, is_train)

        # Статистические признаки
        gdf = self._add_statistical_features(gdf)

        #Адресные признаки
        gdf = self._add_address_features(gdf)

        # Сохраняем статистику
        feature_cols = [c for c in gdf.columns if c.startswith('feat_')]
        self.stats['total_features'] = len(feature_cols)
        self.stats['feature_columns'] = feature_cols

        logger.info(f"Сгенерировано признаков: {len(feature_cols)}")

        return gdf

    def _add_geometry_features(self, gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        """
        Геометрические признаки.
        Основано на форме и размере здания.
        """
        logger.info("Геометрические признаки")
        gdf_proj = gdf.to_crs(config.CLEANING.CRS_METRIC)

        # 1. Площадь (логарифм) — лучше для ML
        gdf['feat_log_area'] = np.log1p(gdf_proj.geometry.area)

        # 2. Периметр
        gdf['feat_perimeter'] = gdf_proj.geometry.length

        # 3. Компактность (отношение площади к периметру)
        gdf['feat_compactness'] = (4 * np.pi * gdf_proj.geometry.area) / (gdf_proj.geometry.length ** 2 + 1e-6)

        # 4. Вытянутость (соотношение сторон bounding box)
        bounds = gdf_proj.bounds
        gdf['feat_elongation'] = (
                (bounds['maxx'] - bounds['minx']) / (bounds['maxy'] - bounds['miny'] + 1e-6)
        ).apply(lambda x: max(x, 1 / x))  # Всегда >= 1

        # 5. Количество вершин
        def count_vertices(geom):
            if hasattr(geom, 'exterior'):
                return len(geom.exterior.coords)
            return 0

        gdf['feat_vertices_count'] = gdf.geometry.apply(count_vertices)

        # 6. Площадь convex hull (выпуклой оболочки)
        gdf['feat_convex_hull_area'] = gdf_proj.geometry.apply(
            lambda g: g.convex_hull.area if g else 0
        )

        # 7. Отношение площади к convex hull (заполненность)
        gdf['feat_convex_hull_ratio'] = (
                gdf_proj.geometry.area / (gdf['feat_convex_hull_area'] + 1e-6)
        )

        return gdf

    def _add_spatial_features(self, gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        """
        Пространственные признаки.
        Позиция здания в городе.
        """
        logger.info("Пространственные признаки")
        gdf_proj = gdf.to_crs(config.CLEANING.CRS_METRIC)

        # Центр города (для СПб: Дворцовая площадь)
        city_center = gpd.GeoSeries(
            [gpd.points_from_xy([30.3158], [59.9391])[0]],
            crs=config.CLEANING.CRS_INPUT
        ).to_crs(config.CLEANING.CRS_METRIC)[0]

        # 1. Расстояние до центра (км)
        gdf['feat_distance_to_center_km'] = gdf_proj.geometry.centroid.apply(
            lambda c: c.distance(city_center) / 1000
        )

        # 2. X-координата (нормализованная)
        gdf['feat_x_coord'] = gdf_proj.centroid.x

        # 3. Y-координата (нормализованная)
        gdf['feat_y_coord'] = gdf_proj.centroid.y

        # 4. H3-индекс (для пространственной кластеризации)
        try:
            import h3
            gdf['feat_h3_index'] = gdf.geometry.centroid.apply(
                lambda c: h3.latlng_to_cell(c.y, c.x, res=9)
            )
        except ImportError:
            logger.warning(" H3 не установлен, пропускаем")
            gdf['feat_h3_index'] = 0

        return gdf

    def _add_neighborhood_features(self, gdf: gpd.GeoDataFrame,
                                   gdf_all: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        """
        Признаки окружения.
        """
        logger.info("Признаки окружения")
        gdf_proj = gdf.to_crs(config.CLEANING.CRS_METRIC)
        gdf_all_proj = gdf_all.to_crs(config.CLEANING.CRS_METRIC)

        # Строим KD-Tree для быстрого поиска соседей
        coords_all = np.array([(g.centroid.x, g.centroid.y) for g in gdf_all_proj.geometry])
        tree = cKDTree(coords_all)
        coords_target = np.array([(g.centroid.x, g.centroid.y) for g in gdf_proj.geometry])

        # Проверяем наличие колонки с высотой
        has_height = 'final_height_m' in gdf_all.columns or 'height' in gdf_all.columns
        height_col = 'final_height_m' if 'final_height_m' in gdf_all.columns else 'height'

        # Проверяем наличие площади
        has_area = 'area_sq_m' in gdf_all.columns or 'area_calculated_sqm' in gdf_all.columns
        area_col = 'area_sq_m' if 'area_sq_m' in gdf_all.columns else 'area_calculated_sqm'

        for radius in config.FEATURES.NEIGHBOR_RADII_METERS:
            counts, avg_heights, avg_areas, density_scores = [], [], [], []

            for i, (x, y) in enumerate(coords_target):
                # Находим всех соседей в радиусе
                indices = tree.query_ball_point([x, y], r=radius)
                neighbors = gdf_all_proj.iloc[indices]

                # 1. Количество соседей (минус само здание)
                counts.append(max(len(indices) - 1, 0))

                # 2. Средняя высота соседей
                if has_height and height_col in neighbors.columns:
                    known_heights = neighbors[neighbors[height_col].notna()][height_col]
                    avg_heights.append(float(known_heights.mean()) if len(known_heights) > 0 else np.nan)
                else:
                    avg_heights.append(np.nan)

                # 3. Средняя площадь соседей
                if has_area and area_col in neighbors.columns:
                    avg_areas.append(float(neighbors[area_col].mean()))
                else:
                    avg_areas.append(np.nan)

                # 4. Плотность застройки (зданий на гектар)
                area_ha = np.pi * (radius ** 2) / 10000
                density_scores.append(counts[-1] / area_ha if area_ha > 0 else 0)

            suffix = f"_{radius}m"
            gdf[f'feat_neighbor_count{suffix}'] = counts
            gdf[f'feat_avg_neighbor_height{suffix}'] = avg_heights
            gdf[f'feat_avg_neighbor_area{suffix}'] = avg_areas
            gdf[f'feat_density{suffix}'] = density_scores

        return gdf

    def _add_categorical_features(self, gdf: gpd.GeoDataFrame,
                                  is_train: bool) -> gpd.GeoDataFrame:
        """
        Категориальные признаки.
        Тип здания, назначение и т.д.
        """
        logger.info("Категориальные признаки")

        # 1-2. Тип здания (из tags или purpose_of_building)
        if 'tags' in gdf.columns:
            gdf['feat_building_type'] = gdf['tags'].apply(
                lambda x: self._extract_building_type(str(x).lower())
            )
        elif 'purpose_of_building' in gdf.columns:
            gdf['feat_building_type'] = gdf['purpose_of_building'].apply(
                lambda x: self._extract_building_type(str(x).lower())
            )
        else:
            gdf['feat_building_type'] = 'unknown'

        # Кодирование типа здания
        if is_train:
            le = LabelEncoder()
            gdf['feat_building_type_enc'] = le.fit_transform(gdf['feat_building_type'])
            self.label_encoders['building_type'] = le
        else:
            le = self.label_encoders.get('building_type')
            if le:
                gdf['feat_building_type_enc'] = gdf['feat_building_type'].apply(
                    lambda x: le.transform([x])[0] if x in le.classes_ else -1
                )
            else:
                gdf['feat_building_type_enc'] = 0

        # 3-4. Жилое/нежилое
        gdf['feat_is_residential'] = gdf.apply(
            lambda row: self._is_residential(row), axis=1
        ).astype(int)

        # 5-6. Район/округ (если есть)
        if 'district' in gdf.columns:
            gdf['feat_district'] = gdf['district'].fillna('unknown')
            if is_train:
                le = LabelEncoder()
                gdf['feat_district_enc'] = le.fit_transform(gdf['feat_district'])
                self.label_encoders['district'] = le
            else:
                le = self.label_encoders.get('district')
                if le:
                    gdf['feat_district_enc'] = gdf['feat_district'].apply(
                        lambda x: le.transform([x])[0] if x in le.classes_ else -1
                    )
                else:
                    gdf['feat_district_enc'] = 0
        else:
            gdf['feat_district_enc'] = 0

        return gdf

    def _add_statistical_features(self, gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        """
        Статистические признаки.
        Z-score, квантили относительно всех зданий.
        """
        logger.info("Статистические признаки")

        # 1-2. Z-score и квантиль площади
        if 'area_sq_m' in gdf.columns or 'area_calculated_sqm' in gdf.columns:
            area_col = 'area_sq_m' if 'area_sq_m' in gdf.columns else 'area_calculated_sqm'
            areas = gdf[area_col].dropna()

            if len(areas) > 10:
                mean_area = areas.mean()
                std_area = areas.std()
                if std_area > 0:
                    gdf['feat_area_zscore'] = (gdf[area_col] - mean_area) / std_area
                else:
                    gdf['feat_area_zscore'] = 0
                gdf['feat_area_quantile'] = gdf[area_col].rank(pct=True)
            else:
                gdf['feat_area_zscore'] = 0
                gdf['feat_area_quantile'] = 0.5
        else:
            gdf['feat_area_zscore'] = 0
            gdf['feat_area_quantile'] = 0.5

        # 3-4. Z-score и квантиль высоты (если есть)
        if 'final_height_m' in gdf.columns or 'height' in gdf.columns:
            height_col = 'final_height_m' if 'final_height_m' in gdf.columns else 'height'
            heights = gdf[height_col].dropna()

            if len(heights) > 10:
                mean_height = heights.mean()
                std_height = heights.std()
                if std_height > 0:
                    gdf['feat_height_zscore'] = (gdf[height_col] - mean_height) / std_height
                else:
                    gdf['feat_height_zscore'] = 0
                gdf['feat_height_quantile'] = gdf[height_col].rank(pct=True)
            else:
                gdf['feat_height_zscore'] = 0
                gdf['feat_height_quantile'] = 0.5
        else:
            gdf['feat_height_zscore'] = 0
            gdf['feat_height_quantile'] = 0.5

        return gdf

    def _add_address_features(self, gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        """
        Адресные признаки.
        Наличие и полнота адреса.
        """
        logger.info("Адресные признаки")

        # 1. Наличие адреса
        if 'gkh_address' in gdf.columns:
            gdf['feat_has_address'] = gdf['gkh_address'].notna().astype(int)
        else:
            gdf['feat_has_address'] = 0

        # 2. Наличие номера дома
        if 'number' in gdf.columns:
            gdf['feat_has_number'] = gdf['number'].notna().astype(int)
        else:
            gdf['feat_has_number'] = 0

        # 3. Полнота адреса (комбинированный признак)
        gdf['feat_address_completeness'] = (gdf['feat_has_address'] + gdf['feat_has_number']) / 2

        return gdf

    def _extract_building_type(self, text: str) -> str:
        """Извлекает тип здания из текста."""
        text = text.lower()

        for building_type, keywords in config.FEATURES.BUILDING_TYPES.items():
            if any(kw in text for kw in keywords):
                return building_type

        return 'other'

    def _is_residential(self, row: pd.Series) -> bool:
        """Определяет, является ли здание жилым."""
        tags = str(row.get('tags', '')).lower()
        purpose = str(row.get('purpose_of_building', '')).lower()

        residential_keywords = config.FEATURES.BUILDING_TYPES['residential']
        return any(kw in tags or kw in purpose for kw in residential_keywords)

    def get_feature_columns(self) -> list:
        """Возвращает список всех сгенерированных признаков."""
        return [c for c in self.stats.get('feature_columns', [])]

    def export_feature_stats(self, gdf: gpd.GeoDataFrame, path: str = None):
        """Экспорт статистики по признакам."""
        from pathlib import Path
        path = path or Path('results/feature_stats.csv')

        feature_cols = self.get_feature_columns()
        stats = []

        for col in feature_cols:
            if col in gdf.columns:
                stats.append({
                    'feature': col,
                    'mean': gdf[col].mean(),
                    'std': gdf[col].std(),
                    'min': gdf[col].min(),
                    'max': gdf[col].max(),
                    'null_count': gdf[col].isna().sum(),
                    'null_rate': gdf[col].isna().mean()
                })

        pd.DataFrame(stats).to_csv(path, index=False, encoding='utf-8-sig')
        logger.info(f"Статистика признаков: {path}")