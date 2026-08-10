"""Zentrale Projektpfade.

Warum dieses Modul nötig ist
----------------------------
Vor dem Refactoring lag das Notebook im Projektwurzelverzeichnis und alle
Datenpfade waren relativ zum Arbeitsverzeichnis angegeben (z. B.
"data/garmin/*/Activities.csv"). Das funktioniert nur, solange der Code
aus genau diesem Verzeichnis heraus ausgeführt wird.

Da das Notebook jetzt unter notebooks/ liegt und die Module zusätzlich aus
Tests heraus importierbar sein sollen, werden alle Pfade hier absolut aus
dem Ort dieser Datei abgeleitet. Damit ist das Ergebnis unabhängig davon, aus
welchem Verzeichnis heraus gestartet wird.
"""

from pathlib import Path

# Diese Datei liegt in <projekt>/src/running_data/paths.py.
# parents[0] = running_data, parents[1] = src, parents[2] = Projektwurzel.
PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]

# --- Eingangsdaten ----------------------------------------------------------
# Die Rohdaten liegen bewusst ausserhalb der Versionsverwaltung (siehe
# .gitignore); der Ordner ist nach Quelle und Exportdatum gegliedert, damit
# mehrere Exporte nebeneinander bestehen können.
DATA_DIR: Path = PROJECT_ROOT / "data"

# Garmin-Connect-Export: eine CSV je Exportdatum.
GARMIN_GLOB: str = str(DATA_DIR / "garmin" / "*" / "Activities.csv")

# Apple-Health-Export: ein grosses XML je Exportdatum.
APPLE_GLOB: str = str(DATA_DIR / "apple" / "*" / "Export.xml")

# GPS-Spuren der Apple-Workouts, eine GPX-Datei je Lauf.
# Noch ungenutzt — vorgesehen für den GPX-Import (TODO 9).
APPLE_ROUTES_GLOB: str = str(DATA_DIR / "apple" / "*" / "workout-routes" / "*.gpx")

# --- Ausgabedaten -----------------------------------------------------------
# Zielordner für den kombinierten, bereinigten Datensatz.
PROCESSED_DIR: Path = DATA_DIR / "processed"
