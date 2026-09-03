"""Apple-spezifische Aufbereitung: Filtern, Schema und Einheiten.

Gegenstück zu running_data.cleaning.garmin_typing. Beide Module haben
dieselbe Aufgabe — die Rohdaten ihrer Quelle in das gemeinsame Schema
überführen — unterscheiden sich aber in den Eigenheiten, die sie dabei
ausgleichen müssen.

Einheitenkonventionen bei Apple Health
--------------------------------------
* Dauer numerisch in Minuten oder Sekunden (Garmin: Text hh:mm:ss).
* Distanz je nach Gerät in Kilometern, Metern oder Meilen.
* Energie in Kilokalorien oder Kilojoule.
* Herzfrequenz in count/min oder bpm.
* Zeitstempel mit Zeitzonen-Offset (Garmin: ohne).

Deklarierte Einheiten werden pro Workout explizit umgerechnet. Nur wenn das
XML keine Einheit enthält, greifen die konservativen Dauer- und
Distanzheuristiken als Rückwärtskompatibilitäts-Fallback.
"""

import numpy as np
import pandas as pd

from ..config import CATEGORICAL_COLUMNS, CORE_COLUMNS, NUMERIC_COLUMNS
from ..logging_setup import get_logger

logger = get_logger(__name__)

# Teilstring zur Erkennung von Laufaktivitäten. Enger gefasst als bei Garmin
# ("running" statt "run"), da Apple bereits normalisierte Typnamen liefert.
RUNNING_KEYWORD = "running"

# Liegt der Median der Dauer in diesem Bereich, sind die Werte in Minuten
# angegeben: Als Sekunden gelesen wären das 10 bis 200 Sekunden — für einen
# aufgezeichneten Lauf unrealistisch kurz.
DURATION_MINUTES_MEDIAN_RANGE = (10, 200)

# Ab diesem Wert wird die Distanz als in Metern angegeben interpretiert.
METERS_HEURISTIC_THRESHOLD = 200

DISTANCE_FACTORS_TO_KM: dict[str, float] = {
    "km": 1.0,
    "m": 0.001,
    "mi": 1.609344,
}
DURATION_FACTORS_TO_SECONDS: dict[str, float] = {"min": 60.0, "s": 1.0}
CALORIES_FACTORS_TO_KCAL: dict[str, float] = {"kcal": 1.0, "kj": 1 / 4.184}
HEART_RATE_FACTORS_TO_BPM: dict[str, float] = {"count/min": 1.0, "bpm": 1.0}


def filter_running(df: pd.DataFrame) -> pd.DataFrame:
    """Beschränkt den Datensatz auf Laufaktivitäten.

    Args:
        df: Importierte Apple-Workouts.

    Returns:
        Nur die Zeilen mit einer Laufaktivität.
    """
    before = len(df)
    filtered = df[
        df["activity_type"].str.lower().str.contains(RUNNING_KEYWORD, na=False)
    ].copy()

    logger.info(
        "Apple: Filter nach Laufsport: %d → %d (-%d)",
        before,
        len(filtered),
        before - len(filtered),
    )
    return filtered


def _harmonize_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """Benennt die neutralen Importspalten auf das gemeinsame Schema um.

    Reine Umbenennung ohne Umrechnung — die Einheiten werden erst später
    angeglichen. Bereits vorhandene Zielspalten werden nicht überschrieben.
    """
    rename_map = {}
    if "distance" in df.columns and "distance_km" not in df.columns:
        rename_map["distance"] = "distance_km"
    if "duration" in df.columns and "duration_sec" not in df.columns:
        rename_map["duration"] = "duration_sec"

    if rename_map:
        df = df.rename(columns=rename_map)
    return df


def _parse_local_timestamp(value: object) -> pd.Timestamp:
    """Parst einen Apple-Zeitstempel und bewahrt seine lokale Uhrzeit."""
    timestamp = pd.to_datetime(value, format="mixed", errors="coerce")
    if pd.isna(timestamp):
        return pd.NaT
    if timestamp.tzinfo is not None:
        timestamp = timestamp.tz_localize(None)
    return timestamp


def _normalize_timestamps(df: pd.DataFrame) -> pd.DataFrame:
    """Bringt die Zeitstempel auf dieselbe Darstellung wie bei Garmin.

    Apple liefert Zeitstempel mit Zeitzonen-Offset. Der Offset wird
    entfernt, nicht umgerechnet: Die Ortszeit des Laufs ist die
    fachlich relevante Grösse — ein Lauf um 7 Uhr morgens bleibt ein Lauf um
    7 Uhr morgens, unabhängig davon, in welcher Zeitzone er stattfand.
    """
    raw_dates = df.get(
        "date", pd.Series(pd.NaT, index=df.index, dtype="datetime64[ns]")
    )
    df["date"] = pd.Series(
        [_parse_local_timestamp(value) for value in raw_dates],
        index=df.index,
        dtype="datetime64[ns]",
    )

    df["export_date"] = pd.to_datetime(df.get("export_date"), errors="coerce")
    return df


def _normalize_declared_units(
    df: pd.DataFrame,
    value_columns: list[str],
    unit_column: str,
    factors: dict[str, float],
    quantity: str,
) -> pd.Series:
    """Rechnet deklarierte Einheiten um und meldet unsichere Deklarationen."""
    if unit_column in df.columns:
        display_units = df[unit_column].astype("string").str.strip()
    else:
        display_units = pd.Series("", index=df.index, dtype="string")

    normalized_units = display_units.str.casefold()
    missing_units = display_units.isna() | display_units.eq("")

    for unit, factor in factors.items():
        unit_rows = normalized_units.eq(unit).fillna(False)
        for column in value_columns:
            df.loc[unit_rows, column] = df.loc[unit_rows, column] * factor

    declared_units = ~missing_units
    supported_units = normalized_units.isin(factors)
    unsupported_rows = declared_units & ~supported_units

    for unit in display_units.loc[unsupported_rows].dropna().unique():
        unit_rows = unsupported_rows & display_units.eq(unit).fillna(False)
        affected_rows = int(unit_rows.sum())
        for column in value_columns:
            df.loc[unit_rows, column] = np.nan
        logger.warning(
            "Apple: Einheit '%s' für %s nicht unterstützt; "
            "%d Zeile(n) auf NaN gesetzt",
            unit,
            quantity,
            affected_rows,
        )

    return missing_units


def _normalize_units(df: pd.DataFrame) -> pd.DataFrame:
    """Normalisiert deklarierte Einheiten und nutzt Heuristiken als Fallback."""
    distance_fallback_rows = _normalize_declared_units(
        df,
        ["distance_km"],
        "distance_unit",
        DISTANCE_FACTORS_TO_KM,
        "distance",
    )
    duration_fallback_rows = _normalize_declared_units(
        df,
        ["duration_sec"],
        "duration_unit",
        DURATION_FACTORS_TO_SECONDS,
        "duration",
    )
    _normalize_declared_units(
        df,
        ["calories"],
        "calories_unit",
        CALORIES_FACTORS_TO_KCAL,
        "calories",
    )
    _normalize_declared_units(
        df,
        ["avg_heart_rate", "max_heart_rate"],
        "heart_rate_unit",
        HEART_RATE_FACTORS_TO_BPM,
        "heart_rate",
    )

    fallback_durations = df.loc[duration_fallback_rows, "duration_sec"]
    median_duration = fallback_durations.median()
    lower, upper = DURATION_MINUTES_MEDIAN_RANGE
    if pd.notna(median_duration) and lower <= median_duration <= upper:
        df.loc[duration_fallback_rows, "duration_sec"] = (
            fallback_durations * DURATION_FACTORS_TO_SECONDS["min"]
        )
        logger.info(
            "Apple: duration_sec war in MINUTEN -> in Sekunden umgerechnet (*60)"
        )

    fallback_distances = df.loc[distance_fallback_rows, "distance_km"]
    if (fallback_distances > METERS_HEURISTIC_THRESHOLD).any():
        df.loc[distance_fallback_rows, "distance_km"] = (
            fallback_distances * DISTANCE_FACTORS_TO_KM["m"]
        )
        logger.info(
            "Apple: distance_km war in METERN -> in Kilometer umgerechnet (/1000)"
        )

    return df


def clean_apple_typing(df: pd.DataFrame) -> pd.DataFrame:
    """Überführt die gefilterten Apple-Daten in das gemeinsame Schema.

    Args:
        df: Gefilterte Apple-Workouts mit den neutralen Importspalten
            date, activity_type, distance, duration,
            calories, avg_heart_rate, max_heart_rate, source und export_date.
            Die optionalen Spalten duration_unit, distance_unit,
            calories_unit und heart_rate_unit enthalten deklarierte Einheiten.

    Returns:
        Datensatz mit exakt den Spalten aus
        CORE_COLUMNS, in dieser Reihenfolge.
    """
    df = df.copy()

    df = _harmonize_column_names(df)
    df = _normalize_timestamps(df)

    # Numerik casten, bevor die Einheiten-Heuristiken rechnen.
    for col in NUMERIC_COLUMNS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")
        else:
            df[col] = np.nan

    df = _normalize_units(df)

    for col in CATEGORICAL_COLUMNS:
        df[col] = df[col].astype("category")

    # Schema festzurren: fehlende Spalten ergaenzen, Reihenfolge sichern.
    for col in CORE_COLUMNS:
        if col not in df.columns:
            df[col] = np.nan

    logger.info("Apple: Typisierung & Einheiten abgeschlossen")
    return df[CORE_COLUMNS].copy()
