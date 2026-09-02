from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict


@dataclass
class CleaningConfig:
    """Параметры очистки данных."""
    MIN_AREA_SQM: float = 10.0
    MAX_AREA_SQM: float = 50000.0
    MIN_HEIGHT_M: float = 2.0
    MAX_HEIGHT_M: float = 200.0
    OUTLIER_ZSCORE_THRESHOLD: float = 3.0
    SHED_TAGS: List[str] = field(default_factory=lambda: [
        'гараж', 'гаражный', 'сарай', 'теплица', 'будка', 'киоск',
        'навес', 'пристройка', 'временное', 'временная',
        'некапитальное', 'хозяйственное', 'подсобное',
        'garage', 'shed', 'temporary', 'storage', 'booth'
    ])
    MIN_IOU_THRESHOLD: float = 0.1
    MAX_DISTANCE_METERS: float = 50.0
    MAX_AREA_RATIO: float = 5.0
    CRS_INPUT: str = "EPSG:4326"
    CRS_METRIC: str = "EPSG:3857"


@dataclass
class FeatureConfig:
    """Параметры Feature Engineering."""

    GEOMETRY_FEATURES: List[str] = field(default_factory=lambda: [
        'area_sq_m', 'perimeter', 'compactness', 'elongation',
        'vertices_count', 'convex_hull_area', 'bounding_box_area'
    ])

    NEIGHBOR_RADII_METERS: List[float] = field(default_factory=lambda: [25, 50, 100, 200])

    BUILDING_TYPES: Dict[str, List[str]] = field(default_factory=lambda: {
        'residential': ['жилое', 'residential', 'жилой', 'апартамент'],
        'office': ['офис', 'office', 'бизнес', 'business', 'административное'],
        'retail': ['торг', 'shop', 'магазин', 'retail', 'торговый'],
        'public': ['культура', 'culture', 'образование', 'education', 'больница', 'hospital'],
        'industrial': ['производ', 'industrial', 'склад', 'warehouse', 'завод'],
        'shed': ['гараж', 'garage', 'сарай', 'shed', 'теплица']
    })

    STATISTICAL_FEATURES: List[str] = field(default_factory=lambda: [
        'area_zscore', 'area_quantile', 'height_zscore', 'height_quantile'
    ])

    SPATIAL_FEATURES: List[str] = field(default_factory=lambda: [
        'distance_to_center', 'x_coord', 'y_coord', 'h3_index'
    ])


@dataclass
class Config:
    """Основная конфигурация."""

    PROJECT_ROOT: Path = Path(__file__).parent.parent
    DATA_DIR: Path = PROJECT_ROOT / "data"
    RESULTS_DIR: Path = PROJECT_ROOT / "results"
    LOGS_DIR: Path = PROJECT_ROOT / "logs"

    SOURCE_A: Path = DATA_DIR / "cup_it_example_src_A.csv"
    SOURCE_B: Path = DATA_DIR / "cup_it_example_src_B.csv"

    CLEANING: CleaningConfig = field(default_factory=CleaningConfig)
    FEATURES: FeatureConfig = field(default_factory=FeatureConfig)

    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = '%(asctime)s - %(levelname)s - %(message)s'

    def __post_init__(self):
        for dir_path in [self.RESULTS_DIR, self.LOGS_DIR]:
            dir_path.mkdir(exist_ok=True, parents=True)


config = Config()