from glob import glob


'''
Sucht automatisch alle vorhandenen Garmin- und Apple-Rohdaten.

glob() löst die *-Muster auf und erstellt daraus Listen mit den konkreten
Dateipfaden. Neue Exporte müssen dadurch nicht manuell im Snakefile
eingetragen werden, solange sie der gleichen Ordnerstruktur folgen.

Beispiel:
data/garmin/*/Activities.csv

findet unter anderem:
data/garmin/2025-08-22/Activities.csv
data/garmin/2026-08-13/Activities.csv
'''

garmin_files = glob("data/garmin/*/Activities.csv")
apple_files = glob("data/apple/*/Export.xml")


'''
Gesamtziel des Workflows.

"rule all" beschreibt, welche Dateien am Ende des Workflows vorhanden
sein sollen.

Die Dateien stehen unter "input", weil rule all sie nicht selbst erzeugt,
sondern sie benötigt, um als erfüllt zu gelten. Dieselben Dateien sind
Outputs der Rule, die sie tatsächlich erzeugt.
'''

rule all:
    input:
        "data/processed/combined_runs.csv",
        "data/processed/combined_runs.parquet"


'''
Führt die bestehende Python-Pipeline aus.

Input:
Alle durch glob() gefundenen Garmin- und Apple-Rohdaten.
Dadurch kennt Snakemake die konkreten Quelldateien und kann erkennen,
wenn sich eine davon verändert.

Output:
Der kombinierte Datensatz als CSV und Parquet.

Shell:
Startet die bestehende running_data-Pipeline. Die Glob-Muster werden
an die Pipeline übergeben, welche damit selbst alle passenden Rohdaten
einliest.
'''

rule running_pipeline:
    input:
        garmin=garmin_files,
        apple=apple_files

    output:
        csv="data/processed/combined_runs.csv",
        parquet="data/processed/combined_runs.parquet"

    shell:
        """
        python -m running_data \
            --garmin "data/garmin/*/Activities.csv" \
            --apple "data/apple/*/Export.xml" \
            --output data/processed
        """
