# DAW-Projekt: Data Wrangling von Laufdaten aus Garmin und Apple Health

*Aufbereitung und Zusammenführung heterogener Laufdaten in einer reproduzierbaren Python-Pipeline*

## Projektziel

Ziel des Projekts ist die Entwicklung einer reproduzierbaren Data-Wrangling-Pipeline, die Laufdaten aus Garmin Connect und Apple Health in einen gemeinsamen, analysierbaren Datensatz überführt.

Die beiden Datenquellen enthalten vergleichbare Informationen zu Laufaktivitäten, unterscheiden sich jedoch in Dateiformat, Struktur, Benennung, Datentypen und Einheiten. Die Pipeline übernimmt deshalb den vollständigen Aufbereitungsprozess von den Rohdaten bis zum exportierten Datensatz:

- Import von Garmin-CSV- und Apple-Health-XML-Daten
- Filterung und Reduktion auf die für die Analyse relevanten Laufdaten
- Harmonisierung von Schema, Datentypen und Einheiten
- Bereinigung unvollständiger, fehlerhafter, doppelter und unplausibler Daten
- nachvollziehbare Imputation fehlender Werte
- Beurteilung der Datenqualität
- fachlich begründete Zusammenführung der harmonisierten Laufdaten durch Konkatenation
- Berechnung ausgewählter abgeleiteter Variablen
- Export des finalen Datensatzes als Parquet und CSV

Die Verarbeitung ist modular in Python implementiert, automatisiert testbar und unabhängig vom Notebook ausführbar. Damit entsteht aus zwei heterogenen Rohdatenquellen ein einheitlicher Datensatz, dessen Aufbereitung nachvollziehbar und reproduzierbar ist.

## Verarbeitungskette

```text
Garmin CSV ──┐
             ├─> Import -> Typisierung -> Cleaning ─┐
Apple XML ───┘                                      │
                                                    ├─> Concat -> Features -> Export
                                                    │
                                   Quality + Report ┘
```

Die Verarbeitung erfolgt zunächst getrennt nach Datenquelle, weil Garmin und Apple unterschiedliche Rohformate verwenden. Nach der quellenspezifischen Typisierung liegen beide Datensätze im selben Schema vor und können mit derselben achtstufigen Bereinigungspipeline verarbeitet werden. Erst danach werden die bereinigten Läufe zu einem gemeinsamen Datensatz zusammengeführt.

### Schritt 1: Import

#### Garmin

- CSV-Import mit automatischer Erkennung des Trennzeichens, insbesondere `;` und `,`
- Fallback über mehrere Encodings
- Vereinheitlichung der Spaltennamen
- Exportdatum wird aus der Ordnerstruktur übernommen

#### Apple Health

- XML-Import mit `lxml.etree.iterparse`
- Streaming-Verarbeitung statt Laden des gesamten XML-Baums
- Auslesen verschachtelter `WorkoutStatistics`
- Exportdatum wird aus der Ordnerstruktur übernommen

Die Importmodule beschränken sich bewusst auf das Einlesen und die grundlegende Zuordnung der Rohdaten. Fachliche Bereinigung, Typisierung und Einheitenumrechnung erfolgen erst in den nachfolgenden Verarbeitungsschritten. Dadurch bleiben Import und Datenbereinigung klar voneinander getrennt.

### Schritt 2: Typisierung und Harmonisierung

Garmin und Apple werden vor der gemeinsamen Cleaning-Pipeline in dasselbe `CORE_COLUMNS`-Schema überführt. Die quellenspezifischen Schritte sind im Code vollständig getrennt, weil beide Exporte unterschiedliche Eigenheiten besitzen.

#### Garmin

Die Garmin-Aufbereitung führt folgende Schritte aus:

1. Es werden nur Aktivitäten behalten, deren `activity_type` den Wortstamm `run` enthält. Dadurch werden auch Varianten wie `Running`, `Trail Running` oder `Treadmill Running` erfasst.
2. Der umfangreiche Garmin-Export wird auf die neun benötigten Rohvariablen aus `RAW_CORE_COLUMNS` reduziert. Fehlende Kernspalten werden mit `pd.NA` ergänzt, damit das Schema auch bei leicht unterschiedlichen Exportversionen stabil bleibt.
3. `export_date` wird in einen Datumswert umgewandelt.
4. `date` wird mit `format="mixed"` geparst. Dadurch können unterschiedliche Garmin-Exportformate verarbeitet werden. Für europäische Datumsangaben wird `dayfirst=True` verwendet, damit Tag und Monat korrekt interpretiert werden.
5. Die Rohspalte `duration` wird aus `hh:mm:ss`, `mm:ss` oder bereits numerischen Werten in Sekunden umgerechnet und als `duration_sec` gespeichert.
6. Falls die Distanzwerte oberhalb der festgelegten Heuristik liegen, werden sie als Meter interpretiert und in Kilometer umgerechnet.
7. `distance_km`, `duration_sec`, `calories`, `avg_heart_rate` und `max_heart_rate` werden numerisch typisiert. Nicht interpretierbare Werte werden zu fehlenden Werten.
8. `activity_type` und `source` werden als kategoriale Variablen typisiert.
9. Der Datensatz wird exakt auf `CORE_COLUMNS` reduziert. Die Garmin-Rohspalte `duration` wird dabei entfernt.

#### Apple Health

Die Apple-Aufbereitung führt folgende Schritte aus:

1. Es werden nur Aktivitäten behalten, deren `activity_type` `running` enthält.
2. Die neutralen Importspalten werden auf das gemeinsame Schema umbenannt: `distance` wird zu `distance_km` und `duration` zu `duration_sec`, sofern die Zielspalten noch nicht vorhanden sind.
3. `date` wird als Zeitstempel interpretiert. Vorhandene Zeitzonen-Offsets werden entfernt, ohne die Ortszeit des Laufs zu verschieben. Anschliessend wird der Zeitstempel einheitlich formatiert.
4. `export_date` wird in einen Datumswert umgewandelt.
5. Die numerischen Kernvariablen werden numerisch typisiert. Fehlt eine erwartete numerische Spalte, wird sie mit `NaN` ergänzt.
6. Falls die mediane Dauer im für Minuten typischen Bereich liegt, wird `duration_sec` von Minuten in Sekunden umgerechnet.
7. Falls Distanzwerte oberhalb der festgelegten Heuristik liegen, werden sie als Meter interpretiert und in Kilometer umgerechnet.
8. `activity_type` und `source` werden als kategoriale Variablen typisiert.
9. Fehlende Spalten aus `CORE_COLUMNS` werden ergänzt und der Datensatz wird auf die gemeinsame Spaltenreihenfolge gebracht.

Nach diesem Schritt besitzen beide Quellen dieselben Kernvariablen in derselben Reihenfolge und mit harmonisierten Einheiten. Die Transformation umfasst damit nicht nur eine Umbenennung von Spalten, sondern auch Filterung, Datentypkonvertierung, Datumsverarbeitung und Einheitenumrechnung. Erst danach durchlaufen beide Quellen dieselbe Cleaning-Pipeline.

### Schritt 3: Bereinigungspipeline

Nach der Typisierung durchlaufen beide Quellen dieselbe Standardpipeline. Sie besteht aus acht aufeinanderfolgenden Schritten, die jeweils eine klar abgegrenzte Aufgabe übernehmen:

| **Schritt** | **Zweck** |
|---|---|
| Date Imputation | Fehlende Laufzeitpunkte werden aus `export_date` ergänzt, sofern dafür ein verwendbares Exportdatum vorhanden ist. |
| Remove Duplicates | Doppelte Laufaktivitäten innerhalb derselben Quelle werden anhand der definierten Duplikatspalten erkannt und entfernt. |
| Validate Essentials | Zeilen werden entfernt, wenn zentrale Angaben wie Distanz oder Dauer fehlen oder nicht auswertbar sind. |
| Plausibility Checks | Distanz, Dauer und die daraus berechnete Pace werden mit den in `config.py` definierten Plausibilitätsgrenzen verglichen. |
| Heart Rate Cleaning | Unplausible oder widersprüchliche Herzfrequenzwerte werden bereinigt. Fehlende Herzfrequenzwerte werden innerhalb der jeweiligen Quelle imputiert, sofern geeignete Vergleichswerte vorhanden sind. |
| Calories Imputation | Fehlende oder ungültige Kalorienwerte werden anhand vergleichbarer Läufe imputiert. Extreme Werte werden zusätzlich durch Winsorising auf robuste Grenzen begrenzt. |
| Final HR Sweep | Nach der vorherigen Bereinigung verbleibende physiologisch unplausible Herzfrequenzwerte führen dazu, dass die betroffene Zeile entfernt wird. |
| Finalize Types | Die vorgesehenen kategorialen Spalten werden abschliessend auf ihre endgültigen Datentypen gesetzt. |

Die Pipeline unterscheidet ausserdem zwischen **kritischen** und **unkritischen** Schritten. Wenn ein kritischer Schritt fehlschlägt, wird die Verarbeitung abgebrochen, weil das Ergebnis danach nicht mehr zuverlässig weiterverarbeitet werden kann. Bei einem unkritischen Fehler wird der Fehler protokolliert und die Pipeline setzt die Verarbeitung mit dem letzten gültigen Datenstand fort.

### Schritt 4: Zusammenführen der Quellen

Nach der Bereinigung werden die Garmin- und Apple-Daten bewusst **konkateniert und nicht gejoint**.

Ein Join setzt voraus, dass Zeilen beider Tabellen dieselbe Entität beschreiben und über einen Schlüssel verbunden werden können. Das ist hier nicht der Fall. Die Garmin- und Apple-Datensätze enthalten unterschiedliche Läufe und stellen damit gleichartige Beobachtungen dar, die untereinander angefügt werden müssen.

```python
combined = concat_sources([garmin_clean, apple_clean])
```

Das Ergebnis wird mit `pd.concat()` zeilenweise kombiniert und anschliessend stabil nach `date` sortiert. Damit sind auch das Zusammenführen und Sortieren explizite Bestandteile der Transformation. Eine quellenübergreifende Deduplizierung findet bewusst nicht statt.

### Schritt 5: Feature Engineering

Beim Feature Engineering werden nur Variablen ergänzt, die sich direkt aus den vorhandenen Messwerten berechnen lassen und die Interpretation der Läufe erleichtern.

#### Feature: `duration_min`

```text
duration_min = duration_sec / 60
```

Die technische Harmonisierung erfolgt in Sekunden. Für Menschen ist eine Laufdauer in Minuten jedoch leichter lesbar. `duration_sec` bleibt als technische Basis erhalten.

#### Feature: `pace_min_per_km`

```text
pace_min_per_km = duration_min / distance_km
```

Die Pace beschreibt, wie viele Minuten durchschnittlich für einen Kilometer benötigt werden. Sie ist eine zentrale Kennzahl im Laufsport und macht Läufe unterschiedlicher Distanz direkt vergleichbar.

**Wichtig für Nicht-Läufer:** Bei der Pace bedeutet ein **kleinerer Wert ein höheres Lauftempo**. Eine Pace von `5.0 min/km` ist also schneller als `6.0 min/km`.

> **Bewusst nicht als Feature umgesetzt: Herzfrequenzzonen**  
> Sinnvolle Trainingszonen sind individuell und benötigen zusätzliche personenbezogene Informationen oder individuell bestimmte Schwellenwerte. Diese Informationen sind in den vorliegenden Aktivitätsdaten nicht zuverlässig vorhanden. Die intern verwendeten Herzfrequenz-Quantile dienen ausschliesslich der Kalorien-Imputation und werden nicht als Trainingszonen interpretiert.

### Schritt 6: Export

Der finale Datensatz wird in zwei Dateiformaten gespeichert, die unterschiedliche Zwecke erfüllen:

- **Parquet** wird als primäres Format für die weitere Verarbeitung verwendet. Datentypen wie Zeitstempel und Kategorien bleiben erhalten.
- **CSV** dient als einfach lesbare Kontrollkopie. Beim CSV-Format gehen Datentypinformationen verloren.

Standardausgabe:

```text
data/processed/
├── combined_runs.csv
└── combined_runs.parquet
```

## Finales Datenschema

| **Spalte** | **Bedeutung** |
|---|---|
| `date` | Zeitpunkt des Laufs |
| `activity_type` | Aktivitätstyp, nach dem Filtern typischerweise Running |
| `distance_km` | Zurückgelegte Distanz in Kilometern |
| `duration_sec` | Harmonisierte Laufdauer in Sekunden |
| `calories` | Gemessener oder imputierter Energieverbrauch in Kilokalorien |
| `avg_heart_rate` | Durchschnittliche Herzfrequenz während des Laufs in Schlägen pro Minute |
| `max_heart_rate` | Maximale Herzfrequenz während des Laufs in Schlägen pro Minute |
| `source` | Herkunft des Datensatzes, `garmin` oder `apple` |
| `export_date` | Datum des jeweiligen Geräteexports |
| `calories_imputed` | Kennzeichnet, ob der Kalorienwert durch die Pipeline ersetzt wurde |
| `imputation_level` | Stufe der verwendeten Kalorien-Imputation. Leer bedeutet, dass keine Imputation nötig war |
| `duration_min` | Aus `duration_sec` abgeleitete Laufdauer in Minuten |
| `pace_min_per_km` | Durchschnittlich benötigte Minuten pro Kilometer |

## Fehlende Werte und Kalorien-Imputation

Fehlende oder als ungültig erkannte Kalorienwerte werden nicht mit einem einzigen globalen Durchschnittswert ersetzt. Stattdessen sucht die Pipeline zuerst nach möglichst vergleichbaren Läufen und verwendet innerhalb dieser Gruppe den Median als Ersatzwert.

Die Imputation arbeitet mit einer vierstufigen Fallback-Kette:

| **Level** | **Vergleichsgruppe** |
|---|---|
| `level3` | gleiche Quelle + Distanzklasse + Herzfrequenz-Quantil |
| `level2` | gleiche Quelle + Distanzklasse |
| `level1` | gleiche Quelle |
| `level0` | gesamter Datensatz |

Je spezifischer die Gruppe, desto ähnlicher sind die Läufe. Falls eine Gruppe keinen verwendbaren Vergleichswert enthält, fällt die Pipeline automatisch auf die nächstgröbere Ebene zurück.

### Begründung der Imputationsmethode

Die Wahl der gruppenbasierten Median-Imputation ist bewusst. Für den vorliegenden Datensatz ist sie ein **robuster, transparenter und reproduzierbarer Ansatz**, ohne mehr statistische Genauigkeit vorzutäuschen, als die vorhandenen Daten erlauben.

- Der **Median** reagiert deutlich weniger empfindlich auf einzelne ungewöhnlich hohe oder tiefe Kalorienwerte als der Mittelwert.
- Die **hierarchische Gruppenbildung** nutzt zuerst möglichst ähnliche Läufe. Quelle, Distanzklasse und Herzfrequenz tragen Informationen über Messsystem, Laufumfang und Belastung und werden deshalb berücksichtigt, bevor auf gröbere Vergleichsgruppen zurückgefallen wird.
- Die **Fallback-Kette** verhindert, dass eine zu kleine oder leere Vergleichsgruppe die Imputation blockiert.
- Mit `calories_imputed` und `imputation_level` bleibt für jede betroffene Zeile nachvollziehbar, **ob und auf welcher Ebene** ein Wert ersetzt wurde. Die Imputation wird damit nicht als ursprüngliche Messung ausgegeben.
- Das Verfahren ist **deterministisch**: Derselbe Input und dieselbe Konfiguration erzeugen dasselbe Resultat, was für eine reproduzierbare Data-Wrangling-Pipeline wichtig ist.

Der Ansatz wird bewusst nicht als allgemein „wissenschaftlich beste“ Imputationsmethode bezeichnet. Es handelt sich um eine einfache Single-Imputation und nicht um ein statistisches Modell, das die Unsicherheit fehlender Werte explizit schätzt. Für das Ziel dieses Projekts: einen kleinen heterogenen Aktivitätsdatensatz nachvollziehbar zu bereinigen: steht deshalb die robuste und überprüfbare Verarbeitung im Vordergrund.

Die Hilfsvariablen für Distanz- und Herzfrequenzklassen werden nur intern verwendet und danach wieder entfernt.

## Datenqualität

Nach Abschluss der Bereinigung wird die Datenqualität für Garmin und Apple getrennt beurteilt. Diese Prüfung verändert die Daten nicht mehr, sondern beschreibt den Zustand des bereinigten Datensatzes anhand mehrerer Qualitätsdimensionen.

Technisch ist diese Qualitätsprüfung **kein neunter Cleaning-Step**. Nach den acht Bereinigungsschritten ruft `run_pipeline()` für jede bereinigte Quelle

```python
DataQualityChecker.assess_quality(cleaned, config)
```

auf. Die Implementierung liegt in `src/running_data/pipeline/quality.py`.

| **Dimension** | **Frage** |
|---|---|
| Completeness | Sind die erwarteten Werte vorhanden? |
| Validity | Liegen Distanz, Dauer, Pace und Herzfrequenz in plausiblen Bereichen? |
| Consistency | Sind zusammengehörige Werte logisch widerspruchsfrei, zum Beispiel `max_heart_rate >= avg_heart_rate`? |
| Uniqueness | Enthält der Datensatz doppelte Läufe? |

Die Herkunftsspalten `calories_imputed` und `imputation_level` werden bei der Completeness bewusst nicht wie normale Messvariablen behandelt. Ein leeres `imputation_level` bedeutet, dass der ursprüngliche Kalorienwert vollständig war und nicht imputiert werden musste.

Zusätzlich erzeugt die Pipeline für jede Quelle einen `CleaningReport`. Dieser dokumentiert pro Verarbeitungsschritt die Zeilenzahl vor und nach dem Schritt und bildet damit einen Audit Trail der Bereinigung.

## Projektstruktur

```text
.
├── data/
│   ├── apple/
│   │   └── <export-date>/
│   │       ├── Export.xml
│   │       └── workout-routes/
│   ├── garmin/
│   │   └── <export-date>/
│   │       └── Activities.csv
│   ├── interim/
│   └── processed/
│       ├── combined_runs.csv
│       └── combined_runs.parquet
├── notebooks/
│   ├── data_wrangling.ipynb
│   └── data_wrangling.qmd
├── src/
│   └── running_data/
│       ├── cleaning/
│       │   ├── apple_typing.py
│       │   ├── garmin_typing.py
│       │   ├── imputation.py
│       │   ├── steps.py
│       │   └── validators.py
│       ├── ingest/
│       │   ├── apple.py
│       │   ├── garmin.py
│       │   └── gpx.py
│       ├── pipeline/
│       │   ├── core.py
│       │   ├── factory.py
│       │   ├── quality.py
│       │   ├── report.py
│       │   └── run.py
│       ├── combine.py
│       ├── config.py
│       ├── export.py
│       ├── features.py
│       ├── logging_setup.py
│       ├── paths.py
│       ├── __init__.py
│       └── __main__.py
├── tests/
│   ├── fixtures/
│   │   ├── apple/
│   │   └── garmin/
│   ├── conftest.py
│   ├── test_export.py
│   ├── test_garmin_typing.py
│   ├── test_imputation.py
│   ├── test_pipeline_core.py
│   ├── test_quality.py
│   ├── test_run_pipeline.py
│   ├── test_schema.py
│   └── test_validators.py
├── Snakefile
├── pyproject.toml
├── requirements.txt
├── requirements-dev.txt
└── README.md
```

### Module und Verantwortlichkeiten

| **Modul** | **Verantwortung** |
|---|---|
| `ingest/garmin.py` | Import der Garmin-CSV-Exporte |
| `ingest/apple.py` | Speicherarmer Import der Apple-Health-XML-Exporte |
| `ingest/gpx.py` | Platzhalter für den noch nicht implementierten GPX-Import |
| `cleaning/garmin_typing.py` | Garmin-Filterung, Schema-Reduktion, Typisierung und Einheitenharmonisierung |
| `cleaning/apple_typing.py` | Apple-Filterung, Umbenennung, Typisierung und Einheitenharmonisierung |
| `cleaning/validators.py` | Fachliche Plausibilitätsregeln |
| `cleaning/imputation.py` | Kalorien-Imputation und zugehörige Hilfslogik |
| `cleaning/steps.py` | Implementierung der acht Cleaning-Schritte |
| `pipeline/core.py` | Generische Ausführung einzelner Pipeline-Schritte |
| `pipeline/factory.py` | Zusammenstellung der acht Standard-Cleaning-Schritte |
| `pipeline/run.py` | Parametrisierter Einstiegspunkt für die gesamte Verarbeitung |
| `pipeline/quality.py` | Berechnung der Datenqualitätsmetriken |
| `pipeline/report.py` | Protokollierung der Wirkung jedes Cleaning-Schritts |
| `combine.py` | Konkatenation und chronologische Sortierung der harmonisierten Quellen |
| `features.py` | Berechnung der abgeleiteten Analysevariablen |
| `export.py` | Schreiben und Lesen der aufbereiteten Ergebnisdateien |
| `config.py` | Zentrale Schwellenwerte, Spaltenlisten und Schema-Konstanten |
| `paths.py` | Zentrale Projekt- und Standardpfade |
| `logging_setup.py` | Gemeinsame Logging-Konfiguration |
| `__init__.py` | Öffentliche Python-Schnittstelle des Pakets |
| `__main__.py` | Kommandozeilen-Einstieg über `python -m running_data` |

Die eigentliche Datenverarbeitung ist in den Python-Modulen unter `src/running_data/` definiert. Das Notebook enthält diese Logik deshalb nicht nochmals als eigene, voneinander abhängige Codeblöcke. Stattdessen importiert und verwendet es dieselben Funktionen, die auch von `run_pipeline()` und den automatisierten Tests aufgerufen werden. Das Notebook dient damit vor allem dazu, Zwischenergebnisse, Bereinigungsberichte und finale Resultate sichtbar und nachvollziehbar darzustellen. Änderungen an der Verarbeitungslogik müssen nur in den Python-Modulen vorgenommen werden und gelten danach gleichzeitig für Notebook, Pipeline und Tests.

## Installation

### Voraussetzungen

- Python `>= 3.11`
- `pip`
- Garmin- und/oder Apple-Health-Rohdaten im unten beschriebenen Format

### Virtuelle Umgebung

```bash
python -m venv .venv
source .venv/bin/activate
```

Unter Windows:

```powershell
.venv\Scripts\activate
```

### Laufzeitumgebung installieren

Die exakten Versionen der Laufzeitabhängigkeiten stehen in `requirements.txt`.

```bash
pip install -r requirements.txt
pip install -e . --no-deps
```

Wesentliche Bibliotheken:

- pandas
- NumPy
- lxml
- pyarrow
- Snakemake

### Entwicklungs- und Testumgebung

```bash
pip install -r requirements-dev.txt
pip install -e . --no-deps
```

`requirements-dev.txt` enthält zusätzlich `pytest`.

## Daten bereitstellen

Wenn keine eigenen Pfade angegeben werden, verwendet die Pipeline die in `paths.py` definierten Standardpfade innerhalb der Projektstruktur.

Garmin:

```text
data/garmin/<export-date>/Activities.csv
```

Apple Health:

```text
data/apple/<export-date>/Export.xml
```

Mehrere Exporte können parallel in getrennten Datumsordnern abgelegt werden. Die Pfadmuster der Pipeline können dadurch mehrere passende Exportdateien finden, ohne dass jeder Ordner einzeln angegeben werden muss.

Die persönlichen Rohdaten unter `data/` werden bewusst nicht als Testvoraussetzung verwendet. Die automatisierten Tests arbeiten mit kleinen synthetischen Fixtures unter `tests/fixtures/`.

## Pipeline ausführen

### Kommandozeile

Nach der Installation kann die gesamte Pipeline mit einem Befehl gestartet werden:

```bash
python -m running_data
```

Dabei werden die Standardpfade für Garmin und Apple verwendet und die Resultate nach `data/processed/` geschrieben.

Hilfe und verfügbare Optionen:

```bash
python -m running_data --help
```

#### Kommandozeilenoptionen

| **Option** | **Bedeutung** |
|---|---|
| `-h`, `--help` | Zeigt die Hilfe mit den verfügbaren Optionen und Standardwerten an und beendet das Programm anschliessend. |
| `--garmin MUSTER` | Überschreibt den Standardpfad für Garmin. `MUSTER` ist ein Dateipfad-Muster mit Platzhaltern. Beim Standard `data/garmin/*/Activities.csv` steht `*` für einen beliebigen Export-Unterordner, sodass mehrere passende Garmin-Exporte gefunden werden können. |
| `--apple MUSTER` | Überschreibt den Standardpfad für Apple Health. Beim Standard `data/apple/*/Export.xml` steht `*` für einen beliebigen Export-Unterordner, sodass mehrere passende XML-Exporte gefunden werden können. |
| `--output ORDNER` | Legt fest, in welchen Ordner `combined_runs.parquet` und `combined_runs.csv` geschrieben werden. Ohne Angabe wird `data/processed/` verwendet. |
| `--dry-run` | Führt Import, Typisierung, Cleaning, Zusammenführung, Feature Engineering und Qualitätsauswertung vollständig aus, schreibt aber keine Ergebnisdateien. Nützlich zur Kontrolle, ob die Pipeline mit den angegebenen Daten erfolgreich läuft. |
| `--quiet` | Unterdrückt die normalen Info-Meldungen der Pipeline. Warnungen und Fehler werden weiterhin ausgegeben. |

In den Pfadmustern steht `*` für einen beliebigen Export-Unterordner. So können beispielsweise mehrere Datumsordner gefunden werden, ohne jeden Pfad einzeln anzugeben.

Beispiel:

```bash
python -m running_data \
  --garmin "data/garmin/*/Activities.csv" \
  --apple "data/apple/*/Export.xml" \
  --output data/processed
```

### Workflow mit Snakemake

Die Python-Pipeline ist zusätzlich in einen Snakemake-Workflow eingebettet. Das `Snakefile` definiert die Garmin- und Apple-Rohdaten als Inputs und die kombinierten CSV- und Parquet-Dateien als Outputs.

Die Rohdaten werden automatisch über ihre Ordnerstruktur gefunden:

```text
data/garmin/<export-date>/Activities.csv
data/apple/<export-date>/Export.xml
```

Neue Exporte müssen dadurch nicht einzeln im `Snakefile` eingetragen werden, solange sie derselben Ordnerstruktur folgen.

Snakemake wird aus dem Repository-Root ausgeführt. Nach der oben beschriebenen Installation kann der Workflow gestartet werden mit:

```bash
snakemake --cores 1
```

Für einen Dry Run, bei dem nur geprüft wird, welche Schritte ausgeführt würden:

```bash
snakemake -n --cores 1
```

Snakemake prüft die Abhängigkeiten zwischen Inputs, Verarbeitungslogik und Ergebnisdateien. Werden Rohdaten ergänzt oder verändert oder ändert sich für die Pipeline relevanter Python-Code, werden die betroffenen Outputs erneut erzeugt. Sind Inputs, Code und Outputs unverändert, wird die Pipeline nicht unnötig erneut ausgeführt.

Der von Snakemake erzeugte Arbeitsordner `.snakemake/` wird über `.gitignore` nicht versioniert.

### Aus Python

```python
from running_data import configure_logging, run_pipeline

configure_logging()

result = run_pipeline()

result.data
result.reports
result.summaries
result.qualities
result.outputs
```

Die Funktion `run_pipeline()` ist parametrisiert. Inputpfade, Outputordner und die Cleaning-Konfiguration können angepasst werden.

Beispiel ohne Dateiexport:

```python
result = run_pipeline(output_dir=None)
```

## Tests

Die Testumgebung wird mit `requirements-dev.txt` installiert.

```bash
pytest
```

Die Tests greifen **nicht** auf persönliche Daten unter `data/` zu. Sie verwenden:

- `tests/fixtures/garmin/2025-08-22/Activities.csv`: eine kleine erfundene Garmin-Datei im echten CSV-Exportformat
- `tests/fixtures/apple/2025-08-22/Export.xml`: ein gekürztes erfundenes Apple-Health-XML mit der relevanten Exportstruktur
- `make_runs` aus `tests/conftest.py`: synthetische DataFrames, mit denen einzelne Grenzfälle gezielt konstruiert werden
- temporäre Verzeichnisse von `pytest` für Exporttests, damit `data/processed/` während der Tests nicht verändert wird

Die Testsuite besteht aktuell aus **acht Testmodulen**:

| **Testmodul** | **Abgedeckter Bereich** |
|---|---|
| `test_validators.py` | Die fünf Plausibilitätsregeln und ihre Grenzwerte für Distanz, Dauer, Pace und Herzfrequenz |
| `test_garmin_typing.py` | Lauf-Filter, Reduktion auf das Rohschema, Dauerumrechnung, Distanz-Heuristik, Datentypen, gemeinsames Schema, Entfernung der Rohspalte `duration` und Regressionstest für den Garmin-Datumsfehler |
| `test_schema.py` | Gemeinsames Schema beider Quellen, Datentypen nach dem Cleaning, Pflichtfelder, finales Ergebnisschema, Features, Quellen, Zeilenzahl, chronologische Sortierung und dokumentiertes Kategorie-Verhalten nach `concat` |
| `test_imputation.py` | Alle vier Ebenen der Kalorien-Fallback-Kette, Herkunftsspalten, Behandlung von Null- und Negativwerten, Distanzklassen, Entfernung interner Hilfsspalten und Hilfslogik für Winsorising |
| `test_pipeline_core.py` | Reihenfolge und Verkettung von Schritten, `CleaningReport`, unveränderte Eingabe sowie Fehlerbehandlung kritischer und unkritischer Schritte |
| `test_quality.py` | Completeness, Validity, Consistency und Uniqueness, Ausschluss der Herkunftsspalten, Statusschwellen und Vergleich mehrerer Quellen |
| `test_export.py` | CSV- und Parquet-Ausgabe, Dateinamen, Zielordner, Überschreiben, fehlende Dateien sowie verlustfreier Parquet-Roundtrip inklusive Datentypen |
| `test_run_pipeline.py` | End-to-End-Verarbeitung von Rohdateien bis Ergebnis, beide und einzelne Quellen, `PipelineResult`, acht Cleaning-Schritte, benutzerdefinierte Konfiguration, Ausgabeordner und Kommandozeilen-Aufruf |

### Regressionstest: Garmin-Datumsformat

**Issue:** Garmin-Exporte können unterschiedliche Datumsformate enthalten. Im älteren Export liegen Zeitstempel beispielsweise im europäischen Format `DD.MM.YYYY HH:MM` vor, während ein neuerer Export Werte wie `YYYY-MM-DD HH:MM:SS` enthält. Eine feste Formatangabe kann deshalb gültige Zeitstempel des jeweils anderen Exportformats zu `NaT` umwandeln. Ein nachfolgender Imputationsschritt könnte solche fehlenden Werte dann mit dem Exportdatum füllen und damit das ursprüngliche Laufdatum verfälschen.

**Lösung:** Die Garmin-Typisierung verarbeitet gemischte Datumsformate bereits vor der allgemeinen Cleaning-Pipeline:

```python
pd.to_datetime(
    df["date"],
    format="mixed",
    dayfirst=True,
    errors="coerce",
)
```

Damit werden unterschiedliche Garmin-Exportformate unterstützt und europäische Datumsangaben weiterhin mit Tag vor Monat interpretiert.

### Dokumentierter Randfall: leere Eingabe

Für eine vollständig leere Eingabe existiert aktuell ein mit `xfail(strict=True)` markierter Test.

**Issue:** `CleaningReport.add_step()` berechnet die gespeicherte `removal_rate` bereits sicher für `rows_before == 0`. In der anschliessenden Log-Ausgabe wird jedoch nochmals `removed / rows_before * 100` ohne dieselbe Absicherung berechnet. Bei einer leeren Eingabe entsteht deshalb ein `ZeroDivisionError`, bevor die eigentlich vorgesehene verständliche Fehlermeldung des kritischen Pipeline-Schritts erreicht wird.

**Aktueller Umgang:** Der Fehler ist als bekannter Randfall explizit im Test festgehalten und wird nicht versteckt. Die normale Gesamtpipeline umgeht ihn: `run_pipeline()` überspringt leere Einzelquellen und löst einen klaren `ValueError` aus, wenn weder Garmin noch Apple Laufaktivitäten liefern. Der `xfail` dokumentiert damit eine noch offene Schwachstelle der generischen Pipeline-Mechanik, ohne den produktiven Standardaufruf zu blockieren.

## Reproduzierbarkeit

Die Reproduzierbarkeit des Projekts hängt nicht von einem einzelnen Mechanismus ab, sondern wird durch mehrere technische Entscheidungen unterstützt:

- **Versionierte Abhängigkeiten:** `requirements.txt` und `requirements-dev.txt`
- **Installierbares Python-Paket:** `src`-Layout und `pyproject.toml`
- **Zentrale Konfiguration:** fachliche Schwellenwerte liegen in `config.py`
- **Parametrisierte Gesamtpipeline:** `run_pipeline()` kapselt den vollständigen Ablauf
- **Kommandozeilen-Einstieg:** `python -m running_data`
- **Workflow-Orchestrierung:** Snakemake überwacht die Abhängigkeiten zwischen Rohdaten, Pipeline-Code und Ergebnisdateien
- **Automatisierte Tests:** Schema, Validierung, Imputation, Export und End-to-End-Verarbeitung
- **Audit Trail:** `CleaningReport` dokumentiert die Wirkung jedes Pipeline-Schritts
- **Reproduzierbarer Export:** Parquet als massgebliches Datenprodukt und CSV als Kontrollkopie
- **Git:** Code, Konfiguration und Testdaten werden versioniert, persönliche Rohdaten bleiben ausserhalb der Versionsverwaltung

## Daten und Datenschutz

Die echten Garmin- und Apple-Health-Exporte enthalten personenbezogene Gesundheits- und Aktivitätsdaten. Diese Rohdaten werden deshalb nicht im Git-Repository versioniert und sollen insbesondere nicht in ein öffentlich zugängliches Repository gelangen.

Die Tests verwenden bewusst kleine, erfundene Datensätze, die nur die technische Struktur der realen Exporte abbilden:

- `tests/fixtures/garmin/2025-08-22/Activities.csv`
- `tests/fixtures/apple/2025-08-22/Export.xml`

Zusätzlich erzeugt `make_runs` in `tests/conftest.py` synthetische Laufdatensätze für gezielte Testfälle. Dadurch kann das Projekt nach einem frischen Checkout getestet werden, ohne Zugriff auf persönliche Rohdaten zu benötigen.


