"""Zentrale Konfiguration der Datenbereinigung.

Hier stehen sämtliche Schwellenwerte und Schema-Definitionen an einer Stelle.
Fachliche Anpassungen erfolgen ausschliesslich hier und nicht verstreut im Verarbeitungscode.
"""


class DataCleaningConfig:
    """Schwellenwerte für Validierung, Imputation und Winsorising.

    Die Werte sind als Klassenattribute abgelegt und werden über eine Instanz
    (``config = DataCleaningConfig()``) an die Bereinigungsschritte übergeben.
    Jeder Schritt erhält die Konfiguration explizit als Parameter, statt auf
    eine globale Variable zuzugreifen. Das macht die Schritte einzeln
    testbar und ihre Abhängigkeiten sichtbar.
    """

    # --- Distanz (km) -------------------------------------------------------
    # Untergrenze; darunter handelt es sich um Fehlmessungen, nicht um Läufe.
    DISTANCE_MIN: float = 0.05
    # Obergrenze; oberhalb eines Ultramarathons als Gerätefehler behandelt.
    DISTANCE_MAX: float = 60
    # Klassengrenzen für die distanzbasierte Kalorien-Imputation.
    DISTANCE_BINS: list[int] = [0, 5, 10, 15, 25, 50]

    # --- Dauer (Sekunden) ---------------------------------------------------
    DURATION_MIN: int = 60
    DURATION_MAX: int = 18_000  # 5 Stunden

    # --- Pace (min/km) ------------------------------------------------------
    PACE_MIN: float = 2.3  # ~Weltrekordniveau
    PACE_MAX: float = 10.5  # Langsames Joggen / schnelles Gehen

    # --- Herzfrequenz (bpm) -------------------------------------------------
    HR_MIN: int = 80
    HR_MAX: int = 210
    HR_MAX_ABSOLUTE: int = 230
    # Toleranz, bis zu der ein max < avg als Rundungsfehler gilt.
    HR_CONSISTENCY_TOLERANCE: int = 3

    # --- Kalorien -----------------------------------------------------------
    CALORIES_MIN: int = 50
    CALORIES_MAX: int = 3000
    CALORIES_PER_KM_MIN: int = 25
    CALORIES_PER_KM_MAX: int = 120

    # --- Imputation ---------------------------------------------------------
    # Anzahl Herzfrequenz-Quantile je Quelle für die Kalorien-Imputation.
    HR_QUANTILES: int = 4


# --- Schema-Konstanten ------------------------------------------------------

# Kernvariablen vor der Typisierung, wie sie direkt aus dem Import kommen.
# Die Spalte "duration" ist hier noch Rohtext (Garmin: "hh:mm:ss", Apple: Minuten).
RAW_CORE_COLUMNS: list[str] = [
    "date",
    "activity_type",
    "distance_km",
    "duration",
    "calories",
    "avg_heart_rate",
    "max_heart_rate",
    "source",
    "export_date",
]

# Kernvariablen nach der Typisierung, harmonisiert über beide Quellen.
CORE_COLUMNS: list[str] = [
    "date",
    "activity_type",
    "distance_km",
    "duration_sec",
    "calories",
    "avg_heart_rate",
    "max_heart_rate",
    "source",
    "export_date",
]

# Spalten, die numerisch typisiert werden.
NUMERIC_COLUMNS: list[str] = [
    "distance_km",
    "duration_sec",
    "calories",
    "avg_heart_rate",
    "max_heart_rate",
]

# Spalten, die als category typisiert werden (spart Speicher, ermöglicht
# Gruppenanalysen).
CATEGORICAL_COLUMNS: list[str] = ["activity_type", "source"]

# Ohne diese Werte ist ein Lauf nicht auswertbar — betroffene Zeilen fallen weg.
ESSENTIAL_COLUMNS: list[str] = ["distance_km", "duration_sec"]

# Fachlicher Schlüssel eines Laufs; dient der Duplikaterkennung und der
# Uniqueness-Metrik.
DUPLICATE_KEY_COLUMNS: list[str] = ["source", "date", "distance_km", "duration_sec"]

# Herkunftsspalten: Sie dokumentieren den Bereinigungsvorgang, nicht den Lauf.
# Ein leeres imputation_level heisst "musste nicht imputiert werden" — also der
# Idealfall — und darf deshalb nicht als fehlender Wert in die Completeness
# eingehen. calories_imputed ist umgekehrt immer gefüllt und liefert damit
# konstant 1.0, also ebenfalls keine Aussage über die Datenqualität.
PROVENANCE_COLUMNS: list[str] = ["calories_imputed", "imputation_level"]
