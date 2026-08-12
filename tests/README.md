# Tests

Automatisierte Tests der Verarbeitungspipeline (TODO 5).

## Ausführen

```bash
pip install -r requirements-dev.txt
pytest
```

`pytest` allein genügt: Die Konfiguration in `pyproject.toml` legt `src/` auf
den Importpfad, ein vorheriges `pip install -e .` ist also nicht nötig.

## Aufbau

| Datei | Prüft |
|---|---|
| `test_validators.py` | Die fünf Plausibilitätsregeln, jeweils an den Grenzwerten |
| `test_garmin_typing.py` | Dauer-Umrechnung und der Datums-Regressionstest (TODO 1) |
| `test_schema.py` | Spalten und Datentypen nach Bereinigung und nach `run_pipeline` |
| `test_imputation.py` | Die vierstufige Fallback-Kette der Kalorien-Imputation |
| `test_pipeline_core.py` | Fehlerbehandlung bei kritischen und unkritischen Schritten |
| `test_quality.py` | Qualitätsmetriken, insbesondere die Herkunftsspalten |
| `test_export.py` | Schreiben und Wiedereinlesen ohne Verlust |
| `test_run_pipeline.py` | Die Gesamtpipeline von Rohdatei bis Ausgabe |

## Testdaten

**Kein Test greift auf `data/` zu.** Die echten Rohdaten liegen ausserhalb der
Versionsverwaltung; ein Test, der sie voraussetzt, schlägt bei jedem fehl, der
das Repository frisch auscheckt. Stattdessen:

- **`fixtures/`** enthält winzige, erfundene Exportdateien im echten Format —
  eine Garmin-CSV in Latin-1 mit Semikolon-Trennung und europäischem
  Datumsformat, ein gekürztes Apple-XML mit verschachtelten
  `WorkoutStatistics`. Der Ordneraufbau spiegelt `data/`, weil das
  Exportdatum aus dem Ordnernamen gelesen wird.
- **`make_runs`** (in `conftest.py`) baut synthetische Läufe im gemeinsamen
  Schema. Damit lässt sich für jeden Test exakt der Grenzfall herstellen, um
  den es geht.

Bewusst ohne `__init__.py`: Das Paket liegt im src-Layout, die Tests
importieren es wie ein beliebiges Drittpaket.
