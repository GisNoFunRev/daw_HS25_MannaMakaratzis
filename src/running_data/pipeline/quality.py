"""Automatisierte Datenqualitäts-Metriken.

Bewertet einen bereinigten Datensatz anhand von vier etablierten Data Quality
Dimensions. Definition siehe
https://dqops.com/docs/dqo-concepts/data-quality-dimensions/

    Dimension      Berechnung                            Aussage
    -------------  ------------------------------------  ---------------------
    Completeness   1 - NaN-Anteil je Spalte              Wie vollständig?
    Validity       Anteil plausibler Werte               Wie realistisch?
    Consistency    Logik zwischen Variablen (max >= avg) Wie widerspruchsfrei?
    Uniqueness     1 - Duplikatanteil                    Wie eindeutig?

Wichtige Einschränkung
----------------------
Completeness misst ausschliesslich, ob ein Wert vorhanden ist — nicht, ob er
richtig ist. Ein Feld, das zu 100 % gefüllt ist, kann durchgehend falsche
Werte enthalten und wird hier trotzdem mit ✅ ausgewiesen. Genau dieser Fall
liegt beim Garmin-Datumsfeld vor (TODO 1): Die Werte sind vollständig, aber
Tag und Monat sind vertauscht. Die Metrik ersetzt daher keine fachliche
Plausibilisierung.
"""

import numpy as np
import pandas as pd

from ..config import DUPLICATE_KEY_COLUMNS, DataCleaningConfig
from ..cleaning.validators import DataValidator

# Schwellen für die Statusanzeige im Qualitätsbericht.
STATUS_GOOD_THRESHOLD = 0.95
STATUS_WARNING_THRESHOLD = 0.85


class DataQualityChecker:
    """Berechnet und formatiert Qualitätsmetriken eines Datensatzes."""

    @staticmethod
    def assess_quality(df: pd.DataFrame, config: DataCleaningConfig) -> dict:
        """Ermittelt die Metriken aller vier Qualitätsdimensionen.

        Die Prüfungen sind gegen fehlende Spalten abgesichert, damit die
        Funktion auch auf Teildatensätzen läuft.

        Args:
            df: Der zu bewertende, bereits bereinigte DataFrame.
            config: Schwellenwerte für die Plausibilitätsprüfungen.

        Returns:
            Verschachteltes Dictionary mit total_rows sowie je einem
            Unter-Dictionary pro Dimension.
        """
        metrics: dict = {
            "total_rows": len(df),
            "completeness": {},
            "validity": {},
            "consistency": {},
            "uniqueness": {},
        }

        # --- Completeness: Anteil nicht-fehlender Werte je Spalte -----------
        for col in df.columns:
            metrics["completeness"][col] = 1 - (df[col].isna().sum() / len(df))

        # --- Validity: Anteil plausibler Werte ------------------------------
        validator = DataValidator()

        if "distance_km" in df.columns and "duration_sec" in df.columns:
            metrics["validity"]["distance"] = validator.validate_distance(
                df, config
            ).mean()
            metrics["validity"]["duration"] = validator.validate_duration(
                df, config
            ).mean()
            metrics["validity"]["pace"] = validator.validate_pace(df, config).mean()

        if "avg_heart_rate" in df.columns:
            metrics["validity"]["hr"] = validator.validate_heart_rate(df, config).mean()

        # --- Consistency: max_hr darf nicht unter avg_hr liegen -------------
        if "max_heart_rate" in df.columns and "avg_heart_rate" in df.columns:
            hr_check = validator.validate_hr_consistency(df, config)
            metrics["consistency"]["hr_max_vs_avg"] = 1 - (
                hr_check["conflict_mask"].sum() / len(df)
            )

        # --- Uniqueness: keine doppelten Läufe ------------------------------
        if all(col in df.columns for col in DUPLICATE_KEY_COLUMNS):
            metrics["uniqueness"]["workouts"] = 1 - (
                df.duplicated(subset=DUPLICATE_KEY_COLUMNS).sum() / len(df)
            )

        return metrics

    @staticmethod
    def quality_report(metrics: dict) -> pd.DataFrame:
        """Formatiert die Metriken als Tabelle mit Statusindikator.

        Args:
            metrics: Rückgabewert von assess_quality.

        Returns:
            DataFrame mit den Spalten category, metric, value und
            status (✅ ab 95 %, ⚠️ ab 85 %, sonst ❌).
        """
        records = []

        for category, values in metrics.items():
            # total_rows ist eine Zahl, keine Dimension - überspringen.
            if not isinstance(values, dict):
                continue

            for key, value in values.items():
                records.append(
                    {
                        "category": category,
                        "metric": key,
                        "value": value,
                        "status": _status_indicator(value),
                    }
                )

        return pd.DataFrame(records)


def _status_indicator(value: float) -> str:
    """Übersetzt einen Metrikwert in ein Ampelsymbol."""
    if value >= STATUS_GOOD_THRESHOLD:
        return "✅"
    if value >= STATUS_WARNING_THRESHOLD:
        return "⚠️"
    return "❌"


def build_comparison_table(
    summaries: dict[str, dict], qualities: dict[str, dict]
) -> pd.DataFrame:
    """Stellt die Bereinigungsergebnisse mehrerer Quellen gegenüber.

    Ersetzt den zuvor fest auf Garmin und Apple verdrahteten Vergleichsblock
    im Notebook (qmd:1556-1589). Die Quellen werden jetzt aus den übergebenen
    Dictionaries abgeleitet, sodass eine dritte Quelle keine Codeänderung
    erfordert.

    Args:
        summaries: Je Quellenname das Ergebnis von
            summary.
        qualities: Je Quellenname das Ergebnis von
            DataQualityChecker.assess_quality. Muss dieselben
            Schlüssel wie summaries haben.

    Returns:
        DataFrame mit der Spalte Metrik und je einer Spalte pro Quelle.
    """
    if summaries.keys() != qualities.keys():
        raise ValueError(
            "summaries und qualities muessen dieselben Quellen enthalten: "
            f"{sorted(summaries)} vs. {sorted(qualities)}"
        )

    table: dict[str, list] = {
        "Metrik": [
            "Initial Rows",
            "Final Rows",
            "Removed Rows",
            "Retention Rate (%)",
            "Completeness (avg)",
            "Validity (avg)",
        ]
    }

    for source, summary in summaries.items():
        quality = qualities[source]
        table[source] = [
            summary["initial_rows"],
            summary["final_rows"],
            summary["total_removed"],
            f"{summary['retention_rate'] * 100:.1f}%",
            f"{np.mean(list(quality['completeness'].values())) * 100:.1f}%",
            f"{np.mean(list(quality['validity'].values())) * 100:.1f}%",
        ]

    return pd.DataFrame(table)
