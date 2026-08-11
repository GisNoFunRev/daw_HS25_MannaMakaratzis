"""Garmin-spezifische Aufbereitung: Filtern, Schema und Einheiten.

Dieses Modul überführt die Garmin-Rohdaten in das gemeinsame Schema. Danach
sind die Daten von den Apple-Daten strukturell nicht mehr zu unterscheiden
und durchlaufen dieselbe Pipeline.

Einheitenkonventionen bei Garmin
--------------------------------
* Dauer als Text im Format hh:mm:ss oder mm:ss.
* Distanz je nach Exporteinstellung in Kilometern oder Metern.
"""

import numpy as np
import pandas as pd

from ..config import (
    CATEGORICAL_COLUMNS,
    CORE_COLUMNS,
    NUMERIC_COLUMNS,
    RAW_CORE_COLUMNS,
)
from ..logging_setup import get_logger

logger = get_logger(__name__)

# Teilstring, an dem Laufaktivitäten erkannt werden. Garmin verwendet
# mehrere Varianten ("Running", "Trail Running", "Treadmill Running"), die
# alle diesen Wortstamm enthalten.
RUNNING_KEYWORD = "run"

# Ab diesem Wert wird angenommen, dass die Distanz in Metern statt in
# Kilometern vorliegt. 200 km liegt oberhalb jeder plausiblen Laufdistanz.
METERS_HEURISTIC_THRESHOLD = 200


def filter_running(df: pd.DataFrame) -> pd.DataFrame:
    """Beschränkt den Datensatz auf Laufaktivitäten.

    Args:
        df: Importierte Garmin-Aktivitäten.

    Returns:
        Nur die Zeilen mit einer Laufaktivität. Fehlt die Spalte
        activity_type, wird der Datensatz unverändert zurückgegeben.
    """
    if "activity_type" not in df.columns:
        logger.warning("Garmin: Spalte activity_type fehlt, Filter übersprungen")
        return df

    before = len(df)
    filtered = df[
        df["activity_type"].str.lower().str.contains(RUNNING_KEYWORD, na=False)
    ].copy()

    logger.info(
        "Garmin: Filter nach Laufsport: %d → %d (-%d)",
        before,
        len(filtered),
        before - len(filtered),
    )
    return filtered


def reduce_to_core_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Reduziert den Datensatz auf die Kernvariablen.

    Der Garmin-Export enthält rund 30 Spalten, von denen nur neun für die
    Auswertung gebraucht werden. Fehlende Kernspalten werden mit pd.NA
    ergänzt, damit das Schema unabhängig von der Exportversion stabil bleibt.

    Args:
        df: Gefilterte Garmin-Aktivitäten.

    Returns:
        Datensatz mit exakt den Spalten aus
        RAW_CORE_COLUMNS, in dieser Reihenfolge.
    """
    present = [c for c in RAW_CORE_COLUMNS if c in df.columns]
    missing = [c for c in RAW_CORE_COLUMNS if c not in df.columns]

    core = df[present].copy()
    for col in missing:
        core[col] = pd.NA

    if missing:
        logger.warning("Garmin: fehlende Kernvariablen ergänzt: %s", missing)

    logger.info(
        "Garmin: Reduktion auf %d Kernvariablen abgeschlossen", len(RAW_CORE_COLUMNS)
    )
    return core[RAW_CORE_COLUMNS]


def convert_duration_to_seconds(duration_str: object) -> float:
    """Rechnet eine Garmin-Dauerangabe in Sekunden um.

    Verarbeitet hh:mm:ss und mm:ss; bereits numerische Werte werden
    unverändert übernommen.

    Args:
        duration_str: Dauer als Text, Zahl oder fehlender Wert.

    Returns:
        Die Dauer in Sekunden, oder NaN bei fehlender oder nicht
        interpretierbarer Eingabe.
    """
    if pd.isna(duration_str):
        return np.nan

    try:
        parts = [float(x) for x in str(duration_str).split(":")]
        if len(parts) == 3:  # hh:mm:ss
            return parts[0] * 3600 + parts[1] * 60 + parts[2]
        if len(parts) == 2:  # mm:ss
            return parts[0] * 60 + parts[1]
        return float(duration_str)  # bereits numerisch
    except (ValueError, TypeError):
        return np.nan


def clean_garmin_typing(df: pd.DataFrame) -> pd.DataFrame:
    """Setzt Datentypen und normalisiert die Einheiten der Garmin-Daten.

    Args:
        df: Datensatz im Schema
            RAW_CORE_COLUMNS.

    Returns:
        Datensatz im gemeinsamen CORE_COLUMNS-Schema mit harmonisierter
        duration_sec sowie numerisch typisierten Messwerten und
        kategorialen Schlüsselspalten.

    Note:
        Die Garmin-Rohspalte duration wird nach der Umrechnung entfernt.
        Die Laufdauer wird quellenübergreifend ausschliesslich über
        duration_sec im gemeinsamen CORE_COLUMNS-Schema weitergeführt.
    """
    df = df.copy()

    df["export_date"] = pd.to_datetime(df["export_date"], errors="coerce")

    # Garmin dates use the European DD.MM.YYYY format.
    # Parse explicitly to prevent pandas from swapping day and month or producing NaT.
    df["date"] = pd.to_datetime(
        df["date"],
        format="%d.%m.%Y %H:%M",
        errors="coerce",
    )
    df["duration_sec"] = df["duration"].apply(convert_duration_to_seconds)

    # Heuristik: Liegt der Maximalwert oberhalb jeder plausiblen Laufdistanz,
    # ist die Spalte in Metern exportiert worden.
    if df["distance_km"].dropna().max() > METERS_HEURISTIC_THRESHOLD:
        logger.info("Garmin: Distanz scheint in Metern zu sein → Konvertierung zu km")
        df["distance_km"] = df["distance_km"] / 1000

    for col in NUMERIC_COLUMNS:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    for col in CATEGORICAL_COLUMNS:
        df[col] = df[col].astype("category")

    logger.info("Garmin: Typisierung & Einheiten abgeschlossen")
    return df[CORE_COLUMNS].copy()
