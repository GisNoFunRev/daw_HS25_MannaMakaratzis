"""Tests der Garmin-Typisierung (running_data.cleaning.garmin_typing).

Enthält den vom Bewertungsraster verlangten Regressionstest für den
Datums-Parsing-Bug (TODO 1).
"""

import numpy as np
import pandas as pd
import pytest

from running_data.config import CORE_COLUMNS, RAW_CORE_COLUMNS
from running_data.cleaning.garmin_typing import (
    clean_garmin_typing,
    convert_duration_to_seconds,
    filter_running,
    reduce_to_core_columns,
)


def _raw_garmin(dates: list[str]) -> pd.DataFrame:
    """Baut einen Garmin-Datensatz im Rohschema RAW_CORE_COLUMNS.

    Die Typisierung erwartet die Rohspalte "duration" als Text, nicht das
    bereits harmonisierte "duration_sec" — deshalb ein eigener Konstrukteur
    statt der make_runs-Fixture.
    """
    n = len(dates)
    return pd.DataFrame(
        {
            "date": dates,
            "activity_type": ["Running"] * n,
            "distance_km": [5.0] * n,
            "duration": ["00:30:00"] * n,
            "calories": [400] * n,
            "avg_heart_rate": [150] * n,
            "max_heart_rate": [170] * n,
            "source": ["garmin"] * n,
            "export_date": ["2025-08-22"] * n,
        }
    )


class TestDatumsRegression:
    """Regressionstest zum Garmin-Datums-Bug (TODO 1).

    Garmin liefert Datumswerte im europäischen Format TT.MM.JJJJ HH:MM.
    Ohne explizite Formatangabe interpretierte pandas sie als MM.TT.JJJJ.
    Die Folge war zweigeteilt und beide Hälften waren tückisch:

    * Tag <= 12: Tag und Monat wurden vertauscht. Der 11. Juli wurde zum
      7. November — ein gültiges Datum, das niemandem auffiel.
    * Tag > 12: Es entstand NaT. Diese Zeilen bekamen anschliessend in
      step_impute_dates alle dasselbe Exportdatum zugewiesen.

    Der Qualitätsbericht meldete trotzdem completeness = 100 %, weil er nur
    auf fehlende Werte prüft. Genau deshalb braucht es diesen Test.
    """

    @pytest.mark.parametrize(
        "roh, jahr, monat, tag, stunde, minute",
        [
            # Der dokumentierte Fall aus TODO 1: wurde zum 7. November.
            ("11.07.2025 16:58", 2025, 7, 11, 16, 58),
            # Zweiter dokumentierter Fall: wurde zum 7. April.
            ("04.07.2025 21:06", 2025, 7, 4, 21, 6),
            # Tag > 12: ergab zuvor NaT.
            ("22.08.2025 07:15", 2025, 8, 22, 7, 15),
            # Grenzfall Monatsende und zweistelliger Monat.
            ("31.12.2024 23:59", 2024, 12, 31, 23, 59),
            # Grenzfall: Tag und Monat identisch, kann nicht vertauscht werden.
            ("05.05.2025 05:05", 2025, 5, 5, 5, 5),
        ],
    )
    def test_tag_und_monat_werden_nicht_vertauscht(
        self, roh, jahr, monat, tag, stunde, minute
    ):
        ergebnis = clean_garmin_typing(_raw_garmin([roh]))["date"].iloc[0]

        assert ergebnis == pd.Timestamp(jahr, monat, tag, stunde, minute), (
            f"{roh!r} wurde zu {ergebnis} statt zum {tag}.{monat}.{jahr}"
        )

    def test_gemischte_spalte_wie_im_echten_export(self):
        """Der eigentliche Regressionsfall — und der einzige vollständige.

        pandas leitet das Datumsformat aus dem ersten Element ab und wendet
        es auf die gesamte Spalte an. Das hat zwei Konsequenzen:

        * Steht vorne ein Tag <= 12, wird MM.TT.JJJJ angenommen. Alle
          späteren Zeilen mit Tag > 12 werden dann zu NaT.
        * Ein Test, der jeden Wert einzeln parst, bemerkt das nicht: Bei
          einem alleinstehenden "22.08.2025" erkennt pandas selbst, dass 22
          kein Monat sein kann, und trifft zufällig das Richtige.

        Dieser Test bildet deshalb bewusst eine gemischte Spalte in der
        Reihenfolge des echten Exports ab.
        """
        dates = [
            "11.07.2025 16:58",  # Tag <= 12: bestimmt die Formatvermutung
            "04.07.2025 21:06",  # Tag <= 12: wurde vertauscht
            "22.08.2025 07:15",  # Tag > 12: wurde dadurch zu NaT
            "31.12.2024 23:59",  # Tag > 12: wurde dadurch zu NaT
        ]

        ergebnis = clean_garmin_typing(_raw_garmin(dates))["date"]

        assert ergebnis.notna().all(), f"NaT entstanden: {ergebnis.tolist()}"
        assert ergebnis.dt.day.tolist() == [11, 4, 22, 31]
        assert ergebnis.dt.month.tolist() == [7, 7, 8, 12]

    def test_fixture_datumswerte_stimmen(self, garmin_typed):
        """Derselbe Nachweis auf dem Weg über eine echte CSV-Datei.

        Die Fixture enthält bewusst je einen Fall mit Tag <= 12 und Tag > 12.
        """
        nach_datum = garmin_typed.sort_values("date")["date"]

        assert nach_datum.notna().all()
        assert pd.Timestamp("2025-07-11 16:58") in nach_datum.tolist()
        assert pd.Timestamp("2025-08-22 07:15") in nach_datum.tolist()

    def test_unparsbares_datum_wird_nat(self):
        """errors="coerce" bleibt erhalten: kein Absturz bei Unsinn."""
        ergebnis = clean_garmin_typing(_raw_garmin(["kein Datum"]))["date"].iloc[0]

        assert pd.isna(ergebnis)


class TestConvertDurationToSeconds:
    """Umrechnung der Garmin-Dauerangabe in Sekunden."""

    @pytest.mark.parametrize(
        "eingabe, erwartet",
        [
            ("01:23:45", 5025.0),  # hh:mm:ss
            ("00:36:52", 2212.0),  # der Wert aus der Fixture
            ("00:00:30", 30.0),
            ("10:00:00", 36000.0),
            ("28:00", 1680.0),  # mm:ss
            ("0:30", 30.0),
            (1800, 1800.0),  # bereits numerisch
            (1800.5, 1800.5),
        ],
    )
    def test_gueltige_eingaben(self, eingabe, erwartet):
        assert convert_duration_to_seconds(eingabe) == erwartet

    @pytest.mark.parametrize(
        "eingabe",
        [
            None,
            np.nan,
            pd.NA,
            "abc",
            "",
            "01:xx:45",
            "1:2:3:4",  # mehr Teile als vorgesehen
        ],
    )
    def test_ungueltige_eingaben_ergeben_nan(self, eingabe):
        assert np.isnan(convert_duration_to_seconds(eingabe))


class TestFilterRunning:
    """Beschränkung auf Laufaktivitäten."""

    @pytest.mark.parametrize(
        "typ, behalten",
        [
            ("Running", True),
            ("Trail Running", True),
            ("Treadmill Running", True),
            ("running", True),  # Kleinschreibung
            ("Cycling", False),
            ("Swimming", False),
            ("Walking", False),
        ],
    )
    def test_erkennt_laufvarianten(self, typ, behalten):
        df = pd.DataFrame({"activity_type": [typ]})

        assert len(filter_running(df)) == (1 if behalten else 0)

    def test_fehlende_spalte_laesst_datensatz_unveraendert(self):
        """Absicherung gegen einen Export ohne Aktivitätstyp."""
        df = pd.DataFrame({"distance_km": [5.0]})

        assert filter_running(df).equals(df)

    def test_fehlender_typ_wird_verworfen(self):
        df = pd.DataFrame({"activity_type": [None, "Running"]})

        assert len(filter_running(df)) == 1


class TestReduceToCoreColumns:
    """Reduktion des rund 30-spaltigen Exports auf die Kernvariablen."""

    def test_liefert_genau_das_rohschema(self, garmin_raw):
        reduziert = reduce_to_core_columns(filter_running(garmin_raw))

        assert list(reduziert.columns) == RAW_CORE_COLUMNS

    def test_fehlende_kernspalten_werden_ergaenzt(self):
        """Ein Export ohne Herzfrequenz darf nicht zum Schemabruch führen."""
        df = pd.DataFrame({"date": ["01.01.2025 10:00"], "distance_km": [5.0]})

        reduziert = reduce_to_core_columns(df)

        assert list(reduziert.columns) == RAW_CORE_COLUMNS
        assert reduziert["avg_heart_rate"].isna().all()


class TestCleanGarminTyping:
    """Schema und Datentypen nach der Typisierung."""

    def test_liefert_genau_das_gemeinsame_schema(self, garmin_typed):
        assert list(garmin_typed.columns) == CORE_COLUMNS

    def test_rohspalte_duration_verschwindet(self, garmin_typed):
        """TODO 11: Die Dauer wird ausschliesslich über duration_sec geführt."""
        assert "duration" not in garmin_typed.columns
        assert "duration_sec" in garmin_typed.columns

    def test_dauer_wurde_umgerechnet(self, garmin_typed):
        """00:36:52 aus der Fixture entspricht 2212 Sekunden."""
        assert 2212.0 in garmin_typed["duration_sec"].tolist()

    def test_datentypen(self, garmin_typed):
        assert garmin_typed["date"].dtype == "datetime64[ns]"
        assert garmin_typed["export_date"].dtype == "datetime64[ns]"
        assert garmin_typed["activity_type"].dtype == "category"
        assert garmin_typed["source"].dtype == "category"
        assert garmin_typed["distance_km"].dtype == "float64"
        assert garmin_typed["duration_sec"].dtype == "float64"

    def test_meter_heuristik(self):
        """Werte oberhalb jeder plausiblen Laufdistanz gelten als Meter."""
        df = _raw_garmin(["01.01.2025 10:00", "02.01.2025 10:00"])
        df["distance_km"] = [5000.0, 10000.0]

        ergebnis = clean_garmin_typing(df)

        assert ergebnis["distance_km"].tolist() == [5.0, 10.0]

    def test_kilometer_bleiben_unangetastet(self):
        df = _raw_garmin(["01.01.2025 10:00", "02.01.2025 10:00"])
        df["distance_km"] = [5.0, 10.0]

        ergebnis = clean_garmin_typing(df)

        assert ergebnis["distance_km"].tolist() == [5.0, 10.0]
