"""Apple-spezifische Aufbereitung: Filtern, Schema und Einheiten.

Gegenstück zu :mod:`running_data.cleaning.garmin_typing`. Beide Module haben
dieselbe Aufgabe — die Rohdaten ihrer Quelle in das gemeinsame Schema
überführen — unterscheiden sich aber in den Eigenheiten, die sie dabei
ausgleichen müssen.

Einheitenkonventionen bei Apple Health
--------------------------------------
* **Dauer** numerisch, üblicherweise in Minuten (Garmin: Text ``hh:mm:ss``).
* **Distanz** je nach Gerät in Kilometern oder Metern.
* **Zeitstempel** mit Zeitzonen-Offset (Garmin: ohne).

Die Einheiten sind im Export nicht deklariert, weshalb sie über Heuristiken
erkannt werden. Beide sind bewusst konservativ gewählt, sodass sie nur
anschlagen, wenn die Alternative physikalisch unmöglich wäre.
"""

import numpy as np
import pandas as pd

from ..config import CATEGORICAL_COLUMNS, CORE_COLUMNS, NUMERIC_COLUMNS
from ..logging_setup import get_logger

logger = get_logger(__name__)

#: Teilstring zur Erkennung von Laufaktivitäten. Enger gefasst als bei Garmin
#: ("running" statt "run"), da Apple bereits normalisierte Typnamen liefert.
RUNNING_KEYWORD = "running"

#: Liegt der Median der Dauer in diesem Bereich, sind die Werte in Minuten
#: angegeben: Als Sekunden gelesen wären das 10 bis 200 Sekunden — für einen
#: aufgezeichneten Lauf unrealistisch kurz.
DURATION_MINUTES_MEDIAN_RANGE = (10, 200)

#: Ab diesem Wert wird die Distanz als in Metern angegeben interpretiert.
METERS_HEURISTIC_THRESHOLD = 200

#: Zielformat des Zeitstempels, abgestimmt auf die Garmin-Daten.
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


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


def _normalize_timestamps(df: pd.DataFrame) -> pd.DataFrame:
    """Bringt die Zeitstempel auf dieselbe Darstellung wie bei Garmin.

    Apple liefert Zeitstempel mit Zeitzonen-Offset. Der Offset wird
    **entfernt, nicht umgerechnet**: Die Ortszeit des Laufs ist die
    fachlich relevante Grösse — ein Lauf um 7 Uhr morgens bleibt ein Lauf um
    7 Uhr morgens, unabhängig davon, in welcher Zeitzone er stattfand.
    """
    df["date"] = pd.to_datetime(df.get("date"), errors="coerce")

    mask = df["date"].notna() & df["date"].apply(
        lambda x: getattr(x, "tzinfo", None) is not None
    )
    if mask.any():
        df.loc[mask, "date"] = df.loc[mask, "date"].dt.tz_localize(None)

    # Nach dem teilweisen Ersetzen oben kann die Spalte den Typ object
    # angenommen haben - erneut sicher nach datetime64[ns] konvertieren.
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["date"] = df["date"].dt.strftime(DATE_FORMAT)

    df["export_date"] = pd.to_datetime(df.get("export_date"), errors="coerce")
    return df


def _normalize_units(df: pd.DataFrame) -> pd.DataFrame:
    """Erkennt und korrigiert abweichende Einheiten bei Dauer und Distanz."""
    median_duration = df["duration_sec"].median()
    lower, upper = DURATION_MINUTES_MEDIAN_RANGE
    if pd.notna(median_duration) and lower <= median_duration <= upper:
        df["duration_sec"] = df["duration_sec"] * 60
        logger.info("Apple: duration_sec war in MINUTEN → in Sekunden umgerechnet (×60)")

    if (df["distance_km"] > METERS_HEURISTIC_THRESHOLD).any():
        df["distance_km"] = df["distance_km"] / 1000.0
        logger.info("Apple: distance_km war in METERN → in Kilometer umgerechnet (/1000)")

    return df


def clean_apple_typing(df: pd.DataFrame) -> pd.DataFrame:
    """Überführt die gefilterten Apple-Daten in das gemeinsame Schema.

    Args:
        df: Gefilterte Apple-Workouts mit den neutralen Importspalten
            ``date``, ``activity_type``, ``distance``, ``duration``,
            ``calories``, ``avg_heart_rate``, ``max_heart_rate``, ``source``
            und ``export_date``.

    Returns:
        Datensatz mit exakt den Spalten aus
        :data:`~running_data.config.CORE_COLUMNS`, in dieser Reihenfolge.
    """
    df = df.copy()

    df = _harmonize_column_names(df)
    df = _normalize_timestamps(df)

    # Numerik casten, bevor die Einheiten-Heuristiken rechnen.
    for col in NUMERIC_COLUMNS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
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
