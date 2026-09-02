import pandas as pd
import geopandas as gpd
from shapely import wkt, make_valid
import logging
from pathlib import Path
from config.config import config
import numpy as np

logger = logging.getLogger(__name__)


def safe_wkt_loads(wkt_str):
    """Безопасная загрузка WKT с обработкой ошибок."""
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
            try:
                geom = make_valid(geom)
            except:
                return None

        if geom.geom_type not in ['Polygon', 'MultiPolygon']:
            return None

        return geom

    except Exception as e:
        logger.debug(f"Ошибка парсинга WKT: {e}")
        return None


def load_source(filepath: str, geometry_col: str = 'geometry') -> gpd.GeoDataFrame:
    """Загружает CSV и конвертирует в GeoDataFrame."""
    filepath = Path(filepath)
    logger.info(f"Загрузка {filepath}")

    if not filepath.exists():
        raise FileNotFoundError(f"Файл не найден: {filepath}")

    try:
        df = pd.read_csv(filepath, low_memory=False, encoding='utf-8')
    except UnicodeDecodeError:
        logger.warning("UTF-8 не подошёл, пробуем cp1251")
        df = pd.read_csv(filepath, low_memory=False, encoding='cp1251')

    logger.info(f"CSV загружен: {len(df)} строк")

    possible_geom_cols = [geometry_col, 'wkt', 'WKT', 'geom', 'geometry_wkt']
    geom_col = None
    for col in possible_geom_cols:
        if col in df.columns:
            geom_col = col
            break

    if geom_col is None:
        raise ValueError(f"Не найдена колонка с геометрией. Доступные: {list(df.columns)}")

    logger.info(f"Колонка геометрии: '{geom_col}'")

    df['geometry'] = df[geom_col].apply(safe_wkt_loads)

    valid_mask = df['geometry'].notna()
    n_valid = valid_mask.sum()

    logger.info(f"Валидных геометрий: {n_valid} ({n_valid / len(df) * 100:.1f}%)")

    if n_valid == 0:
        raise ValueError("Все геометрии невалидны.")

    df_clean = df[valid_mask].copy()

    gdf = gpd.GeoDataFrame(
        df_clean.drop(columns=[geom_col], errors='ignore'),
        geometry=list(df_clean['geometry']),
        crs=config.CRS_INPUT
    )

    logger.info(f"GeoDataFrame: {len(gdf)} объектов, CRS: {gdf.crs}")

    return gdf


def add_basic_features(gdf: gpd.GeoDataFrame, source: str) -> gpd.GeoDataFrame:
    """Добавляет базовые признаки."""
    gdf = gdf.copy()

    gdf_proj = gdf.to_crs(config.CRS_METRIC)

    gdf['centroid_x'] = gdf_proj.geometry.centroid.x
    gdf['centroid_y'] = gdf_proj.geometry.centroid.y
    gdf['centroid'] = gdf.geometry.centroid
    gdf['area_calculated_sqm'] = gdf_proj.geometry.area
    gdf['log_area'] = (gdf['area_calculated_sqm'].fillna(0) + 1).apply(np.log1p)
    gdf['data_source'] = source

    logger.info(f"Добавлены признаки для источника {source}")
    return gdf