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


Weitere geplante Transformationen
---------------------------------
Reskalierung (Standard/MinMax/Yeo-Johnson), Reshape zwischen Lang- und
Breitformat sowie Zeitreihenfunktionen wie ein gleitender Mittelwert der Pace
gehören zu TODO 7 und sind nicht Teil dieses Feature-Engineering-Schritts.
"""


import pandas as pd

def add_features(df: pd.DataFrame) -> pd.DataFrame:


    out = df.copy()

    out["duration_min"] = out["duration_sec"]/60
    out["pace_min_per_km"] = out["duration_min"] / out["distance_km"]

    return out

