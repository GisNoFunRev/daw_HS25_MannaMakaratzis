"""Import der GPX-Routendaten (noch nicht implementiert).

Platzhalter für TODO 9. Unter ``data/apple/<exportdatum>/workout-routes/``
liegen 23 GPX-Dateien mit den GPS-Spuren einzelner Läufe — je Datei eine
Folge von Trackpunkten mit Koordinaten, Höhe, Zeitstempel und
Geschwindigkeit.

Der Import ist aus zwei Gründen vorgesehen:

* Er deckt ein drittes Dateiformat ab (LE1).
* Er ist Voraussetzung für TODO 8: Zwischen den Routenpunkten und den
  Workout-Zusammenfassungen besteht eine echte 1:n-Beziehung über Datum und
  Uhrzeit. Damit lässt sich ein Join fachlich sinnvoll demonstrieren, was mit
  den bisherigen Quellen bewusst nicht möglich war (siehe Kapitel
  "Verknüpfen": Garmin und Apple messen dieselben Läufe nie gleichzeitig,
  weshalb dort konkateniert statt gejoint wird).

Der Dateiname kodiert den Startzeitpunkt, etwa
``route_2025-09-13_2.47pm.gpx``. Er ist damit der naheliegende Join-Schlüssel,
sollte aber gegen den Zeitstempel des ersten Trackpunkts geprüft werden.
"""
