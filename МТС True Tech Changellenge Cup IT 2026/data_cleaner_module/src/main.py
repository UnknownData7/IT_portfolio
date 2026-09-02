import logging
import sys
from pathlib import Path
import argparse

sys.path.append(str(Path(__file__).parent))

from config.config import config
from src.data_cleaner import DataCleaner
from src.data_merge import DataMerger


def setup_logging():
    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL),
        format=config.LOG_FORMAT,
        handlers=[
            logging.FileHandler(config.LOGS_DIR / 'pipeline.log', mode='w', encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger(__name__)


logger = setup_logging()


def main(args):
    """Основной пайплайн: очистка объединение признаки."""
    logger.info("MTS Hackathon: Единая модель высотности")

    logger.info("ШАГ 1/3: Очистка Источника А")

    cleaner_a = DataCleaner(source_name="Source_A")
    gdf_a_clean = cleaner_a.load_and_clean(str(config.SOURCE_A), geometry_col='geometry')
    cleaner_a.export_cleaned(gdf_a_clean, str(config.RESULTS_DIR / 'cleaned_source_A.csv'))


    logger.info("ШАГ 2/3: Очистка Источника Б")

    cleaner_b = DataCleaner(source_name="Source_B")
    gdf_b_clean = cleaner_b.load_and_clean(str(config.SOURCE_B), geometry_col='wkt')
    cleaner_b.export_cleaned(gdf_b_clean, str(config.RESULTS_DIR / 'cleaned_source_B.csv'))


    logger.info("ШАГ 3/3: Объединение источников + признаки")

    merger = DataMerger()
    gdf_merged = merger.merge(gdf_a_clean, gdf_b_clean)
    merger.export_merged(
        str(config.RESULTS_DIR / 'merged_dataset.csv'),
        str(config.RESULTS_DIR / 'merged_dataset.geojson')
    )

    logger.info("Основная информация")

    logger.info(f"Источник А (исходно): {cleaner_a.stats['initial']:,}")
    logger.info(f"Источник А (после очистки): {cleaner_a.stats['final']:,}")
    logger.info(f"Источник Б (исходно): {cleaner_b.stats['initial']:,}")
    logger.info(f"Источник Б (после очистки): {cleaner_b.stats['final']:,}")
    logger.info(f"Найдено совпадений: {len(merger.matches_df):,}")
    logger.info(f"Объединённый датасет: {len(gdf_merged):,}")
    logger.info(f"С высотой: {gdf_merged['final_height_m'].notna().sum():,} " f"({gdf_merged['final_height_m'].notna().mean() * 100:.1f}%)")
    logger.info(f"Признаков сгенерировано: {merger.feature_engineer.stats.get('total_features', 0)}")

    logger.info(f"\nРезультаты:")
    logger.info(f"   {config.RESULTS_DIR / 'cleaned_source_A.csv'}")
    logger.info(f"   {config.RESULTS_DIR / 'cleaned_source_B.csv'}")
    logger.info(f"   {config.RESULTS_DIR / 'merged_dataset.csv'}")
    logger.info(f"   {config.RESULTS_DIR / 'merged_dataset.geojson'}")
    logger.info(f"   {config.RESULTS_DIR / 'feature_stats.csv'}")

    return {
        'gdf_a_clean': gdf_a_clean,
        'gdf_b_clean': gdf_b_clean,
        'gdf_merged': gdf_merged,
        'stats_a': cleaner_a.stats,
        'stats_b': cleaner_b.stats
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--export-only', action='store_true', help='Только экспорт данных')
    args = parser.parse_args()

    results = main(args)
    if results:
        logger.info('Программа завершена успешно')
    else:
        logger.warning("Программа завершена с ошибкой")
        sys.exit(1)