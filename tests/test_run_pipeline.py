"""End-to-End-Tests der Gesamtpipeline (running_data.pipeline.run).

Der Nachweis, dass das Projekt als Ganzes läuft: von den Rohdateien über
Import, Typisierung, Bereinigung, Zusammenführung und abgeleitete Variablen
bis zu den geschriebenen Dateien.

Gearbeitet wird auf den Fixtures, nicht auf data/ — der Test muss auch bei
einem frischen Checkout ohne Rohdaten durchlaufen.
"""

import logging

import pandas as pd
import pytest

from running_data import DataCleaningConfig, PipelineResult, run_pipeline
from running_data.__main__ import build_parser, main
from running_data.export import read_processed

from conftest import APPLE_FIXTURE_GLOB, GARMIN_FIXTURE_GLOB

# Erwartete Zeilenzahlen der Fixtures: Garmin liefert 5 Aktivitäten, davon
# sind 4 Läufe; Apple liefert 3 Workouts, davon 2 Läufe. Alle überstehen die
# Bereinigung.
GARMIN_LAEUFE = 4
APPLE_LAEUFE = 2
GESAMT = GARMIN_LAEUFE + APPLE_LAEUFE


@pytest.fixture
def logging_wiederherstellen():
    """Stellt die Logging-Konfiguration nach einem CLI-Aufruf wieder her.

    configure_logging arbeitet mit force=True und entfernt dabei auch die
    Handler, die pytest für die Testausgabe installiert hat.
    """
    root = logging.getLogger()
    handler, level = root.handlers[:], root.level
    yield
    root.handlers[:] = handler
    root.setLevel(level)


@pytest.fixture(scope="module")
def ergebnis():
    """Ein Lauf über beide Fixture-Quellen, ohne zu schreiben."""
    return run_pipeline(
        garmin_path=GARMIN_FIXTURE_GLOB,
        apple_path=APPLE_FIXTURE_GLOB,
        output_dir=None,
    )


class TestErgebnis:
    """Inhalt des zurückgegebenen PipelineResult."""

    def test_zeilenzahl(self, ergebnis):
        assert len(ergebnis.data) == GESAMT

    def test_beide_quellen_vollstaendig_verarbeitet(self, ergebnis):
        verteilung = ergebnis.data["source"].value_counts()

        assert verteilung["garmin"] == GARMIN_LAEUFE
        assert verteilung["apple"] == APPLE_LAEUFE

    def test_berichte_je_quelle(self, ergebnis):
        assert set(ergebnis.reports) == {"Garmin", "Apple"}
        assert set(ergebnis.summaries) == {"Garmin", "Apple"}
        assert set(ergebnis.qualities) == {"Garmin", "Apple"}

    def test_zusammenfassung_passt_zum_datensatz(self, ergebnis):
        assert ergebnis.summaries["Garmin"]["final_rows"] == GARMIN_LAEUFE
        assert ergebnis.summaries["Apple"]["final_rows"] == APPLE_LAEUFE

    def test_bericht_enthaelt_alle_acht_schritte(self, ergebnis):
        assert len(ergebnis.reports["Garmin"].to_dataframe()) == 8

    def test_ergebnis_ist_unveraenderlich(self, ergebnis):
        """Ein eingefrorenes Ergebnis kann nachträglich nicht verfälscht werden."""
        with pytest.raises(Exception):
            ergebnis.data = pd.DataFrame()

    def test_ist_ein_pipeline_result(self, ergebnis):
        assert isinstance(ergebnis, PipelineResult)


class TestSchreiben:
    """Verhalten von output_dir."""

    def test_none_schreibt_nichts(self, ergebnis, tmp_path):
        assert ergebnis.outputs == {}
        assert list(tmp_path.iterdir()) == []

    def test_schreibt_beide_formate(self, tmp_path):
        result = run_pipeline(
            garmin_path=GARMIN_FIXTURE_GLOB,
            apple_path=APPLE_FIXTURE_GLOB,
            output_dir=tmp_path,
        )

        assert result.outputs["parquet"].exists()
        assert result.outputs["csv"].exists()

    def test_geschriebene_datei_entspricht_dem_ergebnis(self, tmp_path):
        result = run_pipeline(
            garmin_path=GARMIN_FIXTURE_GLOB,
            apple_path=APPLE_FIXTURE_GLOB,
            output_dir=tmp_path,
        )

        gelesen = read_processed(tmp_path)

        pd.testing.assert_frame_equal(result.data.reset_index(drop=True), gelesen)


class TestFehlendeQuellen:
    """Das Projekt soll auch mit nur einem Export laufen."""

    def test_nur_garmin(self, tmp_path):
        result = run_pipeline(
            garmin_path=GARMIN_FIXTURE_GLOB,
            apple_path=str(tmp_path / "gibtsnicht" / "*.xml"),
            output_dir=None,
        )

        assert len(result.data) == GARMIN_LAEUFE
        assert set(result.reports) == {"Garmin"}

    def test_nur_apple(self, tmp_path):
        """Ohne die Leerprüfung stürzt hier apple_typing.filter_running ab."""
        result = run_pipeline(
            garmin_path=str(tmp_path / "gibtsnicht" / "*.csv"),
            apple_path=APPLE_FIXTURE_GLOB,
            output_dir=None,
        )

        assert len(result.data) == APPLE_LAEUFE
        assert set(result.reports) == {"Apple"}

    def test_gar_keine_quelle_meldet_sich_deutlich(self, tmp_path):
        with pytest.raises(ValueError, match="Keine der Quellen"):
            run_pipeline(
                garmin_path=str(tmp_path / "leer" / "*.csv"),
                apple_path=str(tmp_path / "leer" / "*.xml"),
                output_dir=None,
            )


class TestKonfiguration:
    """Eine abweichende Konfiguration muss durchschlagen."""

    def test_strengere_distanzgrenze_entfernt_zeilen(self):
        class NurKurzstrecken(DataCleaningConfig):
            DISTANCE_MAX = 6.0

        result = run_pipeline(
            garmin_path=GARMIN_FIXTURE_GLOB,
            apple_path=APPLE_FIXTURE_GLOB,
            output_dir=None,
            config=NurKurzstrecken(),
        )

        assert len(result.data) < GESAMT
        assert result.data["distance_km"].max() <= 6.0


class TestKommandozeile:
    """python -m running_data — der Aufruf für das Abgabe-Video."""

    def test_dry_run_endet_erfolgreich(self, capsys, logging_wiederherstellen):
        code = main(
            [
                "--garmin",
                GARMIN_FIXTURE_GLOB,
                "--apple",
                APPLE_FIXTURE_GLOB,
                "--dry-run",
                "--quiet",
            ]
        )

        assert code == 0
        ausgabe = capsys.readouterr().out
        assert f"Kombiniert: {GESAMT} Zeilen" in ausgabe
        assert "Nichts geschrieben" in ausgabe

    def test_schreibt_in_den_angegebenen_ordner(
        self, tmp_path, capsys, logging_wiederherstellen
    ):
        code = main(
            [
                "--garmin",
                GARMIN_FIXTURE_GLOB,
                "--apple",
                APPLE_FIXTURE_GLOB,
                "--output",
                str(tmp_path),
                "--quiet",
            ]
        )

        assert code == 0
        assert (tmp_path / "combined_runs.parquet").exists()
        assert "Geschrieben:" in capsys.readouterr().out

    def test_ohne_daten_kein_traceback(self, tmp_path, capsys, logging_wiederherstellen):
        """Ein falscher Pfad ist ein Bedienfehler, kein Programmabsturz."""
        code = main(
            [
                "--garmin",
                str(tmp_path / "*.csv"),
                "--apple",
                str(tmp_path / "*.xml"),
                "--quiet",
            ]
        )

        assert code == 1
        assert "Fehler:" in capsys.readouterr().err

    def test_hilfe_ist_abrufbar(self, capsys):
        with pytest.raises(SystemExit) as abbruch:
            build_parser().parse_args(["--help"])

        assert abbruch.value.code == 0
        assert "--garmin" in capsys.readouterr().out

    def test_standardwerte_zeigen_auf_das_projektverzeichnis(self):
        """Ohne Argumente muss der Aufruf die echten Exporte finden."""
        argumente = build_parser().parse_args([])

        assert argumente.garmin.endswith("Activities.csv")
        assert argumente.apple.endswith("Export.xml")
        assert not argumente.dry_run
