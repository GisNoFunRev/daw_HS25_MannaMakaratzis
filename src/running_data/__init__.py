"""Data-Wrangling-Pipeline für Laufdaten aus Garmin Connect und Apple Health.

Das Paket bündelt die gesamte Verarbeitungslogik, die zuvor direkt im
Quarto-Notebook stand. Das Notebook (``notebooks/data_wrangling.qmd``) ruft
diese Module nur noch auf und stellt die Ergebnisse dar.

Aufbau des Pakets
-----------------
``config``
    Zentrale Schwellenwerte und Schema-Konstanten.
``paths``
    Projektpfade, unabhängig vom aktuellen Arbeitsverzeichnis.
``logging_setup``
    Einrichtung des Loggings (nur vom Notebook aufzurufen).
``ingest``
    Rohdaten-Import je Quelle (Garmin CSV, Apple XML, GPX).
``cleaning``
    Typisierung, Validatoren, Imputation und die einzelnen Bereinigungsschritte.
``pipeline``
    Pipeline-Pattern, Bereinigungsbericht und Datenqualitäts-Metriken.
``combine``
    Zusammenführung der bereinigten Quellen.
``export``
    Persistierung des Ergebnisses (Parquet und CSV).
``features``
    Abgeleitete Variablen (noch nicht implementiert).

Die öffentliche API wird in Phase 6 dieses Refactorings ergänzt, sobald alle
Module vorhanden sind.
"""

__version__ = "0.1.0"
