"""Die Gesamtpipeline als eine aufrufbare Funktion (LE5).

Warum dieses Modul existiert
----------------------------
Die Verarbeitung war bisher nur als Abfolge von Notebook-Zellen ausführbar.
Wer sie starten wollte, musste das Notebook öffnen und alle Zellen in der
richtigen Reihenfolge laufen lassen — aus einem Skript, aus der Kommandozeile
oder aus einem Test heraus war sie nicht erreichbar.

Dass die Reihenfolge nur in Zellpositionen existierte, hatte bereits eine
konkrete Folge: Der Feature-Schritt war implementiert und exportiert, wurde
aber von keiner Zelle aufgerufen. Die abgeleiteten Variablen fehlten dadurch
im Ergebnis, ohne dass etwas fehlschlug. Hier steht die Reihenfolge einmal an
einer Stelle, und ein neuer Schritt wird entweder eingefügt oder eben nicht.

Verarbeitungskette
------------------
    je Quelle:  Import → Typisierung → Bereinigung (8 Schritte)
    danach:     Zusammenführung → abgeleitete Variablen → Export

Aufruf
------
    from running_data import run_pipeline

    result = run_pipeline()
    result.data          # der fertige Datensatz
    result.outputs       # die geschriebenen Dateien

Aus der Kommandozeile: python -m running_data (siehe running_data.__main__).
"""

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from ..cleaning import apple_typing, garmin_typing
from ..combine import concat_sources
from ..config import DataCleaningConfig
from ..export import write_outputs
from ..features import add_features
from ..ingest.apple import import_apple_workouts
from ..ingest.garmin import import_garmin_activities
from ..logging_setup import get_logger
from ..paths import APPLE_GLOB, GARMIN_GLOB, PROCESSED_DIR
from .factory import build_cleaning_pipeline
from .quality import DataQualityChecker
from .report import CleaningReport

logger = get_logger(__name__)

# Quellennamen. Sie erscheinen im Log, im Bericht und als Schlüssel in den
# Dictionaries des Ergebnisses.
SOURCE_GARMIN = "Garmin"
SOURCE_APPLE = "Apple"


@dataclass(frozen=True)
class PipelineResult:
    """Das vollständige Ergebnis eines Pipeline-Laufs.

    Mehr als nur der Datensatz, weil die Zwischenergebnisse für die
    Nachvollziehbarkeit gebraucht werden: Das Notebook zeigt Bericht und
    Qualitätsmetriken an, und die Tests prüfen sie.

    Attributes:
        data: Der kombinierte, bereinigte Datensatz inklusive der
            abgeleiteten Variablen.
        reports: Je Quelle der Bereinigungsbericht mit der Schritt-für-
            Schritt-Statistik.
        summaries: Je Quelle die Kennzahlen des Laufs (Zeilen vorher/nachher,
            Retention Rate). Bereits ausgewertet, damit der Aufrufer nicht
            CleaningReport.summary aufrufen muss — das würde die
            Zusammenfassung ein zweites Mal ins Log schreiben.
        qualities: Je Quelle die Datenqualitäts-Metriken.
        outputs: Die geschriebenen Dateien unter den Schlüsseln "parquet"
            und "csv". Leer, wenn ohne output_dir aufgerufen wurde.
    """

    data: pd.DataFrame
    reports: dict[str, CleaningReport]
    summaries: dict[str, dict]
    qualities: dict[str, dict]
    outputs: dict[str, Path]


def _prepare_garmin(garmin_path: str) -> pd.DataFrame:
    """Importiert und typisiert die Garmin-Daten.

    Args:
        garmin_path: Glob-Muster der Garmin-CSV-Exporte.

    Returns:
        Die Laufaktivitäten im gemeinsamen CORE_COLUMNS-Schema, oder ein
        leerer DataFrame, wenn das Muster auf keine Datei passt.
    """
    raw = import_garmin_activities(garmin_path)
    if raw.empty:
        return raw

    return garmin_typing.clean_garmin_typing(
        garmin_typing.reduce_to_core_columns(garmin_typing.filter_running(raw))
    )


def _prepare_apple(apple_path: str) -> pd.DataFrame:
    """Importiert und typisiert die Apple-Daten.

    Args:
        apple_path: Glob-Muster der Apple-XML-Exporte.

    Returns:
        Die Laufaktivitäten im gemeinsamen CORE_COLUMNS-Schema, oder ein
        leerer DataFrame, wenn das Muster auf keine Datei passt.

    Note:
        Die Prüfung auf einen leeren Import ist hier nicht nur eine
        Abkürzung: apple_typing.filter_running greift ohne Absicherung auf
        die Spalte activity_type zu und würde bei einem leeren DataFrame mit
        einem KeyError abbrechen. Das Garmin-Pendant fängt denselben Fall ab.
    """
    raw = import_apple_workouts(apple_path)
    if raw.empty:
        return raw

    return apple_typing.clean_apple_typing(apple_typing.filter_running(raw))


def run_pipeline(
    garmin_path: str = GARMIN_GLOB,
    apple_path: str = APPLE_GLOB,
    output_dir: Path | None = PROCESSED_DIR,
    config: DataCleaningConfig | None = None,
) -> PipelineResult:
    """Führt die gesamte Verarbeitung von den Rohdateien bis zum Export aus.

    Eine Quelle, die keine Laufaktivitäten liefert, wird übersprungen statt
    zum Abbruch zu führen: Das Projekt soll auch dann durchlaufen, wenn nur
    einer der beiden Exporte vorliegt.

    Args:
        garmin_path: Glob-Muster der Garmin-CSV-Exporte. Standard ist
            running_data.paths.GARMIN_GLOB.
        apple_path: Glob-Muster der Apple-XML-Exporte. Standard ist
            running_data.paths.APPLE_GLOB.
        output_dir: Zielordner für Parquet und CSV. None schreibt nichts
            und liefert das Ergebnis nur im Speicher zurück.
        config: Schwellenwerte der Bereinigung. None verwendet die
            Standardkonfiguration.

    Returns:
        Das Ergebnis als PipelineResult.

    Raises:
        ValueError: Wenn keine der beiden Quellen Laufaktivitäten geliefert
            hat. Ein leeres Ergebnis wäre kein sinnvoller Erfolgsfall,
            sondern fast immer ein falscher Pfad.
    """
    config = config or DataCleaningConfig()

    typed_by_source = {
        SOURCE_GARMIN: _prepare_garmin(garmin_path),
        SOURCE_APPLE: _prepare_apple(apple_path),
    }

    frames: list[pd.DataFrame] = []
    reports: dict[str, CleaningReport] = {}
    summaries: dict[str, dict] = {}
    qualities: dict[str, dict] = {}

    for source, typed in typed_by_source.items():
        if typed.empty:
            logger.warning(
                "%s: keine Laufaktivitäten gefunden, Quelle wird übersprungen",
                source,
            )
            continue

        cleaned, report = build_cleaning_pipeline(source, config).run(typed)

        frames.append(cleaned)
        reports[source] = report
        summaries[source] = report.summary()
        qualities[source] = DataQualityChecker.assess_quality(cleaned, config)

    if not frames:
        raise ValueError(
            "Keine der Quellen hat Laufaktivitäten geliefert. Geprüfte Muster: "
            f"garmin_path={garmin_path!r}, apple_path={apple_path!r}"
        )

    combined = concat_sources(frames)
    featured = add_features(combined)

    outputs = write_outputs(featured, output_dir) if output_dir is not None else {}

    logger.info(
        "Pipeline abgeschlossen: %d Zeilen, %d Spalten aus %d Quelle(n)",
        len(featured),
        featured.shape[1],
        len(frames),
    )

    return PipelineResult(
        data=featured,
        reports=reports,
        summaries=summaries,
        qualities=qualities,
        outputs=outputs,
    )
