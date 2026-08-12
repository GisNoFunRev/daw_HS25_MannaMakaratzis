"""Tests der Datenqualitäts-Metriken (running_data.pipeline.quality)."""

import numpy as np
import pandas as pd
import pytest

from running_data.config import PROVENANCE_COLUMNS
from running_data.pipeline.quality import (
    STATUS_GOOD_THRESHOLD,
    STATUS_WARNING_THRESHOLD,
    DataQualityChecker,
    _status_indicator,
    build_comparison_table,
)


class TestCompleteness:
    """Anteil vorhandener Werte je Spalte."""

    def test_vollstaendige_spalte_ergibt_eins(self, make_runs, config):
        df = make_runs(distance_km=[5.0, 6.0])

        metriken = DataQualityChecker.assess_quality(df, config)

        assert metriken["completeness"]["distance_km"] == 1.0

    def test_haelfte_fehlt(self, make_runs, config):
        df = make_runs(calories=[400.0, np.nan])

        metriken = DataQualityChecker.assess_quality(df, config)

        assert metriken["completeness"]["calories"] == 0.5

    @pytest.mark.parametrize("spalte", PROVENANCE_COLUMNS)
    def test_herkunftsspalten_werden_nicht_bewertet(self, make_runs, config, spalte):
        """Regressionstest zur Completeness-Korrektur.

        Ein leeres imputation_level bedeutet "musste nicht imputiert werden"
        und damit den Idealfall. Solange die Spalte mitgezählt wurde, bekam
        ausgerechnet die Quelle ohne jede Imputation den Wert 0.0 und ein
        rotes X.
        """
        df = make_runs(distance_km=[5.0, 6.0])
        df[spalte] = [None, None]

        metriken = DataQualityChecker.assess_quality(df, config)

        assert spalte not in metriken["completeness"]

    def test_ohne_herkunftsspalten_bleibt_der_mittelwert_sauber(
        self, make_runs, config
    ):
        """Der Mittelwert darf nicht durch nicht bewertbare Spalten sinken."""
        df = make_runs(distance_km=[5.0, 6.0])
        df["imputation_level"] = [None, None]
        df["calories_imputed"] = [False, False]

        metriken = DataQualityChecker.assess_quality(df, config)
        werte = list(metriken["completeness"].values())

        assert np.mean(werte) == 1.0


class TestWeitereDimensionen:
    """Validity, Consistency und Uniqueness."""

    def test_validity_erfasst_alle_vier_regeln(self, make_runs, config):
        metriken = DataQualityChecker.assess_quality(make_runs(), config)

        assert set(metriken["validity"]) == {"distance", "duration", "pace", "hr"}

    def test_validity_zaehlt_unplausible_zeilen(self, make_runs, config):
        """Eine von zwei Distanzen liegt ausserhalb des gültigen Bereichs."""
        df = make_runs(distance_km=[5.0, 999.0])

        metriken = DataQualityChecker.assess_quality(df, config)

        assert metriken["validity"]["distance"] == 0.5

    def test_consistency_erkennt_widerspruch(self, make_runs, config):
        """max unter avg, ausserhalb der Rundungstoleranz."""
        df = make_runs(
            avg_heart_rate=[150.0, 150.0], max_heart_rate=[170.0, 100.0]
        )

        metriken = DataQualityChecker.assess_quality(df, config)

        assert metriken["consistency"]["hr_max_vs_avg"] == 0.5

    def test_uniqueness_erkennt_duplikate(self, make_runs, config):
        """Gleiche Quelle, Zeit, Distanz und Dauer — derselbe Lauf zweimal."""
        df = make_runs(n=2)

        metriken = DataQualityChecker.assess_quality(df, config)

        assert metriken["uniqueness"]["workouts"] == 0.5

    def test_uniqueness_ohne_duplikate(self, make_runs, config):
        df = make_runs(distance_km=[5.0, 6.0])

        metriken = DataQualityChecker.assess_quality(df, config)

        assert metriken["uniqueness"]["workouts"] == 1.0

    def test_fehlende_spalten_fuehren_nicht_zum_absturz(self, config):
        """Die Prüfungen sind laut Docstring gegen Teildatensätze abgesichert."""
        df = pd.DataFrame({"date": pd.to_datetime(["2025-01-01"])})

        metriken = DataQualityChecker.assess_quality(df, config)

        assert metriken["validity"] == {}
        assert metriken["consistency"] == {}
        assert metriken["uniqueness"] == {}


class TestStatusIndikator:
    """Die Ampel: ✅ ab 95 %, ⚠️ ab 85 %, sonst ❌."""

    @pytest.mark.parametrize(
        "wert, erwartet",
        [
            (1.0, "✅"),
            (STATUS_GOOD_THRESHOLD, "✅"),
            (STATUS_GOOD_THRESHOLD - 0.01, "⚠️"),
            (STATUS_WARNING_THRESHOLD, "⚠️"),
            (STATUS_WARNING_THRESHOLD - 0.01, "❌"),
            (0.0, "❌"),
        ],
    )
    def test_schwellenwerte(self, wert, erwartet):
        assert _status_indicator(wert) == erwartet


class TestQualityReport:
    """Aufbereitung der Metriken als Tabelle."""

    def test_spalten(self, make_runs, config):
        metriken = DataQualityChecker.assess_quality(make_runs(), config)

        bericht = DataQualityChecker.quality_report(metriken)

        assert list(bericht.columns) == ["category", "metric", "value", "status"]

    def test_total_rows_ist_keine_metrik(self, make_runs, config):
        """total_rows ist eine Zahl, keine Dimension, und wird übersprungen."""
        metriken = DataQualityChecker.assess_quality(make_runs(), config)

        bericht = DataQualityChecker.quality_report(metriken)

        assert "total_rows" not in bericht["category"].tolist()

    def test_enthaelt_alle_vier_dimensionen(self, make_runs, config):
        metriken = DataQualityChecker.assess_quality(make_runs(), config)

        bericht = DataQualityChecker.quality_report(metriken)

        assert set(bericht["category"]) == {
            "completeness",
            "validity",
            "consistency",
            "uniqueness",
        }


class TestBuildComparisonTable:
    """Gegenüberstellung mehrerer Quellen."""

    @staticmethod
    def _zusammenfassung(zeilen: int) -> dict:
        return {
            "source": "X",
            "initial_rows": zeilen,
            "final_rows": zeilen,
            "total_removed": 0,
            "retention_rate": 1.0,
        }

    @staticmethod
    def _qualitaet() -> dict:
        return {"completeness": {"a": 1.0}, "validity": {"b": 1.0}}

    def test_je_quelle_eine_spalte(self):
        tabelle = build_comparison_table(
            {"Garmin": self._zusammenfassung(13), "Apple": self._zusammenfassung(11)},
            {"Garmin": self._qualitaet(), "Apple": self._qualitaet()},
        )

        assert list(tabelle.columns) == ["Metrik", "Garmin", "Apple"]

    def test_dritte_quelle_erfordert_keine_codeaenderung(self):
        """Der Grund, warum der fest verdrahtete Block ersetzt wurde."""
        quellen = ["Garmin", "Apple", "Polar"]

        tabelle = build_comparison_table(
            {q: self._zusammenfassung(10) for q in quellen},
            {q: self._qualitaet() for q in quellen},
        )

        assert list(tabelle.columns) == ["Metrik", *quellen]

    def test_uneinheitliche_quellen_werden_abgelehnt(self):
        """Sonst entstünde stillschweigend eine Tabelle mit falschen Zahlen."""
        with pytest.raises(ValueError, match="dieselben Quellen"):
            build_comparison_table(
                {"Garmin": self._zusammenfassung(13)},
                {"Apple": self._qualitaet()},
            )
