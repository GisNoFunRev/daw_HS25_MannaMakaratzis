"""Import der Apple-Health-Workouts (LE1).

Datenquelle
-----------
XML-Export aus der Apple-Health-App, abgelegt unter
``data/apple/<exportdatum>/Export.xml``.

Besonderheiten des Formats
--------------------------
* **Dateigrösse**: Der Export umfasst mehrere hundert Megabyte, weil er
  sämtliche Gesundheitsdaten enthält. Die Datei wird deshalb mit
  ``lxml.etree.iterparse`` im Streaming-Verfahren gelesen und jedes
  verarbeitete Element sofort wieder freigegeben, statt den gesamten Baum in
  den Speicher zu laden.
* **Verschachtelung**: Die interessanten Messwerte stehen nicht als Attribute
  am ``<Workout>``-Element, sondern in untergeordneten
  ``<WorkoutStatistics>``-Elementen, die je nach Workout-Typ variieren.

Wie schon beim Garmin-Import wird hier ausschliesslich gelesen: keine
Einheitenumrechnung, keine Bereinigung. Fehlende Messwerte bleiben als leerer
String stehen und werden erst bei der Typisierung zu ``NaN``.
"""

import glob
from pathlib import Path
from typing import Any

import pandas as pd
from lxml import etree  # lxml wegen der Grösse der Apple-Exportdatei

from ..logging_setup import get_logger
from ..paths import APPLE_GLOB

logger = get_logger(__name__)

#: Statistik-Typen, aus denen die Distanz gelesen wird. Apple verwendet je
#: nach Sportart einen anderen Identifier für dieselbe Grösse.
DISTANCE_STATISTIC_TYPES: tuple[str, ...] = (
    "HKQuantityTypeIdentifierDistanceWalkingRunning",
    "HKQuantityTypeIdentifierDistanceCycling",
)

CALORIES_STATISTIC_TYPE = "HKQuantityTypeIdentifierActiveEnergyBurned"
HEART_RATE_STATISTIC_TYPE = "HKQuantityTypeIdentifierHeartRate"

#: Präfix, das Apple jedem Aktivitätstyp voranstellt und das entfernt wird,
#: damit aus "HKWorkoutActivityTypeRunning" schlicht "Running" wird.
ACTIVITY_TYPE_PREFIX = "HKWorkoutActivityType"


def _extract_workout(elem: etree._Element, export_date: str) -> dict[str, Any]:
    """Liest ein einzelnes ``<Workout>``-Element in ein flaches Dictionary.

    Die Messwerte werden als leerer String vorbelegt und nur überschrieben,
    wenn das Workout die entsprechende Statistik mitbringt. Damit hat jede
    Zeile dieselben Schlüssel, unabhängig davon, welche Metriken die Uhr
    aufgezeichnet hat.

    Args:
        elem: Das ``<Workout>``-Element aus dem XML-Baum.
        export_date: Exportdatum aus dem Ordnernamen.

    Returns:
        Ein Dictionary mit den Rohwerten eines Workouts.
    """
    workout: dict[str, Any] = {
        "source": "apple",
        "export_date": export_date,
        "activity_type": elem.get("workoutActivityType", "").replace(
            ACTIVITY_TYPE_PREFIX, ""
        ),
        "date": elem.get("startDate", ""),
        # Einheit bleibt roh (Apple liefert die Dauer üblicherweise in Minuten).
        "duration": elem.get("duration", ""),
        # Werden aus den WorkoutStatistics unten gefüllt.
        "distance": "",
        "calories": "",
        "avg_heart_rate": "",
        "max_heart_rate": "",
    }

    for stats_elem in elem.findall("WorkoutStatistics"):
        stats_type = stats_elem.get("type", "")

        if stats_type in DISTANCE_STATISTIC_TYPES:
            workout["distance"] = stats_elem.get("sum", "")
        elif stats_type == CALORIES_STATISTIC_TYPE:
            workout["calories"] = stats_elem.get("sum", "")
        elif stats_type == HEART_RATE_STATISTIC_TYPE:
            workout["avg_heart_rate"] = stats_elem.get("average", "")
            workout["max_heart_rate"] = stats_elem.get("maximum", "")

    return workout


def _log_import_statistics(df: pd.DataFrame) -> None:
    """Protokolliert, wie viele Workouts brauchbare Kernwerte mitbringen.

    Reine Information zur Nachvollziehbarkeit des Imports — der DataFrame
    wird dabei nicht verändert.
    """
    if df.empty:
        logger.warning("Apple: Import ergab keine Workouts.")
        return

    non_empty_distance = df["distance"].replace("", pd.NA).notna().sum()
    non_empty_duration = df["duration"].replace("", pd.NA).notna().sum()
    logger.info(
        "Apple: Import abgeschlossen. Workouts: %d | distance vorhanden: %d | "
        "duration vorhanden: %d",
        len(df),
        non_empty_distance,
        non_empty_duration,
    )


def import_apple_workouts(xml_path: str = APPLE_GLOB) -> pd.DataFrame:
    """Importiert alle Apple-Health-Workouts aus den XML-Exporten.

    Args:
        xml_path: Glob-Muster der zu lesenden XML-Dateien. Standard ist
            :data:`running_data.paths.APPLE_GLOB`.

    Returns:
        Alle Workouts aller Exporte in einem DataFrame mit den Rohspalten
        ``source``, ``export_date``, ``activity_type``, ``date``,
        ``duration``, ``distance``, ``calories``, ``avg_heart_rate`` und
        ``max_heart_rate``. Leerer DataFrame, wenn keine Datei gefunden wurde.
    """
    xml_files = glob.glob(xml_path)
    apple_workouts: list[dict[str, Any]] = []

    for xml_file in xml_files:
        export_date = Path(xml_file).parent.name
        logger.info("Apple: verarbeite %s", xml_file)

        for event, elem in etree.iterparse(xml_file, events=("start", "end")):
            if event == "end" and elem.tag == "Workout":
                apple_workouts.append(_extract_workout(elem, export_date))
                elem.clear()  # Speicher des verarbeiteten Elements freigeben

    df = pd.DataFrame(apple_workouts)
    _log_import_statistics(df)
    return df
