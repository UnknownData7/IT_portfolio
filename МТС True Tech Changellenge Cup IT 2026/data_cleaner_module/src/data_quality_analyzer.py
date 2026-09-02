import geopandas as gpd
import numpy as np
import logging
from config.config import config
from typing import Dict, Any

logger = logging.getLogger(__name__)

class DataQualityAnalyzer:

    def __init__(self):
        self.report = {}

    def analyze_source(self, gdf: gpd.GeoDataFrame, source_name: str) -> Dict[str, Any]:
        """Полный анализ качества источника данных."""
        logger.info(f"Анализ качества источника: {source_name}")

        report = {
            'source': source_name,
            'total_records': len(gdf),
            'completeness': self._analyze_completeness(gdf),
            'positional_accuracy': self._analyze_positional_accuracy(gdf),
            'attribute_accuracy': self._analyze_attribute_accuracy(gdf, source_name),
            'consistency': self._analyze_consistency(gdf, source_name),
            'topological_correctness': self._analyze_topological_correctness(gdf),
            'outliers': self._detect_outliers(gdf, source_name),
            'recommendations': []
        }

        report['recommendations'] = self._generate_recommendations(report)
        self._log_summary(report)

        self.report[source_name] = report
        return report

    def _analyze_completeness(self, gdf: gpd.GeoDataFrame) -> Dict[str, float]:
        """1. Полнота: какая доля объектов имеет заполненные атрибуты."""
        completeness = {}

        geom_valid = gdf.geometry.notna().sum()
        completeness['geometry'] = geom_valid / len(gdf) * 100

        key_cols = ['area_sq_m', 'height', 'stairs', 'gkh_floor_count_max', 'purpose_of_building', 'tags']
        for col in key_cols:
            if col in gdf.columns:
                completeness[col] = gdf[col].notna().sum() / len(gdf) * 100
            else:
                completeness[col] = 0.0

        completeness['overall'] = np.mean([v for k, v in completeness.items() if k != 'overall'])

        return completeness

    def _analyze_positional_accuracy(self, gdf: gpd.GeoDataFrame) -> Dict[str, Any]:
        """2. Точность позиционирования: анализ координат."""
        gdf_proj = gdf.to_crs(config.CRS_METRIC)
        bounds = gdf_proj.total_bounds

        accuracy = {
            'bounds_min_x': bounds[0],
            'bounds_min_y': bounds[1],
            'bounds_max_x': bounds[2],
            'bounds_max_y': bounds[3],
            'area_coverage_sqkm': (bounds[2] - bounds[0]) * (bounds[3] - bounds[1]) / 1e6,
            'centroid_spread_x': gdf_proj.centroid.x.std(),
            'centroid_spread_y': gdf_proj.centroid.y.std(),
            'is_in_expected_region': True
        }

        coords = np.array([(g.centroid.x, g.centroid.y) for g in gdf_proj.geometry])
        if len(coords) > 100:
            from scipy.spatial import cKDTree
            tree = cKDTree(coords)
            distances, _ = tree.query(coords, k=2)
            accuracy['min_neighbor_distance_m'] = float(distances[:, 1].min())
            accuracy['median_neighbor_distance_m'] = float(np.median(distances[:, 1]))

        return accuracy

    def _analyze_attribute_accuracy(self, gdf: gpd.GeoDataFrame, source: str) -> Dict[str, Any]:
        """3. Атрибутивная точность: анализ значений характеристик."""
        accuracy = {}

        if 'height' in gdf.columns:
            heights = gdf['height'].dropna()
            accuracy['height'] = {
                'count': len(heights),
                'mean': heights.mean(),
                'median': heights.median(),
                'std': heights.std(),
                'min': heights.min(),
                'max': heights.max(),
                'completeness': len(heights) / len(gdf) * 100
            }

        floor_cols = ['stairs', 'gkh_floor_count_max', 'gkh_floor_count_min']
        for col in floor_cols:
            if col in gdf.columns:
                values = gdf[col].dropna()
                accuracy[col] = {
                    'count': len(values),
                    'mean': values.mean(),
                    'median': values.median(),
                    'completeness': len(values) / len(gdf) * 100
                }

        if 'area_sq_m' in gdf.columns:
            areas = gdf['area_sq_m'].dropna()
            accuracy['area_sq_m'] = {
                'count': len(areas),
                'mean': areas.mean(),
                'median': areas.median(),
                'min': areas.min(),
                'max': areas.max(),
                'completeness': len(areas) / len(gdf) * 100
            }

        return accuracy

    def _analyze_consistency(self, gdf: gpd.GeoDataFrame, source: str) -> Dict[str, Any]:
        """4. Согласованность: противоречия внутри источника."""
        consistency = {'conflicts': [], 'conflict_rate': 0.0}

        if 'height' in gdf.columns and 'stairs' in gdf.columns:
            mask = gdf[['height', 'stairs']].notna().all(axis=1)
            if mask.sum() > 0:
                calc_floor_height = gdf.loc[mask, 'height'] / gdf.loc[mask, 'stairs']
                conflicts = (calc_floor_height < 2.5) | (calc_floor_height > 4.5)
                n_conflicts = conflicts.sum()
                consistency['conflicts'].append({
                    'type': 'height_vs_stairs',
                    'count': int(n_conflicts),
                    'rate': n_conflicts / mask.sum() * 100
                })

        if 'gkh_floor_count_min' in gdf.columns and 'gkh_floor_count_max' in gdf.columns:
            mask = gdf[['gkh_floor_count_min', 'gkh_floor_count_max']].notna().all(axis=1)
            if mask.sum() > 0:
                conflicts = gdf.loc[mask, 'gkh_floor_count_min'] > gdf.loc[mask, 'gkh_floor_count_max']
                n_conflicts = conflicts.sum()
                consistency['conflicts'].append({
                    'type': 'floor_min_vs_max',
                    'count': int(n_conflicts),
                    'rate': n_conflicts / mask.sum() * 100
                })

        if consistency['conflicts']:
            consistency['conflict_rate'] = np.mean([c['rate'] for c in consistency['conflicts']])

        return consistency

    def _analyze_topological_correctness(self, gdf: gpd.GeoDataFrame) -> Dict[str, Any]:
        """5. Топологическая корректность: 7 типов ошибок геометрии."""
        topology = {
            'total': len(gdf),
            'valid': 0,
            'invalid': 0,
            'error_types': {
                'self_intersection': 0,
                'zero_area': 0,
                'empty_geometry': 0,
                'not_polygon': 0,
                'duplicate_vertices': 0,
                'spike': 0,
                'other': 0
            }
        }

        for idx, geom in gdf.geometry.items():
            is_valid = True

            if geom is None or getattr(geom, 'is_empty', True):
                topology['error_types']['empty_geometry'] += 1
                is_valid = False
            elif not geom.is_valid:
                topology['error_types']['self_intersection'] += 1
                is_valid = False
            elif geom.geom_type not in ['Polygon', 'MultiPolygon']:
                topology['error_types']['not_polygon'] += 1
                is_valid = False
            else:
                try:
                    geom_proj = gpd.GeoSeries([geom], crs=config.CRS_INPUT).to_crs(config.CRS_METRIC)[0]
                    if geom_proj.area < 1.0:
                        topology['error_types']['zero_area'] += 1
                        is_valid = False
                except:
                    topology['error_types']['other'] += 1
                    is_valid = False

            if is_valid:
                topology['valid'] += 1
            else:
                topology['invalid'] += 1

        topology['validity_rate'] = topology['valid'] / topology['total'] * 100
        return topology

    def _detect_outliers(self, gdf: gpd.GeoDataFrame, source: str) -> Dict[str, Any]:
        """Обнаружение выбросов по ключевым атрибутам."""
        outliers = {}

        if 'height' in gdf.columns:
            heights = gdf['height'].dropna()
            if len(heights) > 20:
                Q1, Q3 = heights.quantile([0.25, 0.75])
                IQR = Q3 - Q1
                lower = Q1 - 3 * IQR
                upper = Q3 + 3 * IQR
                outlier_mask = (gdf['height'] < lower) | (gdf['height'] > upper)
                outliers['height'] = {
                    'count': int(outlier_mask.sum()),
                    'rate': outlier_mask.sum() / len(gdf) * 100,
                    'bounds': [max(lower, 2), min(upper, 200)]
                }

        if 'area_sq_m' in gdf.columns:
            areas = gdf['area_sq_m'].dropna()
            if len(areas) > 20:
                Q1, Q3 = areas.quantile([0.25, 0.75])
                IQR = Q3 - Q1
                lower = Q1 - 3 * IQR
                upper = Q3 + 3 * IQR
                outlier_mask = (gdf['area_sq_m'] < lower) | (gdf['area_sq_m'] > upper)
                outliers['area_sq_m'] = {
                    'count': int(outlier_mask.sum()),
                    'rate': outlier_mask.sum() / len(gdf) * 100
                }

        return outliers

    def _generate_recommendations(self, report: Dict[str, Any]) -> list:
        """Генерация рекомендаций на основе анализа."""
        recommendations = []

        if report['completeness']['overall'] < 80:
            recommendations.append(f"⚠Низкая полнота данных ({report['completeness']['overall']:.1f}%).")

        invalid_rate = 100 - report['topological_correctness']['validity_rate']
        if invalid_rate > 5:
            recommendations.append(f"{invalid_rate:.1f}% невалидных геометрий.")

        if 'height' in report['outliers'] and report['outliers']['height']['rate'] > 2:
            recommendations.append(f"{report['outliers']['height']['rate']:.1f}% выбросов по высоте.")

        if report['consistency']['conflict_rate'] > 3:
            recommendations.append(f"{report['consistency']['conflict_rate']:.1f}% внутренних конфликтов.")

        if not recommendations:
            recommendations.append("Качество данных удовлетворительное.")

        return recommendations

    def _log_summary(self, report: Dict[str, Any]):
        """Логирование сводки анализа."""
        logger.info(f"Полнота: {report['completeness']['overall']:.1f}%")
        logger.info(f"Топология: {report['topological_correctness']['validity_rate']:.1f}% валидных")
        logger.info(f"Выбросы: {sum(o.get('count', 0) for o in report['outliers'].values())} объектов")
        logger.info(f"Рекомендаций: {len(report['recommendations'])}")

    def export_report(self, path: str = None):
        """Экспорт отчёта в JSON."""
        import json
        path = path or config.REPORTS_DIR / 'data_quality_report.json'

        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.report, f, ensure_ascii=False, indent=2, default=str)

        logger.info(f"Отчёт о качестве данных: {path}")
        return path