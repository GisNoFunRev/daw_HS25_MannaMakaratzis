"""Tests für die abgeleiteten Laufvariablen."""

import pandas as pd
import pytest

from running_data.features import add_features


def _runs(**columns: object) -> pd.DataFrame:
    """Erzeugt minimale bereinigte Läufe für Feature-Tests."""
    data: dict[str, object] = {
        "duration_sec": [1800.0, 3600.0],
        "distance_km": [5.0, 10.0],
        "source": ["garmin", "apple"],
    }
    data.update(columns)
    return pd.DataFrame(data)


def test_berechnet_dauer_und_pace_in_den_dokumentierten_einheiten():
    result = add_features(_runs())

    assert result["duration_min"].tolist() == pytest.approx([30.0, 60.0])
    assert result["pace_min_per_km"].tolist() == pytest.approx([6.0, 6.0])


def test_eingabe_bleibt_unveraendert():
    runs = _runs()
    before = runs.copy(deep=True)

    result = add_features(runs)

    pd.testing.assert_frame_equal(runs, before)
    pd.testing.assert_frame_equal(result[before.columns], before)


def test_null_distanz_ergibt_fehlende_pace_statt_unendlich():
    result = add_features(
        _runs(duration_sec=[600.0, 0.0], distance_km=[0.0, 0.0])
    )

    assert result["pace_min_per_km"].isna().all()
