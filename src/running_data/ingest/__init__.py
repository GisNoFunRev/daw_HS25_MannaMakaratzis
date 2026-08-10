"""Rohdaten-Import (LE1).

Jede Datenquelle hat ein eigenes Modul, weil sich die Formate grundlegend
unterscheiden: Garmin liefert semikolongetrennte CSV-Dateien in Latin-1,
Apple Health ein einzelnes, sehr grosses XML.

Die Funktionen dieses Subpakets bereinigen bewusst **nicht**. Sie lesen die
Rohwerte ein und vereinheitlichen lediglich die Spaltennamen, damit beide
Quellen anschliessend dieselbe Bereinigungspipeline durchlaufen können.
"""
