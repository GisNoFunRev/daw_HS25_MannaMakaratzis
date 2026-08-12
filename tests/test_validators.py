"""Tests der Plausibilitätsregeln (running_data.cleaning.validators).

Vom Bewertungsraster ausdrücklich verlangt.

Alle Regeln arbeiten mit pandas.Series.between(inclusive="both"), die
Grenzwerte gehören also noch zum gültigen Bereich. Jeder Test prüft deshalb
vier Punkte: knapp darunter, genau auf der Grenze, innerhalb, und knapp
darüber. Die Grenzwerte werden aus der Konfiguration gelesen statt als Zahlen
hingeschrieben — sonst prüft der Test nur, ob jemand zwei Dateien gleichzeitig
geändert hat.
"""

import numpy as np
import pytest

from running_data.cleaning.validators import DataValidator


class TestValidateDistance:
    """Distanz: DISTANCE_MIN bis DISTANCE_MAX Kilometer."""

    def test_grenzwerte(self, make_runs, config):
        werte = [
            config.DISTANCE_MIN - 0.01,  # knapp darunter
            config.DISTANCE_MIN,  # genau auf der Untergrenze
            (config.DISTANCE_MIN + config.DISTANCE_MAX) / 2,  # mittendrin
            config.DISTANCE_MAX,  # genau auf der Obergrenze
            config.DISTANCE_MAX + 0.01,  # knapp darüber
        ]
        df = make_runs(distance_km=werte)

        maske = DataValidator.validate_distance(df, config)

        assert maske.tolist() == [False, True, True, True, False]

    def test_fehlender_wert_gilt_als_unplausibel(self, make_runs, config):
        df = make_runs(distance_km=[np.nan])

        assert DataValidator.validate_distance(df, config).tolist() == [False]

    def test_negative_distanz(self, make_runs, config):
        df = make_runs(distance_km=[-5.0])

        assert DataValidator.validate_distance(df, config).tolist() == [False]


class TestValidateDuration:
    """Dauer: DURATION_MIN bis DURATION_MAX Sekunden."""

    def test_grenzwerte(self, make_runs, config):
        werte = [
            config.DURATION_MIN - 1,
            config.DURATION_MIN,
            3600,
            config.DURATION_MAX,
            config.DURATION_MAX + 1,
        ]
        df = make_runs(duration_sec=werte)

        maske = DataValidator.validate_duration(df, config)

        assert maske.tolist() == [False, True, True, True, False]

    def test_fehlender_wert_gilt_als_unplausibel(self, make_runs, config):
        df = make_runs(duration_sec=[np.nan])

        assert DataValidator.validate_duration(df, config).tolist() == [False]


class TestValidatePace:
    """Pace: abgeleitet aus Dauer und Distanz, PACE_MIN bis PACE_MAX min/km."""

    @staticmethod
    def _sekunden_fuer(pace_min_pro_km: float, distanz_km: float) -> float:
        """Rechnet eine gewünschte Pace in die zugehörige Dauer um."""
        return pace_min_pro_km * distanz_km * 60

    @pytest.mark.parametrize(
        "abweichung, erwartet",
        [
            (-0.01, False),  # knapp schneller als der Weltrekordbereich
            (0.0, True),  # genau auf der Untergrenze
        ],
    )
    def test_untergrenze(self, make_runs, config, abweichung, erwartet):
        pace = config.PACE_MIN + abweichung
        df = make_runs(distance_km=[10.0], duration_sec=[self._sekunden_fuer(pace, 10.0)])

        assert DataValidator.validate_pace(df, config).tolist() == [erwartet]

    @pytest.mark.parametrize(
        "abweichung, erwartet",
        [
            (0.0, True),  # genau auf der Obergrenze
            (0.01, False),  # knapp langsamer als schnelles Gehen
        ],
    )
    def test_obergrenze(self, make_runs, config, abweichung, erwartet):
        pace = config.PACE_MAX + abweichung
        df = make_runs(distance_km=[10.0], duration_sec=[self._sekunden_fuer(pace, 10.0)])

        assert DataValidator.validate_pace(df, config).tolist() == [erwartet]

    def test_faengt_unmoegliche_kombination_ab(self, make_runs, config):
        """20 km in 45 Minuten.

        Der eigentliche Zweck dieser Regel: Distanz und Dauer sind einzeln
        betrachtet völlig plausibel, die Kombination ergibt aber eine Pace von
        2.25 min/km und damit deutlich über Weltrekordniveau.
        """
        df = make_runs(distance_km=[20.0], duration_sec=[45 * 60])

        assert DataValidator.validate_distance(df, config).tolist() == [True]
        assert DataValidator.validate_duration(df, config).tolist() == [True]
        assert DataValidator.validate_pace(df, config).tolist() == [False]


class TestValidateHeartRate:
    """Durchschnittliche Herzfrequenz: HR_MIN bis HR_MAX bpm."""

    def test_grenzwerte(self, make_runs, config):
        werte = [
            config.HR_MIN - 1,
            config.HR_MIN,
            150,
            config.HR_MAX,
            config.HR_MAX + 1,
        ]
        df = make_runs(avg_heart_rate=werte)

        maske = DataValidator.validate_heart_rate(df, config)

        assert maske.tolist() == [False, True, True, True, False]

    def test_fehlender_wert_gilt_als_unplausibel(self, make_runs, config):
        df = make_runs(avg_heart_rate=[np.nan])

        assert DataValidator.validate_heart_rate(df, config).tolist() == [False]


class TestValidateHrConsistency:
    """Konsistenzregel max_heart_rate >= avg_heart_rate."""

    def test_maximum_ueber_durchschnitt_ist_unauffaellig(self, make_runs, config):
        df = make_runs(avg_heart_rate=[150.0], max_heart_rate=[170.0])

        pruefung = DataValidator.validate_hr_consistency(df, config)

        assert pruefung["inverted_mask"].tolist() == [False]
        assert pruefung["conflict_mask"].tolist() == [False]

    def test_gleichstand_ist_kein_widerspruch(self, make_runs, config):
        df = make_runs(avg_heart_rate=[150.0], max_heart_rate=[150.0])

        pruefung = DataValidator.validate_hr_consistency(df, config)

        assert pruefung["inverted_mask"].tolist() == [False]

    def test_innerhalb_der_toleranz_gilt_als_rundungsfehler(self, make_runs, config):
        """Genau HR_CONSISTENCY_TOLERANCE Schläge Unterschied — noch korrigierbar."""
        df = make_runs(
            avg_heart_rate=[150.0],
            max_heart_rate=[150.0 - config.HR_CONSISTENCY_TOLERANCE],
        )

        pruefung = DataValidator.validate_hr_consistency(df, config)

        assert pruefung["inverted_mask"].tolist() == [True]
        assert pruefung["tolerance_mask"].tolist() == [True]
        assert pruefung["conflict_mask"].tolist() == [False]

    def test_ausserhalb_der_toleranz_ist_echter_widerspruch(self, make_runs, config):
        """Ein Schlag mehr als die Toleranz — beide Werte sind unglaubwürdig."""
        df = make_runs(
            avg_heart_rate=[150.0],
            max_heart_rate=[150.0 - config.HR_CONSISTENCY_TOLERANCE - 1],
        )

        pruefung = DataValidator.validate_hr_consistency(df, config)

        assert pruefung["inverted_mask"].tolist() == [True]
        assert pruefung["tolerance_mask"].tolist() == [False]
        assert pruefung["conflict_mask"].tolist() == [True]

    @pytest.mark.parametrize("fehlend", ["avg_heart_rate", "max_heart_rate"])
    def test_fehlender_wert_erzeugt_keinen_widerspruch(
        self, make_runs, config, fehlend
    ):
        """Ohne beide Werte lässt sich die Regel nicht anwenden.

        Wichtig, weil ein fälschlich als Widerspruch gewerteter fehlender Wert
        in step_clean_heart_rate dazu führen würde, den jeweils anderen,
        vorhandenen Wert ebenfalls zu verwerfen.
        """
        df = make_runs(**{fehlend: [np.nan]})

        pruefung = DataValidator.validate_hr_consistency(df, config)

        assert pruefung["inverted_mask"].tolist() == [False]
        assert pruefung["conflict_mask"].tolist() == [False]
