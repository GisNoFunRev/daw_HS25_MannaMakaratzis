"""Tests der Persistierung (running_data.export).

Der Export ist die letzte Station der Pipeline — was hier verloren geht,
merkt niemand mehr. Geprüft wird deshalb vor allem, dass Parquet den
Datensatz verlustfrei zurückgibt, einschliesslich der Datentypen.

Alle Tests schreiben nach tmp_path. Der echte Ausgabeordner
data/processed wird nie angefasst.
"""

import pandas as pd
import pytest

from running_data.export import OUTPUT_BASENAME, read_processed, write_outputs


class TestWriteOutputs:
    """Schreiben der beiden Ausgabeformate."""

    def test_schreibt_parquet_und_csv(self, garmin_cleaned, tmp_path):
        pfade = write_outputs(garmin_cleaned, tmp_path)

        assert set(pfade) == {"parquet", "csv"}
        assert pfade["parquet"].exists()
        assert pfade["csv"].exists()

    def test_verwendet_den_standardnamen(self, garmin_cleaned, tmp_path):
        pfade = write_outputs(garmin_cleaned, tmp_path)

        assert pfade["parquet"].name == f"{OUTPUT_BASENAME}.parquet"
        assert pfade["csv"].name == f"{OUTPUT_BASENAME}.csv"

    def test_eigener_dateiname(self, garmin_cleaned, tmp_path):
        pfade = write_outputs(garmin_cleaned, tmp_path, basename="laeufe_2025")

        assert pfade["parquet"].name == "laeufe_2025.parquet"

    def test_legt_fehlenden_ordner_an(self, garmin_cleaned, tmp_path):
        ziel = tmp_path / "gibt" / "es" / "noch" / "nicht"

        pfade = write_outputs(garmin_cleaned, ziel)

        assert ziel.is_dir()
        assert pfade["parquet"].exists()

    def test_ueberschreibt_bestehende_datei(self, garmin_cleaned, tmp_path):
        write_outputs(garmin_cleaned, tmp_path)
        write_outputs(garmin_cleaned.head(1), tmp_path)

        assert len(read_processed(tmp_path)) == 1

    def test_schreibt_ohne_index_spalte(self, garmin_cleaned, tmp_path):
        """Ein mitgeschriebener Index würde als Spalte "Unnamed: 0" auftauchen."""
        pfade = write_outputs(garmin_cleaned, tmp_path)

        aus_csv = pd.read_csv(pfade["csv"])

        assert not any(spalte.startswith("Unnamed") for spalte in aus_csv.columns)


class TestRoundtrip:
    """Schreiben und Wiedereinlesen muss verlustfrei sein."""

    def test_parquet_liefert_denselben_datensatz(self, garmin_cleaned, tmp_path):
        write_outputs(garmin_cleaned, tmp_path)

        gelesen = read_processed(tmp_path)

        pd.testing.assert_frame_equal(garmin_cleaned.reset_index(drop=True), gelesen)

    def test_parquet_erhaelt_die_datentypen(self, garmin_cleaned, tmp_path):
        """Der Grund, warum Parquet und nicht CSV das massgebliche Format ist."""
        write_outputs(garmin_cleaned, tmp_path)

        gelesen = read_processed(tmp_path)

        assert gelesen["date"].dtype == "datetime64[ns]"
        assert gelesen["activity_type"].dtype == "category"
        assert gelesen["calories_imputed"].dtype == "bool"

    def test_csv_verliert_die_datentypen(self, garmin_cleaned, tmp_path):
        """Festgehalten als bewusste Eigenschaft, nicht als Mangel.

        Deshalb ist die CSV laut Modul-Docstring die Kontrollkopie und nicht
        der Eingang für weitere Verarbeitungsschritte.
        """
        pfade = write_outputs(garmin_cleaned, tmp_path)

        aus_csv = pd.read_csv(pfade["csv"])

        assert aus_csv["date"].dtype == "object"
        assert aus_csv["activity_type"].dtype == "object"

    def test_csv_enthaelt_dieselben_zeilen_und_spalten(self, garmin_cleaned, tmp_path):
        pfade = write_outputs(garmin_cleaned, tmp_path)

        aus_csv = pd.read_csv(pfade["csv"])

        assert list(aus_csv.columns) == list(garmin_cleaned.columns)
        assert len(aus_csv) == len(garmin_cleaned)


class TestReadProcessed:
    """Einlesen des zuvor geschriebenen Datensatzes."""

    def test_fehlende_datei_meldet_sich_deutlich(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            read_processed(tmp_path)
