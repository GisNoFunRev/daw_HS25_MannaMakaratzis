"""Gemeinsame Fixtures für die Testsuite.

Grundsatz: kein Test greift auf data/ zu
---------------------------------------
Die echten Rohdaten liegen ausserhalb der Versionsverwaltung (siehe
.gitignore). Ein Test, der sie voraussetzt, schlägt bei jedem fehl, der das
Repository frisch auscheckt — auch beim Dozenten. Die Tests arbeiten deshalb
ausschliesslich mit zwei Quellen:

* tests/fixtures/ — winzige, erfundene Exportdateien im echten Format.
  Sie decken Import und End-to-End ab.
* make_runs — synthetische DataFrames im gemeinsamen Schema, direkt im
  Testcode konstruiert. Sie decken die Einzellogik ab, weil sich dort exakt
  der Grenzfall herstellen lässt, um den es gerade geht.
"""

from pathlib import Path

import pandas as pd
import pytest

from running_data import (
    DataCleaningConfig,
    build_cleaning_pipeline,
    import_apple_workouts,
    import_garmin_activities,
)
from running_data.cleaning import apple_typing, garmin_typing

# --- Pfade auf die Fixture-Exporte ------------------------------------------
# Der Aufbau spiegelt data/ bewusst exakt: <quelle>/<exportdatum>/<datei>.
# Das Exportdatum wird beim Import aus dem Ordnernamen gelesen, eine flachere
# Ablage würde die Fixtures also unbrauchbar machen.
FIXTURES_DIR = Path(__file__).parent / "fixtures"
GARMIN_FIXTURE_GLOB = str(FIXTURES_DIR / "garmin" / "*" / "Activities.csv")
APPLE_FIXTURE_GLOB = str(FIXTURES_DIR / "apple" / "*" / "Export.xml")

# Exportdatum der Fixtures, abgeleitet aus den Ordnernamen.
FIXTURE_EXPORT_DATE = "2025-08-22"


@pytest.fixture(scope="session")
def config() -> DataCleaningConfig:
    """Die Standardkonfiguration.

    Session-weit, weil sie nur Schwellenwerte hält und von keinem Test
    verändert wird.
    """
    return DataCleaningConfig()


@pytest.fixture
def garmin_raw() -> pd.DataFrame:
    """Rohimport der Garmin-Fixture: 5 Aktivitäten, davon 4 Läufe."""
    return import_garmin_activities(GARMIN_FIXTURE_GLOB)


@pytest.fixture
def garmin_typed(garmin_raw: pd.DataFrame) -> pd.DataFrame:
    """Garmin-Fixture gefiltert, reduziert und typisiert."""
    return garmin_typing.clean_garmin_typing(
        garmin_typing.reduce_to_core_columns(garmin_typing.filter_running(garmin_raw))
    )


@pytest.fixture
def garmin_cleaned(
    garmin_typed: pd.DataFrame, config: DataCleaningConfig
) -> pd.DataFrame:
    """Garmin-Fixture nach der vollständigen Bereinigungspipeline."""
    cleaned, _ = build_cleaning_pipeline("Garmin", config).run(garmin_typed)
    return cleaned


@pytest.fixture
def apple_raw() -> pd.DataFrame:
    """Rohimport der Apple-Fixture: 3 Workouts, davon 2 Läufe."""
    return import_apple_workouts(APPLE_FIXTURE_GLOB)


@pytest.fixture
def apple_typed(apple_raw: pd.DataFrame) -> pd.DataFrame:
    """Apple-Fixture gefiltert und typisiert."""
    return apple_typing.clean_apple_typing(apple_typing.filter_running(apple_raw))


@pytest.fixture
def apple_cleaned(
    apple_typed: pd.DataFrame, config: DataCleaningConfig
) -> pd.DataFrame:
    """Apple-Fixture nach der vollständigen Bereinigungspipeline."""
    cleaned, _ = build_cleaning_pipeline("Apple", config).run(apple_typed)
    return cleaned


# Plausible Vorgabewerte für einen Lauf. Ein Test überschreibt genau die
# Spalten, um die es ihm geht; alles andere bleibt unauffällig und stört die
# Prüfung nicht.
_RUN_DEFAULTS: dict[str, object] = {
    "date": "2025-08-01 07:00:00",
    "activity_type": "Running",
    "distance_km": 5.0,
    "duration_sec": 1800.0,
    "calories": 400.0,
    "avg_heart_rate": 150.0,
    "max_heart_rate": 170.0,
    "source": "garmin",
    "export_date": "2025-08-22",
}


@pytest.fixture
def make_runs():
    """Erzeugt synthetische Läufe im gemeinsamen Schema.

    Die Zeilenzahl ergibt sich aus der längsten übergebenen Liste; skalare
    Angaben werden auf diese Länge wiederholt. Nicht genannte Spalten werden
    mit plausiblen Vorgabewerten gefüllt.

    Beispiel:
        >>> make_runs(distance_km=[0.04, 0.05, 60.0, 60.1])
        # 4 Läufe, die sich nur in der Distanz unterscheiden

    Returns:
        Eine Funktion, die den DataFrame baut.
    """

    def _make(n: int | None = None, **columns: object) -> pd.DataFrame:
        unknown = set(columns) - set(_RUN_DEFAULTS)
        if unknown:
            raise ValueError(f"Unbekannte Spalten: {sorted(unknown)}")

        lengths = [len(v) for v in columns.values() if isinstance(v, list)]
        rows = n if n is not None else (max(lengths) if lengths else 1)

        data = {}
        for name, default in _RUN_DEFAULTS.items():
            value = columns.get(name, default)
            data[name] = list(value) if isinstance(value, list) else [value] * rows

        return pd.DataFrame(data)

    return _make
