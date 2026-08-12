"""Schema-Checks nach Bereinigung und nach der Gesamtpipeline.

Vom Bewertungsraster ausdrücklich verlangt.

Diese Tests sind die Absicherung gegen stille Schemaänderungen: Wird eine
Spalte umbenannt, versehentlich fallen gelassen oder ändert sich ihr Typ,
schlägt hier etwas fehl, statt dass es erst im Export oder in der Auswertung
auffällt.

Beide Quellen werden gegen dasselbe Schema geprüft. Genau darauf beruht die
Zusammenführung: Sind Garmin- und Apple-Daten nach der Typisierung nicht
strukturgleich, ergibt die Konkatenation stillschweigend Spalten voller NaN.
"""

import pandas as pd
import pytest

from running_data import run_pipeline
from running_data.config import (
    CORE_COLUMNS,
    ESSENTIAL_COLUMNS,
    NUMERIC_COLUMNS,
    PROVENANCE_COLUMNS,
)

from conftest import APPLE_FIXTURE_GLOB, GARMIN_FIXTURE_GLOB

# Von add_features ergänzte Spalten. Bewusst hier und nicht in der
# Konfiguration: Der Test soll fehlschlagen, wenn sich das Ergebnisschema
# ändert, und nicht stillschweigend mitwandern.
FEATURE_COLUMNS = ["duration_min", "pace_min_per_km"]

# Was die Bereinigungspipeline über das Kernschema hinaus ergänzt.
CLEANED_COLUMNS = CORE_COLUMNS + PROVENANCE_COLUMNS

# Das Schema des ausgelieferten Datensatzes.
FINAL_COLUMNS = CLEANED_COLUMNS + FEATURE_COLUMNS


@pytest.fixture(scope="module")
def ergebnis():
    """Ein Pipeline-Lauf über die Fixtures, ohne zu schreiben.

    Modulweit, weil kein Test das Ergebnis verändert und der Lauf sonst pro
    Test wiederholt würde.
    """
    return run_pipeline(
        garmin_path=GARMIN_FIXTURE_GLOB,
        apple_path=APPLE_FIXTURE_GLOB,
        output_dir=None,
    )


class TestSchemaNachTypisierung:
    """Beide Quellen müssen nach der Typisierung strukturgleich sein."""

    def test_garmin_liefert_kernschema(self, garmin_typed):
        assert list(garmin_typed.columns) == CORE_COLUMNS

    def test_apple_liefert_kernschema(self, apple_typed):
        assert list(apple_typed.columns) == CORE_COLUMNS

    def test_beide_quellen_sind_strukturgleich(self, garmin_typed, apple_typed):
        """Voraussetzung dafür, dass die Konkatenation sinnvoll ist."""
        assert list(garmin_typed.columns) == list(apple_typed.columns)


class TestSchemaNachBereinigung:
    """Nach der Pipeline kommen die beiden Herkunftsspalten hinzu."""

    @pytest.mark.parametrize("quelle", ["garmin_cleaned", "apple_cleaned"])
    def test_spalten(self, quelle, request):
        bereinigt = request.getfixturevalue(quelle)

        assert list(bereinigt.columns) == CLEANED_COLUMNS

    @pytest.mark.parametrize("quelle", ["garmin_cleaned", "apple_cleaned"])
    def test_datentypen(self, quelle, request):
        bereinigt = request.getfixturevalue(quelle)

        assert bereinigt["date"].dtype == "datetime64[ns]"
        assert bereinigt["export_date"].dtype == "datetime64[ns]"
        assert bereinigt["activity_type"].dtype == "category"
        assert bereinigt["source"].dtype == "category"
        assert bereinigt["calories_imputed"].dtype == "bool"
        for spalte in NUMERIC_COLUMNS:
            assert bereinigt[spalte].dtype == "float64", spalte

    @pytest.mark.parametrize("quelle", ["garmin_cleaned", "apple_cleaned"])
    def test_pflichtfelder_sind_vollstaendig(self, quelle, request):
        """Zeilen ohne Distanz oder Dauer entfernt der kritische Schritt 3."""
        bereinigt = request.getfixturevalue(quelle)

        assert not bereinigt[ESSENTIAL_COLUMNS].isna().any().any()


class TestSchemaNachGesamtpipeline:
    """Das Schema des ausgelieferten Datensatzes."""

    def test_spalten_und_reihenfolge(self, ergebnis):
        assert list(ergebnis.data.columns) == FINAL_COLUMNS

    def test_keine_doppelten_spalten(self, ergebnis):
        assert len(set(ergebnis.data.columns)) == len(ergebnis.data.columns)

    def test_rohspalte_duration_ist_verschwunden(self, ergebnis):
        """TODO 11: Die Dauer wird nur noch über duration_sec geführt."""
        assert "duration" not in ergebnis.data.columns

    def test_abgeleitete_variablen_sind_enthalten(self, ergebnis):
        """Sie fehlten, solange add_features von niemandem aufgerufen wurde."""
        for spalte in FEATURE_COLUMNS:
            assert spalte in ergebnis.data.columns
            assert ergebnis.data[spalte].notna().all()

    def test_beide_quellen_sind_vertreten(self, ergebnis):
        assert set(ergebnis.data["source"]) == {"garmin", "apple"}

    def test_zeilenzahl_entspricht_der_summe_der_quellen(self, ergebnis):
        erwartet = sum(s["final_rows"] for s in ergebnis.summaries.values())

        assert len(ergebnis.data) == erwartet

    def test_chronologisch_sortiert(self, ergebnis):
        assert ergebnis.data["date"].is_monotonic_increasing

    def test_kategorien_werden_beim_zusammenfuehren_zu_object(self, ergebnis):
        """Dokumentiert bewusst das Ist-Verhalten, nicht das Wunschverhalten.

        step_finalize_types typisiert activity_type und source je Quelle als
        category. pandas.concat kann zwei Kategorien mit unterschiedlichen
        Ausprägungen aber nicht zusammenführen und fällt auf object zurück.
        Der Speichervorteil der Kategorien geht dadurch im Endergebnis
        verloren.
        """
        assert ergebnis.data["activity_type"].dtype == "object"
        assert ergebnis.data["source"].dtype == "object"

    def test_datumsspalten_bleiben_zeitstempel(self, ergebnis):
        assert ergebnis.data["date"].dtype == "datetime64[ns]"
        assert ergebnis.data["export_date"].dtype == "datetime64[ns]"

    def test_pace_passt_zu_distanz_und_dauer(self, ergebnis):
        """Die abgeleiteten Variablen müssen zu ihren Ausgangswerten passen."""
        erwartet = (ergebnis.data["duration_sec"] / 60) / ergebnis.data["distance_km"]

        pd.testing.assert_series_equal(
            ergebnis.data["pace_min_per_km"], erwartet, check_names=False
        )
