"""Tests der Kalorien-Imputation (running_data.cleaning.imputation).

Die vierstufige Fallback-Kette ist die komplexeste Logik im Projekt und im
Normalbetrieb kaum zu beobachten: Mit den echten Daten greift praktisch immer
dieselbe Ebene, die übrigen drei bleiben ungeprüft.

Diese Tests konstruieren deshalb für jede Ebene genau die Datenlage, die sie
erzwingt:

    level3   gleiche Quelle, gleiche Distanzklasse, gleiches HF-Quantil
    level2   gleiche Quelle, gleiche Distanzklasse
    level1   gleiche Quelle
    level0   der gesamte Datensatz
"""

import numpy as np
import pandas as pd

from running_data.cleaning.imputation import (
    _build_distance_bins,
    count_changed,
    impute_grouped_calories,
)


class TestFallbackKette:
    """Je ein Datensatz pro Ebene der Fallback-Kette."""

    def test_level3_gleiche_distanzklasse_und_herzfrequenz(self, make_runs, config):
        """Der Idealfall: ein direkt vergleichbarer Lauf existiert.

        Acht Läufe mit vier verschiedenen Herzfrequenzen, also vier
        HF-Quantilen zu je zwei Läufen. Der Lauf ohne Kalorienwert teilt sich
        Distanzklasse und Quantil mit genau einem anderen.
        """
        df = make_runs(
            distance_km=[3.0, 4.0, 3.5, 4.5, 6.0, 7.0, 6.5, 7.5],
            avg_heart_rate=[140.0, 140.0, 150.0, 150.0, 160.0, 160.0, 170.0, 170.0],
            calories=[300.0, np.nan, 320.0, 330.0, 400.0, 410.0, 420.0, 430.0],
        )

        ergebnis = impute_grouped_calories(df, config)

        assert ergebnis.loc[1, "imputation_level"] == "level3"
        assert ergebnis.loc[1, "calories"] == 300.0
        assert ergebnis.loc[1, "calories_imputed"]

    def test_level2_nur_distanzklasse_passt(self, make_runs, config):
        """Das HF-Quantil ist leer, die Distanzklasse trägt.

        Vier verschiedene Herzfrequenzen bei vier Läufen: Jeder Lauf bekommt
        sein eigenes Quantil, level3 findet also keinen Vergleichswert.
        """
        df = make_runs(
            distance_km=[3.0, 4.0, 6.0, 7.0],
            avg_heart_rate=[140.0, 200.0, 150.0, 160.0],
            calories=[300.0, np.nan, 400.0, 410.0],
        )

        ergebnis = impute_grouped_calories(df, config)

        assert ergebnis.loc[1, "imputation_level"] == "level2"
        assert ergebnis.loc[1, "calories"] == 300.0

    def test_level1_nur_die_quelle_passt(self, make_runs, config):
        """Der Lauf ist der einzige seiner Distanzklasse.

        18 km fällt in die Klasse [15, 25) und steht dort allein — weder
        level3 noch level2 finden etwas, der Median der Quelle greift.
        """
        df = make_runs(
            distance_km=[3.0, 6.0, 18.0],
            avg_heart_rate=[140.0, 150.0, 160.0],
            calories=[300.0, 400.0, np.nan],
        )

        ergebnis = impute_grouped_calories(df, config)

        assert ergebnis.loc[2, "imputation_level"] == "level1"
        assert ergebnis.loc[2, "calories"] == 350.0  # Median aus 300 und 400

    def test_level0_der_gesamte_datensatz(self, make_runs, config):
        """Die ganze Quelle hat keinen einzigen Kalorienwert.

        Nur die andere Quelle liefert noch etwas — die letzte Auffanglinie,
        die garantiert, dass nie ein Wert fehlt.
        """
        df = make_runs(
            source=["garmin", "garmin", "apple", "apple"],
            distance_km=[3.0, 4.0, 3.0, 4.0],
            avg_heart_rate=[140.0, 150.0, 160.0, 170.0],
            calories=[np.nan, np.nan, 400.0, 500.0],
        )

        ergebnis = impute_grouped_calories(df, config)

        assert ergebnis.loc[0, "imputation_level"] == "level0"
        assert ergebnis.loc[0, "calories"] == 450.0  # Median aus 400 und 500

    def test_am_ende_fehlt_kein_wert(self, make_runs, config):
        """Die Kette muss jeden fehlenden Wert füllen, egal auf welcher Ebene."""
        df = make_runs(
            distance_km=[3.0, 8.0, 12.0, 20.0, 30.0],
            avg_heart_rate=[140.0, 150.0, 160.0, 170.0, 180.0],
            calories=[300.0, np.nan, np.nan, np.nan, np.nan],
        )

        ergebnis = impute_grouped_calories(df, config)

        assert ergebnis["calories"].notna().all()


class TestHerkunftsspalten:
    """calories_imputed und imputation_level dokumentieren den Eingriff."""

    def test_vorhandene_werte_bleiben_unangetastet(self, make_runs, config):
        df = make_runs(
            distance_km=[3.0, 4.0],
            avg_heart_rate=[140.0, 150.0],
            calories=[300.0, 350.0],
        )

        ergebnis = impute_grouped_calories(df, config)

        assert ergebnis["calories"].tolist() == [300.0, 350.0]
        assert not ergebnis["calories_imputed"].any()

    def test_nicht_imputierte_zeilen_haben_kein_level(self, make_runs, config):
        """Ein leeres imputation_level heisst "war vollständig".

        Genau diese Bedeutung ist der Grund, warum die Spalte über
        PROVENANCE_COLUMNS aus der Completeness-Messung ausgenommen ist.
        """
        df = make_runs(
            distance_km=[3.0, 4.0],
            avg_heart_rate=[140.0, 150.0],
            calories=[300.0, np.nan],
        )

        ergebnis = impute_grouped_calories(df, config)

        assert pd.isna(ergebnis.loc[0, "imputation_level"])
        assert not pd.isna(ergebnis.loc[1, "imputation_level"])

    def test_nullwerte_gelten_als_fehlend(self, make_runs, config):
        """0 kcal ist kein Messwert, sondern eine Luecke."""
        df = make_runs(
            distance_km=[3.0, 4.0],
            avg_heart_rate=[140.0, 150.0],
            calories=[300.0, 0.0],
        )

        ergebnis = impute_grouped_calories(df, config)

        assert ergebnis.loc[1, "calories_imputed"]
        assert ergebnis.loc[1, "calories"] > 0

    def test_negative_werte_gelten_als_fehlend(self, make_runs, config):
        df = make_runs(
            distance_km=[3.0, 4.0],
            avg_heart_rate=[140.0, 150.0],
            calories=[300.0, -50.0],
        )

        ergebnis = impute_grouped_calories(df, config)

        assert ergebnis.loc[1, "calories_imputed"]
        assert ergebnis.loc[1, "calories"] > 0

    def test_hilfsspalten_werden_entfernt(self, make_runs, config):
        """_dist_bin und _hr_bin sind Zwischenergebnisse, kein Ergebnis."""
        df = make_runs(distance_km=[3.0, 4.0])

        ergebnis = impute_grouped_calories(df, config)

        assert "_dist_bin" not in ergebnis.columns
        assert "_hr_bin" not in ergebnis.columns

    def test_eingabe_wird_nicht_veraendert(self, make_runs, config):
        """Die Funktion arbeitet auf einer Kopie."""
        df = make_runs(distance_km=[3.0, 4.0], calories=[300.0, np.nan])
        vorher = df.copy()

        impute_grouped_calories(df, config)

        pd.testing.assert_frame_equal(df, vorher)


class TestDistanzklassen:
    """Einteilung in die konfigurierten Distanzklassen."""

    def test_klassengrenzen_sind_linksgeschlossen(self, config):
        """DISTANCE_BINS = [0, 5, 10, 15, 25, 50], right=False.

        5.0 gehört damit in [5, 10) und nicht mehr in [0, 5).
        """
        bins = _build_distance_bins(pd.Series([4.99, 5.0, 9.99, 10.0]), config)

        assert bins.iloc[0].left == 0
        assert bins.iloc[1].left == 5
        assert bins.iloc[2].left == 5
        assert bins.iloc[3].left == 10

    def test_distanz_ausserhalb_der_klassen_wird_nan(self, config):
        """Oberhalb der letzten Klassengrenze gibt es keine Klasse."""
        bins = _build_distance_bins(pd.Series([100.0]), config)

        assert pd.isna(bins.iloc[0])


class TestCountChanged:
    """Zählt die Wirkung des Winsorisings."""

    def test_zaehlt_abweichende_zeilen(self):
        alt = pd.Series([100.0, 200.0, 300.0])
        neu = pd.Series([100.0, 250.0, 350.0])

        assert count_changed(alt, neu) == 2

    def test_gleiche_serien_ergeben_null(self):
        serie = pd.Series([100.0, 200.0])

        assert count_changed(serie, serie.copy()) == 0
