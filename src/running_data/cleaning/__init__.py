"""Bereinigung und Transformation der Rohdaten (LE2).

Das Subpaket trennt vier Verantwortlichkeiten:

validators
    Prüfregeln, die eine boolesche Maske zurückgeben — sie verändern nichts.
imputation
    Strategien zum Auffüllen fehlender Werte.
steps
    Die quellenunabhängigen Bereinigungsschritte der Pipeline.
garmin_typing / apple_typing
    Quellenspezifische Typisierung und Einheiten-Normalisierung. Nur hier
    darf Wissen über eine einzelne Quelle stehen; ab steps sind beide
    Datensätze auf dasselbe Schema harmonisiert.
"""
