"""Persistierung des Ergebnisses (Output-Layer).

Der kombinierte Datensatz wird in zwei Formaten abgelegt, weil sie
unterschiedliche Zwecke erfüllen:

**Parquet** ist das massgebliche Format für die Weiterverarbeitung. Es
speichert die Datentypen mit — ``date`` bleibt ein Zeitstempel,
``activity_type`` bleibt kategorial — und ist deutlich kompakter.

**CSV** ist die Kontrollkopie: in jedem Editor lesbar und ohne
Spezialwerkzeug prüfbar. Datentypen gehen dabei verloren, weshalb CSV nicht
als Eingang für weitere Verarbeitungsschritte dienen sollte.
"""

from pathlib import Path

import pandas as pd

from .logging_setup import get_logger
from .paths import PROCESSED_DIR

logger = get_logger(__name__)

#: Basisname der Ausgabedateien, ohne Endung.
OUTPUT_BASENAME = "combined_runs"

#: Parquet-Engine. Als Abhängigkeit in requirements.txt und pyproject.toml
#: geführt, da sie nicht Teil von pandas ist.
PARQUET_ENGINE = "pyarrow"


def write_outputs(
    df: pd.DataFrame,
    output_dir: Path = PROCESSED_DIR,
    basename: str = OUTPUT_BASENAME,
) -> dict[str, Path]:
    """Schreibt den Datensatz als Parquet und CSV.

    Der Zielordner wird angelegt, falls er noch nicht existiert.

    Args:
        df: Der zu persistierende Datensatz.
        output_dir: Zielordner. Standard ist
            :data:`running_data.paths.PROCESSED_DIR`.
        basename: Dateiname ohne Endung.

    Returns:
        Die geschriebenen Pfade unter den Schlüsseln ``"parquet"`` und
        ``"csv"``.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    paths = {
        "parquet": output_dir / f"{basename}.parquet",
        "csv": output_dir / f"{basename}.csv",
    }

    df.to_parquet(paths["parquet"], index=False, engine=PARQUET_ENGINE)
    df.to_csv(paths["csv"], index=False)

    logger.info(
        "Output geschrieben: %s (%d Zeilen)",
        ", ".join(str(p) for p in paths.values()),
        len(df),
    )
    return paths


def read_processed(
    output_dir: Path = PROCESSED_DIR, basename: str = OUTPUT_BASENAME
) -> pd.DataFrame:
    """Liest den zuvor geschriebenen Datensatz aus der Parquet-Datei.

    Dient der Kontrolle, dass die Persistierung verlustfrei war: Was hier
    zurückkommt, muss dem geschriebenen DataFrame entsprechen.

    Args:
        output_dir: Ordner der Ausgabedateien.
        basename: Dateiname ohne Endung.

    Returns:
        Der eingelesene Datensatz.
    """
    path = output_dir / f"{basename}.parquet"
    df = pd.read_parquet(path)
    logger.info("Gelesen: %s (%d Zeilen)", path, len(df))
    return df
