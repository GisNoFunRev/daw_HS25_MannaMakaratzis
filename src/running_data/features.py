"""Abgeleitete Variablen für die Analyse der Laufdaten.

Feature-Auswahl
---------------
Es werden nur Variablen ergänzt, die für die Interpretation von Laufdaten
einen direkten fachlichen Nutzen haben.

pace_min_per_km
    Pace in Minuten pro Kilometer. Sie kombiniert Dauer und Distanz zu einer
    zentralen und im Laufsport üblichen Kennzahl.

duration_min
    Dauer in Minuten. Die harmonisierte Variable duration_sec bleibt die
    technische Basis, Minuten sind für die Interpretation eines Laufs jedoch
    besser lesbar.

Bewusst nicht ergänzt
---------------------
Wochentag und Monat werden nicht als eigene Features gespeichert, da sie für
die vorliegende Analyse keinen zusätzlichen Nutzen bieten und jederzeit aus
date abgeleitet werden können.

Herzfrequenzzonen werden ebenfalls nicht abgeleitet. Trainingszonen sind
individuell und benötigen zusätzliche personenbezogene Parameter bzw.
individuell bestimmte Schwellenwerte, die in den vorliegenden Daten nicht
enthalten sind.

Die intern verwendeten Herzfrequenz-Quantile dienen ausschliesslich der
Kalorien-Imputation und werden deshalb nicht als Trainingsfeatures
interpretiert oder im finalen Datensatz gespeichert.
"""

import pandas as pd


def add_features(df: pd.DataFrame) -> pd.DataFrame:
    """Ergänzt interpretierbare Dauer- und Pace-Variablen.

    Args:
        df: Bereinigter Laufdatensatz mit den numerischen Spalten
            duration_sec und distance_km.

    Returns:
        Kopie des vollständigen Eingabedatensatzes mit duration_min in
        Minuten und pace_min_per_km in Minuten pro Kilometer. Bei einer
        Distanz kleiner oder gleich null bleibt die Pace fehlend, weil sie
        fachlich nicht definiert ist.

    Raises:
        KeyError: Wenn duration_sec oder distance_km fehlt.
    """

    out = df.copy()

    out["duration_min"] = out["duration_sec"] / 60
    valid_distance = out["distance_km"].where(out["distance_km"] > 0)
    out["pace_min_per_km"] = out["duration_min"] / valid_distance

    return out
