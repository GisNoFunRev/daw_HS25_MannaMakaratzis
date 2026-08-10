"""Import der Garmin-Connect-Aktivitäten (LE1).

Datenquelle
-----------
CSV-Export aus Garmin Connect, abgelegt unter
``data/garmin/<exportdatum>/Activities.csv``.

Besonderheiten des Formats
--------------------------
* **Encoding**: Garmin exportiert nicht in UTF-8, sondern je nach Version in
  Latin-1 bzw. CP1252. Ein fester Encoding-Parameter schlägt deshalb
  sporadisch fehl; stattdessen werden mehrere Kandidaten der Reihe nach
  probiert.
* **Trennzeichen**: Semikolon statt Komma (europäisches Format).
* **Spaltennamen**: nicht standardisiert, mit Leerzeichen ("Avg HR").

Dieses Modul führt bewusst **keine** Bereinigung und keine
Einheitenumrechnung durch. Es liest die Rohwerte und vereinheitlicht
lediglich die Spaltennamen, damit Garmin- und Apple-Daten anschliessend
dieselbe Bereinigungspipeline durchlaufen können.
"""

import glob
from pathlib import Path

import pandas as pd

from ..logging_setup import get_logger
from ..paths import GARMIN_GLOB

logger = get_logger(__name__)

#: Encodings in der Reihenfolge, in der sie probiert werden. Latin-1 zuerst,
#: weil es das in den vorliegenden Exporten tatsächlich verwendete ist.
CANDIDATE_ENCODINGS: tuple[str, ...] = ("latin-1", "iso-8859-1", "utf-8", "cp1252")

#: Abbildung der Garmin-Spaltennamen auf das gemeinsame Schema.
#: Noch Teil von LE1 (Struktur angleichen), nicht von LE2 (Daten bereinigen).
COLUMN_RENAME_MAP: dict[str, str] = {
    "Activity Type": "activity_type",
    "Date": "date",
    "Distance": "distance_km",
    "Calories": "calories",
    "Time": "duration",
    "Avg HR": "avg_heart_rate",
    "Max HR": "max_heart_rate",
}


def _read_csv_with_fallback_encoding(file: str) -> pd.DataFrame | None:
    """Liest eine Garmin-CSV und probiert dabei mehrere Encodings durch.

    Args:
        file: Pfad zur CSV-Datei.

    Returns:
        Der eingelesene DataFrame, oder ``None``, wenn keines der Encodings
        in :data:`CANDIDATE_ENCODINGS` funktioniert hat.
    """
    for encoding in CANDIDATE_ENCODINGS:
        try:
            df = pd.read_csv(file, sep=";", encoding=encoding)
        except UnicodeDecodeError:
            continue
        logger.info("Garmin: %s mit Encoding %s gelesen", file, encoding)
        return df

    logger.error("Garmin: %s konnte mit keinem Encoding gelesen werden", file)
    return None


def import_garmin_activities(data_path: str = GARMIN_GLOB) -> pd.DataFrame:
    """Importiert alle Garmin-CSV-Exporte und fügt sie zusammen.

    Je Exportordner wird das Exportdatum aus dem Ordnernamen übernommen
    (z. B. ``data/garmin/2025-08-22/`` → ``export_date = "2025-08-22"``).
    Das erlaubt es, mehrere Exporte nebeneinander abzulegen und später
    nachzuvollziehen, aus welchem Export eine Zeile stammt.

    Args:
        data_path: Glob-Muster der zu lesenden CSV-Dateien. Standard ist
            :data:`running_data.paths.GARMIN_GLOB`.

    Returns:
        Alle Aktivitäten aller Exporte in einem DataFrame mit
        vereinheitlichten Spaltennamen. Leerer DataFrame, wenn keine Datei
        gefunden oder keine lesbar war.
    """
    garmin_files = glob.glob(data_path)
    garmin_dfs: list[pd.DataFrame] = []

    for file in garmin_files:
        df = _read_csv_with_fallback_encoding(file)
        if df is None:
            continue

        # Herkunft festhalten: Quelle zur Harmonisierung mit Apple,
        # Exportdatum aus dem Ordnernamen.
        df["source"] = "garmin"
        df["export_date"] = Path(file).parent.name

        df = df.rename(columns=COLUMN_RENAME_MAP)
        garmin_dfs.append(df)

    if not garmin_dfs:
        logger.warning("Garmin: Import ergab keine Aktivitäten (%s)", data_path)
        return pd.DataFrame()

    combined = pd.concat(garmin_dfs, ignore_index=True)
    logger.info(
        "Garmin: Import abgeschlossen. Dateien: %d | Aktivitäten: %d",
        len(garmin_dfs),
        len(combined),
    )
    return combined
