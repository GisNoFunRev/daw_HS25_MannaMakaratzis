# Tests

Dieser Ordner ist das Gerüst für die automatisierten Tests (TODO 5) und
aktuell noch leer.

Vorgesehen sind mindestens:

- **Schema-Check** nach dem Cleaning: Spalten und Datentypen des kombinierten
  Datensatzes entsprechen dem erwarteten Schema.
- **Validator-Tests** für `running_data.cleaning.validators`: je Regel ein
  Fall knapp innerhalb und knapp ausserhalb der Grenze.
- **Regressionstest für den Garmin-Datums-Bug** (TODO 1): ein bekanntes
  Garmin-Datum im Format `TT.MM.JJJJ HH:MM` muss auf den korrekten Tag und
  Monat geparst werden.

Bewusst ohne `__init__.py`: Das Paket liegt im src-Layout und wird über
`pip install -e .` installiert, die Tests importieren es also wie ein
beliebiges Drittpaket.

Ausführen (nach `pip install -e .` und `pip install pytest`):

```bash
pytest
```
