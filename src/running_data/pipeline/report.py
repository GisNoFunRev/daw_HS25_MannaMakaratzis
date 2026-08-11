"""Bereinigungsbericht (Audit Trail der Pipeline).

Der Bericht beantwortet die Frage, die bei jeder Datenbereinigung als erstes
gestellt wird: *Wie viele Zeilen sind wo verloren gegangen und warum?*

Jeder Pipeline-Schritt meldet über CleaningReport.add_step, wie viele
Zeilen er vorgefunden und wie viele er zurückgegeben hat. Daraus entsteht eine
lückenlose Kette vom Rohdatensatz bis zum Ergebnis.
"""

from typing import Any

import pandas as pd

from ..logging_setup import get_logger

logger = get_logger(__name__)


class CleaningReport:
    """Sammelt die Schritt-für-Schritt-Statistik eines Pipeline-Laufs.

    Attributes:
        source: Name der Datenquelle, z. B. "Garmin".
        steps: Ein Eintrag je ausgeführtem Schritt.
        initial_rows: Zeilenzahl vor dem ersten Schritt.
        final_rows: Zeilenzahl nach dem letzten Schritt.
    """

    def __init__(self, source: str) -> None:
        self.source = source
        self.steps: list[dict[str, Any]] = []
        self.initial_rows: int = 0
        self.final_rows: int = 0

    def add_step(
        self, step_name: str, rows_before: int, rows_after: int, **kwargs: Any
    ) -> None:
        """Dokumentiert einen abgeschlossenen Bereinigungsschritt.

        Args:
            step_name: Name des Schritts, wie er im Bericht erscheint.
            rows_before: Zeilenzahl vor dem Schritt.
            rows_after: Zeilenzahl nach dem Schritt.
            **kwargs: Zusätzliche Kennzahlen, die im Bericht mitgeführt werden.
        """
        removed = rows_before - rows_after
        self.steps.append(
            {
                "step": step_name,
                "rows_before": rows_before,
                "rows_after": rows_after,
                "removed": removed,
                "removal_rate": removed / rows_before if rows_before > 0 else 0,
                **kwargs,
            }
        )
        logger.info(
            "%s | %s: %d → %d (-%d, %.1f%%)",
            self.source,
            step_name,
            rows_before,
            rows_after,
            removed,
            removed / rows_before * 100,
        )

    def to_dataframe(self) -> pd.DataFrame:
        """Gibt die Schritt-Statistik als DataFrame zurück (für die Anzeige)."""
        return pd.DataFrame(self.steps)

    def summary(self) -> dict[str, Any]:
        """Fasst den Lauf zusammen und protokolliert die Zusammenfassung.

        Returns:
            Kennzahlen des Laufs: source, initial_rows,
            final_rows, total_removed und retention_rate.
        """
        total_removed = self.initial_rows - self.final_rows
        retention_rate = (
            self.final_rows / self.initial_rows if self.initial_rows > 0 else 0
        )

        logger.info(
            "\n%s\nDATA CLEANING SUMMARY: %s\n%s\n"
            "Initial rows:     %6d\n"
            "Final rows:       %6d\n"
            "Total removed:    %6d (%.1f%%)\n"
            "Retention rate:   %.1f%%\n%s",
            "=" * 60,
            self.source.upper(),
            "=" * 60,
            self.initial_rows,
            self.final_rows,
            total_removed,
            (1 - retention_rate) * 100,
            retention_rate * 100,
            "=" * 60,
        )

        return {
            "source": self.source,
            "initial_rows": self.initial_rows,
            "final_rows": self.final_rows,
            "total_removed": total_removed,
            "retention_rate": retention_rate,
        }
