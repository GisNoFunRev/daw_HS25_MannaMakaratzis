"""Validierungsregeln für Laufdaten.

Alle Prüfungen folgen demselben Prinzip: Sie geben eine **boolesche Maske**
zurück und verändern die Daten nicht. Ob eine als unplausibel erkannte Zeile
entfernt, korrigiert oder nur gezählt wird, entscheidet der aufrufende
Bereinigungsschritt.

Diese Trennung hat zwei Vorteile: Dieselbe Regel lässt sich sowohl zum
Filtern (:mod:`running_data.cleaning.steps`) als auch zum Messen
(:mod:`running_data.pipeline.quality`) verwenden, und jede Regel ist für sich
testbar, ohne dass ein DataFrame verändert werden muss.

Alle Grenzwerte stammen aus :class:`~running_data.config.DataCleaningConfig`
und sind bewusst nicht hier hinterlegt.
"""

import pandas as pd

from ..config import DataCleaningConfig


class DataValidator:
    """Sammlung der Plausibilitätsregeln für einen Laufdatensatz.

    Die Methoden sind statisch: Sie halten keinen Zustand, sondern erhalten
    Daten und Konfiguration bei jedem Aufruf. Die Klasse dient allein der
    thematischen Bündelung.
    """

    @staticmethod
    def validate_distance(
        df: pd.DataFrame, config: DataCleaningConfig
    ) -> pd.Series:
        """Prüft die Distanz auf einen realistischen Bereich.

        Returns:
            Boolesche Maske; ``True`` bedeutet plausible Distanz.
        """
        return df["distance_km"].between(
            config.DISTANCE_MIN, config.DISTANCE_MAX, inclusive="both"
        )

    @staticmethod
    def validate_duration(
        df: pd.DataFrame, config: DataCleaningConfig
    ) -> pd.Series:
        """Prüft die Dauer auf einen realistischen Bereich.

        Returns:
            Boolesche Maske; ``True`` bedeutet plausible Dauer.
        """
        return df["duration_sec"].between(
            config.DURATION_MIN, config.DURATION_MAX, inclusive="both"
        )

    @staticmethod
    def validate_pace(df: pd.DataFrame, config: DataCleaningConfig) -> pd.Series:
        """Prüft die aus Dauer und Distanz abgeleitete Pace (min/km).

        Diese Regel fängt Fälle ab, die einzeln betrachtet unauffällig sind:
        20 km und 45 Minuten sind je für sich plausibel, in Kombination aber
        nicht.

        Returns:
            Boolesche Maske; ``True`` bedeutet plausible Pace.
        """
        pace = (df["duration_sec"] / 60.0) / df["distance_km"]
        return pace.between(config.PACE_MIN, config.PACE_MAX, inclusive="both")

    @staticmethod
    def validate_heart_rate(
        df: pd.DataFrame, config: DataCleaningConfig
    ) -> pd.Series:
        """Prüft die durchschnittliche Herzfrequenz auf physiologische Grenzen.

        Returns:
            Boolesche Maske; ``True`` bedeutet plausible Herzfrequenz.
        """
        return df["avg_heart_rate"].between(
            config.HR_MIN, config.HR_MAX, inclusive="both"
        )

    @staticmethod
    def validate_hr_consistency(
        df: pd.DataFrame, config: DataCleaningConfig
    ) -> dict[str, pd.Series]:
        """Prüft die Konsistenzregel ``max_heart_rate >= avg_heart_rate``.

        Eine Verletzung dieser Regel hat zwei mögliche Ursachen, die
        unterschiedlich behandelt werden müssen: Liegt der Unterschied im
        Bereich der Rundungstoleranz, handelt es sich um einen
        Darstellungsfehler und der Wert lässt sich korrigieren. Ist er
        grösser, sind beide Werte unglaubwürdig.

        Returns:
            Dictionary mit drei Masken:

            ``inverted_mask``
                Alle Zeilen mit ``max < avg``.
            ``tolerance_mask``
                Davon jene innerhalb der Rundungstoleranz — korrigierbar.
            ``conflict_mask``
                Die übrigen — echte Widersprüche.
        """
        inverted = (
            df["max_heart_rate"].notna()
            & df["avg_heart_rate"].notna()
            & (df["max_heart_rate"] < df["avg_heart_rate"])
        )

        tolerance = inverted & (
            (df["avg_heart_rate"] - df["max_heart_rate"])
            <= config.HR_CONSISTENCY_TOLERANCE
        )

        return {
            "inverted_mask": inverted,
            "tolerance_mask": tolerance,
            "conflict_mask": inverted & ~tolerance,
        }
