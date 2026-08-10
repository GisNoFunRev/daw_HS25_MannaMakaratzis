"""Zusammensetzung der Standard-Bereinigungspipeline.

Warum dieses Modul existiert
----------------------------
Im Notebook war die Pipeline zweimal ausgeschrieben: einmal für Garmin
(qmd:1230-1286) und einmal für Apple (qmd:1464-1520). Die beiden Blöcke waren
57 Zeilen lang und unterschieden sich in genau einer Zeile — dem
Variablennamen.

Damit war die Zusage "beide Quellen werden identisch bereinigt" allein eine
Frage der Sorgfalt beim Kopieren. Ein neunter Schritt hätte an zwei Stellen
eingefügt werden müssen; ein Versäumnis wäre nicht aufgefallen, weil beide
Berichte weiterhin plausibel ausgesehen hätten.

Durch build_cleaning_pipeline ist die Gleichheit jetzt per
Konstruktion gegeben: Es gibt nur noch eine Definition der Schrittfolge.
"""

from ..cleaning import steps
from ..config import DataCleaningConfig
from .core import CleaningStep, DataCleaningPipeline

# Die Standard-Schrittfolge der Datenbereinigung.
#
# Die Reihenfolge ist fachlich begründet (siehe Modul-Docstring von
# running_data.cleaning.steps). Kritisch ist allein "Validate
# Essentials": Ohne Distanz und Dauer ist ein Eintrag kein auswertbarer Lauf,
# alle weiteren Schritte würden auf leeren Daten arbeiten.
DEFAULT_CLEANING_STEPS: tuple[CleaningStep, ...] = (
    CleaningStep(
        name="Date Imputation",
        function=steps.step_impute_dates,
        description="Imputiert fehlende Datumsangaben aus export_date",
        is_critical=False,
    ),
    CleaningStep(
        name="Remove Duplicates",
        function=steps.step_remove_duplicates,
        description="Entfernt Duplikate basierend auf Schlüsselfeldern",
        is_critical=False,
    ),
    CleaningStep(
        name="Validate Essentials",
        function=steps.step_validate_essentials,
        description="Entfernt Zeilen ohne distance/duration",
        is_critical=True,
    ),
    CleaningStep(
        name="Plausibility Checks",
        function=steps.step_validate_plausibility,
        description="Validiert Distanz, Dauer, Pace",
        is_critical=False,
    ),
    CleaningStep(
        name="Heart Rate Cleaning",
        function=steps.step_clean_heart_rate,
        description="Bereinigt und imputiert Herzfrequenzwerte",
        is_critical=False,
    ),
    CleaningStep(
        name="Calories Imputation",
        function=steps.step_impute_calories,
        description="Gruppenbasierte Imputation und Winsorising",
        is_critical=False,
    ),
    CleaningStep(
        name="Final HR Sweep",
        function=steps.step_final_hr_sweep,
        description="Entfernt physiologisch unrealistische Herzfrequenzen",
        is_critical=False,
    ),
    CleaningStep(
        name="Finalize Types",
        function=steps.step_finalize_types,
        description="Setzt finale Datentypen",
        is_critical=False,
    ),
)


def build_cleaning_pipeline(
    source: str, config: DataCleaningConfig
) -> DataCleaningPipeline:
    """Baut die Standard-Bereinigungspipeline für eine Datenquelle.

    Args:
        source: Name der Quelle für Log und Bericht, z. B. "Garmin".
        config: Schwellenwerte, die an alle Schritte weitergereicht werden.

    Returns:
        Die fertig bestückte, noch nicht ausgeführte Pipeline.

    Beispiel:
        >>> cleaned, report = build_cleaning_pipeline("Garmin", config).run(df)
    """
    pipeline = DataCleaningPipeline(source, config)
    for step in DEFAULT_CLEANING_STEPS:
        pipeline.add_step(step)
    return pipeline
