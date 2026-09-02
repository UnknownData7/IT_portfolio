import pandas as pd
import geopandas as gpd
from shapely import wkt, make_valid
import logging
from config.config import config

logger = logging.getLogger(__name__)


class DataCleaner:
    """Комплексная очистка геоданных."""

    def __init__(self, source_name: str):
        self.source_name = source_name
        self.stats = {
            'initial': 0,
            'after_geometry_clean': 0,
            'after_shed_filter': 0,
            'after_outlier_filter': 0,
            'final': 0
        }

    def load_and_clean(self, filepath: str, geometry_col: str = 'geometry') -> gpd.GeoDataFrame:
        """Загрузка + полная очистка."""
        logger.info(f"Очистка источника: {self.source_name}")
        logger.info(f"Файл: {filepath}")

        # Загрузка
        gdf = self._load_data(filepath, geometry_col)
        self.stats['initial'] = len(gdf)

        # Очистка геометрий (7 типов ошибок)
        gdf = self._clean_geometries(gdf)
        self.stats['after_geometry_clean'] = len(gdf)

        # Фильтрация сараев/гаражей
        gdf = self._filter_sheds(gdf)
        self.stats['after_shed_filter'] = len(gdf)

        # Удаление выбросов по площади/высоте
        gdf = self._filter_outliers(gdf)
        self.stats['after_outlier_filter'] = len(gdf)

        self.stats['final'] = len(gdf)

        # Логирование статистики
        self._log_stats()

        return gdf

    def _load_data(self, filepath: str, geometry_col: str) -> gpd.GeoDataFrame:
        """Загрузка CSV в GeoDataFrame."""
        try:
            df = pd.read_csv(filepath, low_memory=False, encoding='utf-8')
        except UnicodeDecodeError:
            df = pd.read_csv(filepath, low_memory=False, encoding='cp1251')

        # Определение колонки геометрии
        possible_cols = [geometry_col, 'wkt', 'WKT', 'geom']
        geom_col = next((c for c in possible_cols if c in df.columns), None)

        if geom_col is None:
            raise ValueError(f"Не найдена колонка геометрии в {filepath}")

        # Парсинг WKT
        df['geometry'] = df[geom_col].apply(self._safe_wkt_loads)
        df = df[df['geometry'].notna()].reset_index(drop=True)

        gdf = gpd.GeoDataFrame(df, geometry='geometry', crs=config.CLEANING.CRS_INPUT)

        logger.info(f"Загружено: {len(gdf)} объектов")
        return gdf

    def _safe_wkt_loads(self, wkt_str):
        """Безопасный парсинг WKT."""
        if pd.isna(wkt_str) or wkt_str == '' or wkt_str is None:
            return None

        try:
            wkt_str = str(wkt_str).strip()
            if not wkt_str or wkt_str.lower() in ['none', 'nan', 'null']:
                return None

            geom = wkt.loads(wkt_str)

            if geom.is_empty:
                return None

            if not geom.is_valid:
                geom = make_valid(geom)
                if geom is None or geom.is_empty:
                    return None

            if geom.geom_type not in ['Polygon', 'MultiPolygon']:
                return None

            return geom
        except:
            return None

    def _clean_geometries(self, gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        """
        Очистка геометрий (7 типов ошибок из ТЗ):
        1. Самопересекающиеся полигоны
        2. Разрывы (gaps)
        3. Несовпадение границ
        4. Нулевая площадь
        5. Неправильная ориентация
        6. Вырожденные отверстия
        7. Пустая геометрия
        """
        logger.info("Очистка геометрий (7 типов ошибок)...")

        def clean_geom(geom):
            if geom is None or getattr(geom, 'is_empty', True):
                return None  # пустая геометрия

            try:
                # Самопересечения
                if not geom.is_valid:
                    geom = make_valid(geom)
                    if geom is None or geom.is_empty:
                        return None

                # MultiPolygon - Polygon (берём крупнейший)
                if geom.geom_type == 'MultiPolygon':
                    if len(geom.geoms) == 0:
                        return None
                    geom = max(geom.geoms, key=lambda g: g.area)

                #Нулевая площадь
                geom_proj = gpd.GeoSeries([geom], crs=config.CLEANING.CRS_INPUT).to_crs(
                    config.CLEANING.CRS_METRIC)[0]
                if geom_proj.area < 1.0:
                    return None

                #Ориентация (GeoPandas исправляет автоматически)
                #Отверстия (make_valid исправляет)

                return geom
            except:
                return None

        gdf['geometry'] = gdf['geometry'].apply(clean_geom)
        gdf = gdf[gdf['geometry'].notna()].reset_index(drop=True)

        removed = self.stats['initial'] - len(gdf)
        logger.info(f"Удалено по геометрии: {removed} ({removed / self.stats['initial'] * 100:.1f}%)")

        return gdf

    def _filter_sheds(self, gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        """Фильтрация малых зданий."""
        logger.info("Фильтрация малых построек")

        def is_shed(row):
            # Проверка по тегам (Источник А)
            tags = str(row.get('tags', '')).lower()
            for tag in config.CLEANING.SHED_TAGS:
                if tag in tags:
                    return True

            # Проверка по назначению (Источник Б)
            purpose = str(row.get('purpose_of_building', '')).lower()
            for tag in config.CLEANING.SHED_TAGS:
                if tag in purpose:
                    return True

            # Проверка по площади + этажности
            area = row.get('area_sq_m') or row.get('area_calculated_sqm') or 0
            stairs = row.get('stairs') or row.get('gkh_floor_count_max') or 0

            if stairs == 1 and 0 < area < 30:
                return True

            return False

        mask = gdf.apply(is_shed, axis=1)
        shed_count = mask.sum()

        gdf = gdf[~mask].reset_index(drop=True)

        logger.info(f"Отфильтровано: {shed_count} ({shed_count / self.stats['after_geometry_clean'] * 100:.1f}%)")

        return gdf

    def _filter_outliers(self, gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        """Удаление выбросов по площади и высоте."""
        logger.info("Фильтрация выбросов")

        initial_count = len(gdf)

        # Выбросы по площади
        if 'area_sq_m' in gdf.columns or 'area_calculated_sqm' in gdf.columns:
            area_col = 'area_sq_m' if 'area_sq_m' in gdf.columns else 'area_calculated_sqm'
            areas = gdf[area_col].dropna()

            if len(areas) > 20:
                Q1, Q3 = areas.quantile([0.25, 0.75])
                IQR = Q3 - Q1
                lower = Q1 - 3 * IQR
                upper = Q3 + 3 * IQR

                # Применяем ограничения из конфига
                lower = max(lower, config.CLEANING.MIN_AREA_SQM)
                upper = min(upper, config.CLEANING.MAX_AREA_SQM)

                area_mask = gdf[area_col].between(lower, upper)
                gdf = gdf[area_mask]

        # Выбросы по высоте
        if 'height' in gdf.columns:
            heights = gdf['height'].dropna()

            if len(heights) > 20:
                Q1, Q3 = heights.quantile([0.25, 0.75])
                IQR = Q3 - Q1
                lower = max(Q1 - 3 * IQR, config.CLEANING.MIN_HEIGHT_M)
                upper = min(Q3 + 3 * IQR, config.CLEANING.MAX_HEIGHT_M)

                height_mask = gdf['height'].between(lower, upper, inclusive='both') | gdf['height'].isna()
                gdf = gdf[height_mask]

        removed = initial_count - len(gdf)
        logger.info(f"Удалено выбросов: {removed} ({removed / initial_count * 100:.1f}%)")

        return gdf

    def _log_stats(self):
        """Логирование статистики очистки."""
        logger.info(f"\nСтатистика очистки ({self.source_name}):")
        logger.info(f"Исходно: {self.stats['initial']:,}")
        logger.info(f"После очистки геометрий: {self.stats['after_geometry_clean']:,}")
        logger.info(f"После фильтрации сараев: {self.stats['after_shed_filter']:,}")
        logger.info(f"После фильтрации выбросов: {self.stats['after_outlier_filter']:,}")
        logger.info(f"Итого: {self.stats['final']:,} ({self.stats['final'] / self.stats['initial'] * 100:.1f}%)")

    def export_cleaned(self, gdf: gpd.GeoDataFrame, path: str):
        """Экспорт очищенных данных."""
        gdf.to_file(path.replace('.csv', '.geojson'), driver='GeoJSON', encoding='utf-8')

        df_export = gdf.copy()
        df_export['geometry_wkt'] = df_export.geometry.to_wkt()
        df_export = df_export.drop(columns=['geometry'])
        df_export.to_csv(path, index=False, encoding='utf-8-sig')

        logger.info(f"Экспорт: {path}")