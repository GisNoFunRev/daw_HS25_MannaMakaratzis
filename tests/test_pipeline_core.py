"""Tests der Pipeline-Mechanik (running_data.pipeline.core).

Geprüft wird hier nicht, was die Bereinigung tut, sondern wie die Pipeline
einen beliebigen Schritt ausführt — insbesondere die Unterscheidung zwischen
kritischen und unkritischen Schritten.

Diese Fehlerbehandlung ist das Herzstück der Klasse und wird im Normalbetrieb
nie ausgelöst: Solange alle acht Schritte durchlaufen, bleibt sie toter Code.
Erst hier zeigt sich, ob sie das tut, was der Docstring verspricht.
"""

import pandas as pd
import pytest

from running_data.pipeline.core import CleaningStep, DataCleaningPipeline


@pytest.fixture
def daten():
    """Ein beliebiger Datensatz mit drei Zeilen."""
    return pd.DataFrame({"a": [1, 2, 3]})


def _schritt(name, funktion, kritisch=False):
    """Kurzschreibweise für einen Testschritt."""
    return CleaningStep(
        name=name, function=funktion, description="Testschritt", is_critical=kritisch
    )


def _unveraendert(df, config, report):
    return df


def _wirft(df, config, report):
    raise RuntimeError("Schritt fehlgeschlagen")


def _entfernt_alles(df, config, report):
    return df.iloc[0:0]


def _entfernt_eine_zeile(df, config, report):
    return df.iloc[1:]


class TestAusfuehrung:
    """Reihenfolge, Verkettung und Protokollierung."""

    def test_schritte_laufen_in_der_hinzugefuegten_reihenfolge(self, daten, config):
        protokoll = []

        def _merker(name):
            def _fn(df, cfg, rep):
                protokoll.append(name)
                return df

            return _fn

        pipeline = DataCleaningPipeline("Test", config)
        pipeline.add_step(_schritt("erster", _merker("erster")))
        pipeline.add_step(_schritt("zweiter", _merker("zweiter")))
        pipeline.add_step(_schritt("dritter", _merker("dritter")))

        pipeline.run(daten)

        assert protokoll == ["erster", "zweiter", "dritter"]

    def test_add_step_erlaubt_verkettung(self, config):
        pipeline = DataCleaningPipeline("Test", config)

        ergebnis = pipeline.add_step(_schritt("a", _unveraendert)).add_step(
            _schritt("b", _unveraendert)
        )

        assert ergebnis is pipeline
        assert len(pipeline.steps) == 2

    def test_bericht_haelt_jeden_schritt_fest(self, daten, config):
        pipeline = DataCleaningPipeline("Test", config)
        pipeline.add_step(_schritt("Erster", _unveraendert))
        pipeline.add_step(_schritt("Zweiter", _entfernt_eine_zeile))

        _, bericht = pipeline.run(daten)

        tabelle = bericht.to_dataframe()
        assert tabelle["step"].tolist() == ["Erster", "Zweiter"]
        assert tabelle["removed"].tolist() == [0, 1]

    def test_bericht_kennt_anfangs_und_endbestand(self, daten, config):
        pipeline = DataCleaningPipeline("Test", config)
        pipeline.add_step(_schritt("Entfernt eine", _entfernt_eine_zeile))

        _, bericht = pipeline.run(daten)

        assert bericht.initial_rows == 3
        assert bericht.final_rows == 2

    def test_eingabe_wird_nicht_veraendert(self, daten, config):
        """Die Pipeline arbeitet laut Docstring auf einer Kopie."""
        vorher = daten.copy()
        pipeline = DataCleaningPipeline("Test", config)
        pipeline.add_step(_schritt("Entfernt eine", _entfernt_eine_zeile))

        pipeline.run(daten)

        pd.testing.assert_frame_equal(daten, vorher)


class TestKritischeSchritte:
    """Ein kritischer Schritt bricht die Pipeline ab."""

    def test_ausnahme_wird_weitergereicht(self, daten, config):
        pipeline = DataCleaningPipeline("Test", config)
        pipeline.add_step(_schritt("Kritisch", _wirft, kritisch=True))

        with pytest.raises(RuntimeError, match="Schritt fehlgeschlagen"):
            pipeline.run(daten)

    def test_leeres_ergebnis_ist_ein_fehler(self, daten, config):
        """Auch ein technisch erfolgreicher Schritt, der alles entfernt.

        Ohne diese Prüfung würden die folgenden Schritte auf einem leeren
        Datensatz arbeiten und am Ende ein plausibel aussehendes, aber leeres
        Ergebnis liefern.
        """
        pipeline = DataCleaningPipeline("Test", config)
        pipeline.add_step(_schritt("Kritisch", _entfernt_alles, kritisch=True))

        with pytest.raises(ValueError, match="removed all data"):
            pipeline.run(daten)

    def test_nachfolgende_schritte_laufen_nicht_mehr(self, daten, config):
        protokoll = []

        def _danach(df, cfg, rep):
            protokoll.append("gelaufen")
            return df

        pipeline = DataCleaningPipeline("Test", config)
        pipeline.add_step(_schritt("Kritisch", _wirft, kritisch=True))
        pipeline.add_step(_schritt("Danach", _danach))

        with pytest.raises(RuntimeError):
            pipeline.run(daten)

        assert protokoll == []


class TestUnkritischeSchritte:
    """Ein unkritischer Schritt darf fehlschlagen, ohne alles mitzureissen."""

    def test_pipeline_laeuft_weiter(self, daten, config):
        protokoll = []

        def _danach(df, cfg, rep):
            protokoll.append("gelaufen")
            return df

        pipeline = DataCleaningPipeline("Test", config)
        pipeline.add_step(_schritt("Unkritisch", _wirft, kritisch=False))
        pipeline.add_step(_schritt("Danach", _danach))

        pipeline.run(daten)

        assert protokoll == ["gelaufen"]

    def test_datenstand_von_vor_dem_schritt_bleibt_erhalten(self, daten, config):
        """Die Zuweisung an current_df erfolgt nicht, wenn der Schritt wirft."""
        pipeline = DataCleaningPipeline("Test", config)
        pipeline.add_step(_schritt("Entfernt eine", _entfernt_eine_zeile))
        pipeline.add_step(_schritt("Unkritisch", _wirft, kritisch=False))

        ergebnis, _ = pipeline.run(daten)

        assert len(ergebnis) == 2

    def test_fehlgeschlagener_schritt_steht_nicht_im_bericht(self, daten, config):
        """add_step wird bei einer Ausnahme nicht mehr erreicht.

        Der Bericht zeigt den Schritt deshalb gar nicht — der Fehlschlag ist
        nur im Log sichtbar. Festgehalten als Ist-Verhalten.
        """
        pipeline = DataCleaningPipeline("Test", config)
        pipeline.add_step(_schritt("Laeuft", _unveraendert))
        pipeline.add_step(_schritt("Faellt aus", _wirft, kritisch=False))

        _, bericht = pipeline.run(daten)

        assert bericht.to_dataframe()["step"].tolist() == ["Laeuft"]

    def test_leeres_ergebnis_ist_erlaubt(self, daten, config):
        """Anders als beim kritischen Schritt kein Abbruch."""
        pipeline = DataCleaningPipeline("Test", config)
        pipeline.add_step(_schritt("Unkritisch", _entfernt_alles, kritisch=False))

        ergebnis, _ = pipeline.run(daten)

        assert len(ergebnis) == 0


@pytest.mark.xfail(
    strict=True,
    reason=(
        "Bekannter Fehler in CleaningReport.add_step: Die Logzeile rechnet "
        "removed / rows_before * 100 ohne die Absicherung, die zwei Zeilen "
        "darueber fuer removal_rate getroffen wird. Ein leerer Datensatz "
        "erzeugt dadurch ZeroDivisionError statt einer verstaendlichen "
        "Meldung. Nicht im Rahmen dieser Aufgabe behoben; run_pipeline "
        "umgeht den Fall, indem es leere Quellen ueberspringt."
    ),
)
def test_leere_eingabe_ergibt_verstaendlichen_fehler(config):
    """Was passieren sollte, wenn die Pipeline nichts zu tun bekommt.

    Erwartet wird der ValueError aus der Leerprüfung des kritischen Schritts.
    Tatsächlich kommt ZeroDivisionError, weil add_step schon vorher an der
    Logzeile scheitert.

    Der kritische Schritt ist hier entscheidend: Bei einem unkritischen
    Schritt fängt die Pipeline die ZeroDivisionError ab und läuft weiter,
    der Fehler bleibt dann unsichtbar (siehe test_leeres_ergebnis_ist_erlaubt).
    Die Standardpipeline enthält mit "Validate Essentials" einen kritischen
    Schritt, weshalb build_cleaning_pipeline auf einem leeren Datensatz
    tatsächlich mit ZeroDivisionError abbricht.
    """
    pipeline = DataCleaningPipeline("Test", config)
    pipeline.add_step(_schritt("Kritisch", _unveraendert, kritisch=True))

    with pytest.raises(ValueError):
        pipeline.run(pd.DataFrame({"a": []}))
