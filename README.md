# DAW Project: Running Data Wrangling from Apple, Garmin and Samsung

The goal in this project is to summarise all of the running workouts from the diffrent watches.

## Folder Structure

The idea behind this folder structure is to be able to add diffrent exports from different times and different watches in an agile way.

```bash
.
├── apple
│   └── 2025-09-19
│       ├── Export.xml
│       ├── export_cda.xml
│       └── workout-routes
│           ├── route_2024-06-25_4.44pm.gpx
│           ├── route_2024-06-25_6.27pm.gpx
│           ├── route_2024-08-22_7.29pm.gpx
│           ├── route_2024-08-22_9.46pm.gpx
│           ├── route_2025-01-29_7.43pm.gpx
│           ├── route_2025-02-04_3.28pm.gpx
│           ├── route_2025-02-14_12.34pm.gpx
│           ├── route_2025-06-12_9.28pm.gpx
│           ├── route_2025-07-29_3.34pm.gpx
│           ├── route_2025-08-05_5.49pm.gpx
│           ├── route_2025-08-16_1.34pm.gpx
│           ├── route_2025-08-21_1.11pm.gpx
│           ├── route_2025-08-21_5.11pm.gpx
│           ├── route_2025-08-23_6.39pm.gpx
│           ├── route_2025-08-26_8.34am.gpx
│           ├── route_2025-09-09_6.13pm.gpx
│           ├── route_2025-09-11_4.50pm.gpx
│           ├── route_2025-09-13_11.57am.gpx
│           ├── route_2025-09-13_2.47pm.gpx
│           ├── route_2025-09-14_11.24am.gpx
│           ├── route_2025-09-14_3.07pm.gpx
│           ├── route_2025-09-17_7.44am.gpx
│           └── route_2025-09-19_8.08am.gpx
└── garmin
    └── 2025-08-22
        └── Activities.csv
```


## Workflow-Orchestrierung mit Snakemake

Die bestehende Python-Pipeline ist zusätzlich in einen Snakemake-Workflow eingebettet.
Das `Snakefile` definiert die Garmin- und Apple-Rohdaten als Inputs und die kombinierten
CSV- und Parquet-Dateien als Outputs.

Die Rohdaten werden automatisch über ihre Ordnerstruktur gefunden. Neue Exporte müssen
dadurch nicht einzeln im `Snakefile` eingetragen werden, solange sie der gleichen Struktur
folgen:

```text
data/garmin/<exportdatum>/Activities.csv
data/apple/<exportdatum>/Export.xml
```

Der Workflow wird ausgeführt mit:

```bash
snakemake --cores 1
```

Für einen Dry Run, bei dem Snakemake den Workflow nur prüft und keine Verarbeitung
ausführt:

```bash
snakemake -n --cores 1
```

Snakemake prüft die Abhängigkeiten zwischen Rohdaten und Ergebnisdateien. Sind die
Outputs bereits vorhanden und aktuell, wird die Pipeline nicht erneut ausgeführt.
Werden Rohdaten geändert oder ergänzt, erkennt Snakemake die Änderung und führt die
betroffene Pipeline erneut aus.

Snakemake ist als Laufzeitabhängigkeit in `requirements.txt` und `pyproject.toml`
definiert. Der von Snakemake erzeugte Arbeitsordner `.snakemake/` wird über
`.gitignore` nicht versioniert.
