"""Data-Wrangling-Pipeline für Laufdaten aus Garmin Connect und Apple Health.

Das Paket bündelt die gesamte Verarbeitungslogik, die zuvor direkt im
Quarto-Notebook stand. Das Notebook (notebooks/data_wrangling.qmd) ruft
diese Module nur noch auf und stellt die Ergebnisse dar.

Verarbeitungskette
------------------
    ingest        →  cleaning        →  pipeline       →  combine  →  export
    Rohdaten je      Typisierung je     8 Schritte,       beide       Parquet
    Quelle lesen     Quelle, dann       je Quelle         Quellen     und CSV
                     harmonisiert       identisch         vereint

Aufbau des Pakets
-----------------
config
    Zentrale Schwellenwerte und Schema-Konstanten.
paths
    Projektpfade, unabhängig vom aktuellen Arbeitsverzeichnis.
logging_setup
    Einrichtung des Loggings — vom Notebook aufzurufen, nicht von Modulen.
ingest
    Rohdaten-Import je Quelle (Garmin CSV, Apple XML, GPX).
cleaning
    Typisierung, Validatoren, Imputation und die Bereinigungsschritte.
pipeline
    Pipeline-Pattern, Bereinigungsbericht und Datenqualitäts-Metriken.
combine
    Zusammenführung der bereinigten Quellen.
export
    Persistierung des Ergebnisses.
features
    Abgeleitete Variablen (noch nicht implementiert).

Beispiel
--------
    from running_data import (
        DataCleaningConfig, build_cleaning_pipeline, concat_sources,
        configure_logging, import_garmin_activities, write_outputs,
    )
    from running_data.cleaning import garmin_typing

    configure_logging()
    config = DataCleaningConfig()

    typed = garmin_typing.clean_garmin_typing(
        garmin_typing.reduce_to_core_columns(
            garmin_typing.filter_running(import_garmin_activities())
        )
    )
    cleaned, report = build_cleaning_pipeline("Garmin", config).run(typed)
    write_outputs(concat_sources([cleaned]))
"""

from .combine import concat_sources
from .config import (
    CATEGORICAL_COLUMNS,
    CORE_COLUMNS,
    NUMERIC_COLUMNS,
    RAW_CORE_COLUMNS,
    DataCleaningConfig,
)
from .export import read_processed, write_outputs
from .ingest.apple import import_apple_workouts
from .ingest.garmin import import_garmin_activities
from .logging_setup import configure_logging, get_logger
from .pipeline.factory import build_cleaning_pipeline
from .pipeline.quality import DataQualityChecker, build_comparison_table

__version__ = "0.1.0"

__all__ = [
    # Konfiguration und Infrastruktur
    "DataCleaningConfig",
    "CORE_COLUMNS",
    "RAW_CORE_COLUMNS",
    "NUMERIC_COLUMNS",
    "CATEGORICAL_COLUMNS",
    "configure_logging",
    "get_logger",
    # Import
    "import_garmin_activities",
    "import_apple_workouts",
    # Bereinigung
    "build_cleaning_pipeline",
    # Qualität
    "DataQualityChecker",
    "build_comparison_table",
    # Zusammenführen und Export
    "concat_sources",
    "write_outputs",
    "read_processed",
    "__version__",
]
