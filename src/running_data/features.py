"""Abgeleitete Variablen (noch nicht implementiert).

Platzhalter für TODO 10 und Teile von TODO 7.

Ausgangslage
------------
Mehrere Grössen werden bereits berechnet, aber nur intern verwendet und
anschliessend verworfen:

* Die **Pace** entsteht in
  :meth:`~running_data.cleaning.validators.DataValidator.validate_pace`, wird
  dort nur zur Plausibilitätsprüfung ausgewertet und nicht gespeichert.
* Die **Distanzklassen** entstehen in
  :func:`~running_data.cleaning.imputation._build_distance_bins` und werden am
  Ende der Imputation wieder entfernt.

Vorgesehene Spalten im Endergebnis
----------------------------------
``pace_min_per_km``
    Minuten pro Kilometer — die für Läufer aussagekräftigste Kennzahl.
``weekday`` / ``month``
    Aus ``date`` abgeleitet, für Trainingsmuster über die Woche und das Jahr.
``distance_category``
    Die bereits intern gebildeten Distanzklassen als sichtbare Spalte.

Zusätzlich aus TODO 7: Reskalierung (Standard/MinMax/Yeo-Johnson), Reshape
zwischen Lang- und Breitformat sowie Zeitreihenfunktionen wie ein gleitender
Mittelwert der Pace.
"""
