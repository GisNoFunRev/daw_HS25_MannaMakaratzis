"""Zusammenführung der bereinigten Quellen (LE4).

Warum konkateniert und nicht gejoint wird
-----------------------------------------
Ein Join setzt eine Beziehung zwischen den Datensätzen voraus — dieselbe
Entität, beschrieben durch unterschiedliche Attribute. Diese Beziehung besteht
hier nicht: Eine Person trägt beim Laufen entweder die Garmin- oder die
Apple-Uhr, nie beide gleichzeitig. Jeder Lauf existiert also in genau einer
Quelle, und es gibt keine gemeinsamen Schlüssel, über die sich Zeilen paaren
liessen.

Fachlich richtig ist deshalb die **Konkatenation**: Beide Quellen liefern
gleichartige Beobachtungen, die untereinander gehängt werden. Ein Join würde
hier ein Kreuzprodukt oder überwiegend leere Zeilen erzeugen.

Ein echter Join wird an anderer Stelle möglich: Zwischen den GPX-Routenpunkten
und den Workout-Zusammenfassungen besteht eine 1:n-Beziehung über den
Zeitstempel (TODO 8/9).

Der Import und diese Zusammenführung sind der Bereinigungspipeline bewusst
vor- beziehungsweise nachgelagert: Die Pipeline arbeitet je Quelle, weil sich
die Bereinigungsentscheidungen auf eine einzelne Quelle beziehen.
"""

import pandas as pd

from .logging_setup import get_logger

logger = get_logger(__name__)


def concat_sources(
    frames: list[pd.DataFrame], sort_by: str = "date"
) -> pd.DataFrame:
    """Hängt die bereinigten Datensätze mehrerer Quellen untereinander.

    Args:
        frames: Die zusammenzuführenden DataFrames, üblicherweise je einer
            pro Quelle.
        sort_by: Spalte, nach der das Ergebnis sortiert wird. Die Sortierung
            ist stabil, die Reihenfolge innerhalb desselben Zeitstempels
            entspricht also der Reihenfolge in ``frames``.

    Returns:
        Der kombinierte, chronologisch sortierte Datensatz.

    Note:
        Es wird bewusst **nicht** über Quellgrenzen hinweg dedupliziert. Zwei
        Läufe mit identischen Kennzahlen aus verschiedenen Quellen sind zwei
        eigenständige Beobachtungen; Duplikate innerhalb einer Quelle hat die
        Pipeline bereits entfernt.
    """
    combined = pd.concat(frames, ignore_index=True).sort_values(
        sort_by, kind="stable"
    )

    logger.info(
        "Zusammenführung: %s → %d Zeilen kombiniert",
        " + ".join(str(len(f)) for f in frames),
        len(combined),
    )
    return combined
