"""Regressionstests für die Apple-spezifische Typisierung."""

import logging

import pandas as pd
import pytest

from running_data.cleaning.apple_typing import clean_apple_typing
from running_data.config import CORE_COLUMNS


def _apple_frame(dates: list[object] | None) -> pd.DataFrame:
    """Erzeugt minimale synthetische Apple-Workouts für Typisierungstests."""
    rows = len(dates) if dates is not None else 2
    data: dict[str, list[object]] = {
        "activity_type": ["HKWorkoutActivityTypeRunning"] * rows,
        "distance": [5.0] * rows,
        "duration": [30.0] * rows,
        "calories": [400.0] * rows,
        "avg_heart_rate": [150.0] * rows,
        "max_heart_rate": [170.0] * rows,
        "source": ["apple"] * rows,
        "export_date": ["2025-08-22"] * rows,
    }
    if dates is not None:
        data["date"] = dates
    return pd.DataFrame(data)


def _typed_dates(dates: list[object] | None) -> pd.Series:
    """Typisiert die synthetischen Workouts und gibt ihre Datumsspalte zurück."""
    return clean_apple_typing(_apple_frame(dates))["date"]


def _typed_measurements(**columns: object) -> pd.DataFrame:
    """Typisiert synthetische Apple-Messwerte mit optionalen Einheiten."""
    lengths = [len(value) for value in columns.values() if isinstance(value, list)]
    rows = max(lengths) if lengths else 1
    frame = _apple_frame(["2025-01-15 07:30:00 +0100"] * rows)

    for name, value in columns.items():
        frame[name] = list(value) if isinstance(value, list) else [value] * rows

    return clean_apple_typing(frame)


class TestAppleZeitstempel:
    """Apple-Ortszeiten werden ohne Offset, aber als echte Zeitstempel geliefert."""

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("2025-01-15 07:30:00 +0100", "2025-01-15 07:30:00"),
            ("2025-07-15 18:45:30 +0200", "2025-07-15 18:45:30"),
            ("2025-03-10 06:15:00", "2025-03-10 06:15:00"),
        ],
        ids=["winter-offset", "summer-offset", "naive"],
    )
    def test_lokale_uhrzeit_bleibt_erhalten(self, raw, expected):
        result = _typed_dates([raw])

        assert result.iloc[0] == pd.Timestamp(expected)
        assert result.dtype == "datetime64[ns]"

    def test_gemischte_offsets_funktionieren_in_einer_spalte(self):
        result = _typed_dates(
            [
                "2025-01-15 07:30:00 +0100",
                "2025-07-15 18:45:30 +0200",
            ]
        )

        expected = pd.Series(
            ["2025-01-15 07:30:00", "2025-07-15 18:45:30"],
            dtype="datetime64[ns]",
            name="date",
        )
        pd.testing.assert_series_equal(result.reset_index(drop=True), expected)

    @pytest.mark.parametrize(
        "raw",
        [
            ["2025-01-15 07:30:00 +0100", "2025-01-16 08:00:00"],
            ["2025-01-16 08:00:00", "2025-01-15 07:30:00 +0100"],
        ],
        ids=["aware-first", "naive-first"],
    )
    def test_aware_und_naive_werte_funktionieren_in_beiden_reihenfolgen(self, raw):
        result = _typed_dates(raw)

        assert result.notna().all()
        assert result.dtype == "datetime64[ns]"

    def test_ungueltige_und_fehlende_werte_werden_nat(self):
        result = _typed_dates(["ungueltig", None, pd.NA])

        assert result.isna().all()
        assert result.dtype == "datetime64[ns]"

    def test_fehlende_datumsspalte_wird_als_nat_ergaenzt(self):
        result = _typed_dates(None)

        assert result.isna().all()
        assert result.dtype == "datetime64[ns]"

    def test_apple_und_garmin_haben_nach_typisierung_denselben_datumstyp(
        self, apple_typed, garmin_typed
    ):
        assert apple_typed["date"].dtype == garmin_typed["date"].dtype


class TestAppleEinheiten:
    """Deklarierte Apple-Einheiten werden zeilenweise sicher normalisiert."""

    def test_xml_import_liefert_deklarierte_einheiten(self, apple_raw):
        unit_columns = [
            "duration_unit",
            "distance_unit",
            "calories_unit",
            "heart_rate_unit",
        ]

        assert set(unit_columns).issubset(apple_raw.columns)
        assert apple_raw.loc[0, unit_columns].to_dict() == {
            "duration_unit": "min",
            "distance_unit": "km",
            "calories_unit": "kcal",
            "heart_rate_unit": "count/min",
        }

    @pytest.mark.parametrize(
        ("value", "unit", "expected_km"),
        [
            (5.0, "km", 5.0),
            (5000.0, "m", 5.0),
            (3.106856, "mi", 5.0),
        ],
        ids=["kilometres", "metres", "miles"],
    )
    def test_distanz_wird_in_kilometer_umgerechnet(
        self, value, unit, expected_km
    ):
        result = _typed_measurements(distance=value, distance_unit=unit)

        assert result.loc[0, "distance_km"] == pytest.approx(expected_km)

    @pytest.mark.parametrize(
        ("value", "unit", "expected_seconds"),
        [(30.0, "min", 1800.0), (1800.0, "s", 1800.0)],
        ids=["minutes", "seconds"],
    )
    def test_dauer_wird_in_sekunden_umgerechnet(
        self, value, unit, expected_seconds
    ):
        result = _typed_measurements(duration=value, duration_unit=unit)

        assert result.loc[0, "duration_sec"] == pytest.approx(expected_seconds)

    @pytest.mark.parametrize(
        ("value", "unit", "expected_kcal"),
        [(100.0, "kcal", 100.0), (418.4, "kJ", 100.0)],
        ids=["kilocalories", "kilojoules"],
    )
    def test_energie_wird_in_kilokalorien_umgerechnet(
        self, value, unit, expected_kcal
    ):
        result = _typed_measurements(calories=value, calories_unit=unit)

        assert result.loc[0, "calories"] == pytest.approx(expected_kcal)

    @pytest.mark.parametrize("unit", ["count/min", "bpm"])
    def test_herzfrequenz_wird_in_bpm_uebernommen(self, unit):
        result = _typed_measurements(
            avg_heart_rate=150.0,
            max_heart_rate=170.0,
            heart_rate_unit=unit,
        )

        assert result.loc[0, "avg_heart_rate"] == pytest.approx(150.0)
        assert result.loc[0, "max_heart_rate"] == pytest.approx(170.0)

    def test_gemischte_einheiten_werden_pro_zeile_umgerechnet(self):
        result = _typed_measurements(
            distance=[5.0, 5000.0],
            distance_unit=["km", "m"],
            duration=[30.0, 1800.0],
            duration_unit=["min", "s"],
        )

        assert result["distance_km"].tolist() == pytest.approx([5.0, 5.0])
        assert result["duration_sec"].tolist() == pytest.approx([1800.0, 1800.0])

    def test_deklarierte_einheiten_uebersteuern_heuristiken(self):
        result = _typed_measurements(
            distance=500.0,
            distance_unit="km",
            duration=30.0,
            duration_unit="s",
        )

        assert result.loc[0, "distance_km"] == pytest.approx(500.0)
        assert result.loc[0, "duration_sec"] == pytest.approx(30.0)

    def test_fehlende_einheiten_nutzen_bestehende_heuristiken(self):
        result = _typed_measurements(distance=5000.0, duration=30.0)

        assert result.loc[0, "distance_km"] == pytest.approx(5.0)
        assert result.loc[0, "duration_sec"] == pytest.approx(1800.0)
        assert result.loc[0, "calories"] == pytest.approx(400.0)
        assert result.loc[0, "avg_heart_rate"] == pytest.approx(150.0)
        assert result.loc[0, "max_heart_rate"] == pytest.approx(170.0)

    def test_leere_einheiten_nutzen_heuristiken_nur_in_betroffener_zeile(self):
        result = _typed_measurements(
            distance=[5.0, 5000.0],
            distance_unit=["km", ""],
            duration=[30.0, 30.0],
            duration_unit=["s", ""],
        )

        assert result["distance_km"].tolist() == pytest.approx([5.0, 5.0])
        assert result["duration_sec"].tolist() == pytest.approx([30.0, 1800.0])

    @pytest.mark.parametrize(
        ("unit_column", "unit", "quantity", "result_columns"),
        [
            ("distance_unit", "yard", "distance", ["distance_km"]),
            ("duration_unit", "hour", "duration", ["duration_sec"]),
            ("calories_unit", "cal", "calories", ["calories"]),
            (
                "heart_rate_unit",
                "Hz",
                "heart_rate",
                ["avg_heart_rate", "max_heart_rate"],
            ),
        ],
        ids=["distance", "duration", "calories", "heart-rate"],
    )
    def test_nicht_unterstuetzte_einheit_wird_verworfen_und_geloggt(
        self,
        caplog,
        unit_column,
        unit,
        quantity,
        result_columns,
    ):
        with caplog.at_level(
            logging.WARNING, logger="running_data.cleaning.apple_typing"
        ):
            result = _typed_measurements(**{unit_column: [unit, unit]})

        assert result[result_columns].isna().all().all()
        assert caplog.messages == [
            f"Apple: Einheit '{unit}' für {quantity} nicht unterstützt; "
            "2 Wert(e) auf NaN gesetzt"
        ]

    def test_einheitenspalten_bleiben_ausserhalb_des_zielschema(self):
        result = _typed_measurements(
            duration_unit="min",
            distance_unit="km",
            calories_unit="kcal",
            heart_rate_unit="count/min",
        )

        assert result.columns.tolist() == CORE_COLUMNS
