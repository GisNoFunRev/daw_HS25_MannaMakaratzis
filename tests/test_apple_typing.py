"""Regressionstests für die Apple-spezifische Typisierung."""

import pandas as pd
import pytest

from running_data.cleaning.apple_typing import clean_apple_typing


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
