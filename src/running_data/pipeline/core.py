"""Das Pipeline-Pattern (LE5).

Dieses Modul enthält die Mechanik der Pipeline, aber bewusst **keine**
konkreten Bereinigungsschritte: :class:`DataCleaningPipeline` weiss nicht, was
"Herzfrequenz bereinigen" bedeutet, sondern nur, wie ein beliebiger Schritt
ausgeführt, protokolliert und im Fehlerfall behandelt wird.

Welche Schritte tatsächlich zusammengesetzt werden, entscheidet
:mod:`running_data.pipeline.factory`. Diese Trennung erlaubt es, die
Reihenfolge der Bereinigung zu ändern, ohne die Ausführungslogik anzufassen.

Fehlerbehandlung
----------------
Jeder Schritt ist als kritisch oder unkritisch markiert:

* **kritisch** — schlägt der Schritt fehl oder bleibt kein Datensatz übrig,
  bricht die Pipeline ab. Beispiel: das Entfernen von Zeilen ohne Distanz und
  Dauer. Ohne diese Werte ist eine Weiterverarbeitung sinnlos.
* **unkritisch** — der Fehler wird protokolliert, die Pipeline läuft mit dem
  Datenstand *vor* dem Schritt weiter. Beispiel: die Kalorien-Imputation; ein
  fehlender Kalorienwert macht einen Lauf nicht unbrauchbar.
"""

from dataclasses import dataclass
from typing import Callable

import pandas as pd

from ..config import DataCleaningConfig
from ..logging_setup import get_logger
from .report import CleaningReport

logger = get_logger(__name__)

#: Signatur, der jeder Bereinigungsschritt genügen muss. Die einheitliche
#: Signatur ist der Grund, warum die Pipeline Schritte austauschbar behandeln
#: kann, ohne sie zu kennen.
CleaningStepFunction = Callable[
    [pd.DataFrame, DataCleaningConfig, CleaningReport], pd.DataFrame
]


@dataclass
class CleaningStep:
    """Ein einzelner Schritt der Bereinigungspipeline.

    Attributes:
        name: Anzeigename, erscheint im Log und im Bericht.
        function: Die auszuführende Funktion, siehe
            :data:`CleaningStepFunction`.
        description: Beschreibung für die Dokumentation.
        is_critical: Ob ein Fehler die Pipeline abbrechen soll.
    """

    name: str
    function: CleaningStepFunction
    description: str
    is_critical: bool = False


class DataCleaningPipeline:
    """Führt eine Folge von :class:`CleaningStep` nacheinander aus.

    Beispiel:
        >>> pipeline = DataCleaningPipeline("Garmin", config)
        >>> pipeline.add_step(step_a).add_step(step_b)
        >>> cleaned, report = pipeline.run(df)
    """

    def __init__(self, source: str, config: DataCleaningConfig) -> None:
        self.source = source
        self.config = config
        self.report = CleaningReport(source)
        self.steps: list[CleaningStep] = []

    def add_step(self, step: CleaningStep) -> "DataCleaningPipeline":
        """Hängt einen Schritt an das Ende der Pipeline.

        Returns:
            Die Pipeline selbst, damit Aufrufe verkettet werden können
            (``pipeline.add_step(a).add_step(b)``).
        """
        self.steps.append(step)
        return self

    def run(self, df: pd.DataFrame) -> tuple[pd.DataFrame, CleaningReport]:
        """Führt alle Schritte in der hinzugefügten Reihenfolge aus.

        Args:
            df: Der zu bereinigende DataFrame. Er wird nicht verändert; die
                Pipeline arbeitet auf einer Kopie.

        Returns:
            Ein Tupel aus dem bereinigten DataFrame und dem zugehörigen
            :class:`~running_data.pipeline.report.CleaningReport`.

        Raises:
            Exception: Wird von einem als kritisch markierten Schritt
                weitergereicht.
            ValueError: Wenn ein kritischer Schritt alle Zeilen entfernt hat.
        """
        self.report.initial_rows = len(df)
        current_df = df.copy()

        logger.info("\n%s", "=" * 60)
        logger.info("Starting Data Cleaning Pipeline: %s", self.source.upper())
        logger.info("Initial rows: %d", len(current_df))
        logger.info("%s\n", "=" * 60)

        for i, step in enumerate(self.steps, 1):
            try:
                logger.info("[%d/%d] Starting: %s", i, len(self.steps), step.name)
                rows_before = len(current_df)

                current_df = step.function(current_df, self.config, self.report)

                self.report.add_step(step.name, rows_before, len(current_df))

                # Ein kritischer Schritt, der alles entfernt, ist immer ein
                # Fehler - auch wenn er technisch erfolgreich durchlief.
                if step.is_critical and len(current_df) == 0:
                    raise ValueError(f"Critical step '{step.name}' removed all data!")

            except Exception as e:
                logger.error("Error in step '%s': %s", step.name, e)
                if step.is_critical:
                    raise
                # Unkritisch: Der Datenstand von vor dem Schritt bleibt
                # erhalten, weil die Zuweisung an current_df nicht erfolgt ist.
                logger.warning("Skipping non-critical step '%s'", step.name)

        self.report.final_rows = len(current_df)
        logger.info("\n%s", "=" * 60)
        logger.info("Pipeline Complete: %s", self.source.upper())
        logger.info("Final rows: %d", len(current_df))
        logger.info("%s\n", "=" * 60)

        return current_df, self.report
