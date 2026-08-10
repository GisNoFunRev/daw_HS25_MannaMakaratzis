"""Pipeline-Infrastruktur (LE5).

``core``
    Das Pipeline-Pattern selbst: ``CleaningStep`` und ``DataCleaningPipeline``.
    Kennt keine konkreten Bereinigungsschritte.
``factory``
    Baut die konkrete, 8-stufige Standard-Pipeline. Dass Garmin und Apple
    identisch bereinigt werden, ist dadurch per Konstruktion garantiert und
    nicht mehr eine Frage der Sorgfalt beim Kopieren.
``report``
    Protokolliert je Schritt, wie viele Zeilen entfernt wurden.
``quality``
    Misst die Qualität des Ergebnisses anhand der vier Data-Quality-Dimensionen.
"""
