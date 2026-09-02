import pandas as pd
import geopandas as gpd
import numpy as np
from scipy.spatial import cKDTree
import logging
from config.config import config
from src.feature_engineering import FeatureEngineer

logger = logging.getLogger(__name__)


class DataMerger:
    """Объединение двух источников в единый датасет с признаками."""

    def __init__(self):
        self.matches_df = None
        self.merged_gdf = None
        self.feature_engineer = FeatureEngineer()
        self.stats = {}

    def merge(self, gdf_a: gpd.GeoDataFrame, gdf_b: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        """Полное объединение источников + признаки."""
        logger.info("Объединение источников А и Б")
        logger.info(f"Источник А: {len(gdf_a)} объектов")
        logger.info(f"Источник Б: {len(gdf_b)} объектов")

        #Пространственное сопоставление
        self.matches_df = self._spatial_match(gdf_a, gdf_b)

        # Разрешение many-to-one
        resolved_matches = self._resolve_many_to_one(self.matches_df)

        # Слияние атрибутов
        self.merged_gdf = self._merge_attributes(gdf_a, gdf_b, resolved_matches)

        # Логика MAX для высоты
        self.merged_gdf = self._apply_max_height_logic(self.merged_gdf)

        #Feature Engineering
        self.merged_gdf = self.feature_engineer.extract_all_features(
            self.merged_gdf,
            is_train=True,
            gdf_all=self.merged_gdf
        )

        # Статистика
        self._log_stats()

        return self.merged_gdf


    def _spatial_match(self, gdf_a: gpd.GeoDataFrame, gdf_b: gpd.GeoDataFrame) -> pd.DataFrame:
        """Пространственное сопоставление через IoU + центроиды."""
        logger.info("Шаг 1: Пространственное сопоставление")

        gdf_a_proj = gdf_a.to_crs(config.CLEANING.CRS_METRIC).copy()
        gdf_b_proj = gdf_b.to_crs(config.CLEANING.CRS_METRIC).copy()

        matches = []

        #sjoin по пересечению
        try:
            candidates = gpd.sjoin(gdf_a_proj, gdf_b_proj, predicate='intersects',
                                   how='inner', lsuffix='_a', rsuffix='_b')

            for _, row in candidates.iterrows():
                iou = self._calculate_iou(row['geometry_a'], row['geometry_b'])
                dist = row['geometry_a'].centroid.distance(row['geometry_b'].centroid)

                if iou >= config.CLEANING.MIN_IOU_THRESHOLD:
                    matches.append({
                        'id_a': row.get('id_a', row.get('id')),
                        'id_b': row.get('id_b', row.get('id_right')),
                        'iou': iou,
                        'distance_m': dist,
                        'match_type': 'intersection'
                    })
        except Exception as e:
            logger.warning(f"sjoin failed: {e}")

        #центроидный поиск для оставшихся
        matched_ids_a = set(m['id_a'] for m in matches)
        unmatched_a = gdf_a_proj[~gdf_a_proj['id'].isin(matched_ids_a)].copy()

        if len(unmatched_a) > 0:
            centroid_matches = self._centroid_match(unmatched_a, gdf_b_proj)
            matches.extend(centroid_matches)

        matches_df = pd.DataFrame(matches) if matches else pd.DataFrame(columns=[
            'id_a', 'id_b', 'iou', 'distance_m', 'match_type'
        ])

        logger.info(f"Найдено совпадений: {len(matches_df)}")

        return matches_df

    def _calculate_iou(self, geom_a, geom_b) -> float:
        """IoU (Intersection over Union)."""
        try:
            intersection = geom_a.intersection(geom_b).area
            union = geom_a.union(geom_b).area
            return intersection / union if union > 1e-6 else 0.0
        except:
            return 0.0

    def _centroid_match(self, gdf_a: gpd.GeoDataFrame, gdf_b: gpd.GeoDataFrame,
                        max_distance: float = None) -> list:
        """Сопоставление по центроидам через cKDTree."""
        max_distance = max_distance or config.CLEANING.MAX_DISTANCE_METERS

        coords_a = np.array([(g.centroid.x, g.centroid.y) for g in gdf_a.geometry])
        coords_b = np.array([(g.centroid.x, g.centroid.y) for g in gdf_b.geometry])

        tree_b = cKDTree(coords_b)
        distances, indices = tree_b.query(coords_a, k=1)

        matches = []
        for i, (dist, j) in enumerate(zip(distances, indices)):
            if dist <= max_distance and j < len(gdf_b):
                geom_a = gdf_a.iloc[i]['geometry']
                geom_b = gdf_b.iloc[j]['geometry']

                matches.append({
                    'id_a': gdf_a.iloc[i].get('id', i),
                    'id_b': gdf_b.iloc[j].get('id', j),
                    'iou': self._calculate_iou(geom_a, geom_b),
                    'distance_m': dist,
                    'match_type': 'centroid'
                })

        return matches

    def _resolve_many_to_one(self, matches_df: pd.DataFrame) -> pd.DataFrame:
        """Разрешение many-to-one: для каждого id_a оставляем лучший матч по IoU."""
        logger.info("Шаг 2: Разрешение many-to-one(many)")

        if len(matches_df) == 0:
            return matches_df

        resolved = matches_df.loc[matches_df.groupby('id_a')['iou'].idxmax()].reset_index(drop=True)

        logger.info(f"Уникальных id_a: {resolved['id_a'].nunique()}")
        logger.info(f"Уникальных id_b: {resolved['id_b'].nunique()}")

        return resolved

    def _merge_attributes(self, gdf_a: gpd.GeoDataFrame, gdf_b: gpd.GeoDataFrame,
                          matches: pd.DataFrame) -> gpd.GeoDataFrame:
        """Слияние атрибутов из обоих источников."""
        logger.info(" Шаг 3: Слияние атрибутов")

        merged = gdf_a.copy()
        merged['data_source'] = 'A'

        match_map = matches.set_index('id_a')[['id_b', 'iou', 'match_type']].to_dict('index')

        merged['matched_id_b'] = merged['id'].apply(lambda x: match_map.get(x, {}).get('id_b', None))
        merged['match_iou'] = merged['id'].apply(lambda x: match_map.get(x, {}).get('iou', None))
        merged['match_type'] = merged['id'].apply(lambda x: match_map.get(x, {}).get('match_type', None))

        gdf_b_indexed = gdf_b.set_index('id')

        for col in gdf_b.columns:
            if col not in merged.columns and col != 'geometry':
                merged[f'B_{col}'] = merged['matched_id_b'].apply(
                    lambda x: gdf_b_indexed.loc[x, col] if x is not None and x in gdf_b_indexed.index else None
                )

        merged['height_source'] = merged.apply(
            lambda row: 'B' if pd.notna(row.get('B_height')) else 'A_inferred',
            axis=1
        )

        logger.info(f"Слитых атрибутов из Б: {sum(1 for c in merged.columns if c.startswith('B_'))}")

        return merged

    def _apply_max_height_logic(self, gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        """Логика MAX для высоты."""
        logger.info("Шаг 4: Логика MAX для высоты")

        def calculate_max_height(row):
            heights = []

            if pd.notna(row.get('B_height')) and row['B_height'] > 0:
                heights.append(row['B_height'])

            if pd.notna(row.get('B_stairs')) and row['B_stairs'] > 0:
                floor_h = row.get('B_avg_floor_height', 3.0)
                if pd.notna(floor_h) and floor_h > 0:
                    heights.append(row['B_stairs'] * floor_h)
                else:
                    heights.append(row['B_stairs'] * 3.0)

            if pd.notna(row.get('gkh_floor_count_max')) and row['gkh_floor_count_max'] > 0:
                heights.append(row['gkh_floor_count_max'] * 3.0)

            return max(heights) if heights else None

        gdf['final_height_m'] = gdf.apply(calculate_max_height, axis=1)

        with_height = gdf['final_height_m'].notna().sum()
        logger.info(f"Зданий с высотой: {with_height} ({with_height / len(gdf) * 100:.1f}%)")

        def used_max(row):
            count = 0
            if pd.notna(row.get('B_height')): count += 1
            if pd.notna(row.get('B_stairs')): count += 1
            if pd.notna(row.get('gkh_floor_count_max')): count += 1
            return count > 1

        max_used = gdf.apply(used_max, axis=1).sum()
        logger.info(f"MAX() использовано: {max_used} ({max_used / len(gdf) * 100:.1f}%)")

        return gdf

    def _log_stats(self):
        """Статистика объединения."""
        logger.info(f"\nСтатистика объединения:")
        logger.info(f"Совпадений найдено: {len(self.matches_df):,}")
        logger.info(f"Уникальных id_a: {self.matches_df['id_a'].nunique() if len(self.matches_df) > 0 else 0:,}")
        logger.info(f"Уникальных id_b: {self.matches_df['id_b'].nunique() if len(self.matches_df) > 0 else 0:,}")
        logger.info(f"Итого в объединённом датасете: {len(self.merged_gdf):,}")
        logger.info(f"Признаков сгенерировано: {self.feature_engineer.stats.get('total_features', 0)}")

    def export_merged(self, path_csv: str, path_geojson: str):
        """Экспорт объединённого датасета."""
        self.merged_gdf.to_file(path_geojson, driver='GeoJSON', encoding='utf-8')

        df_export = self.merged_gdf.copy()
        df_export['geometry_wkt'] = df_export.geometry.to_wkt()
        df_export = df_export.drop(columns=['geometry'])
        df_export.to_csv(path_csv, index=False, encoding='utf-8-sig')

        logger.info(f"Экспорт: {path_csv}, {path_geojson}")

        # Экспорт статистики признаков
        self.feature_engineer.export_feature_stats(self.merged_gdf)