"""Die einzelnen Schritte der Bereinigungspipeline.

Alle Funktionen dieses Moduls haben dieselbe Signatur
``(df, config, report) -> df`` (siehe
:data:`~running_data.pipeline.core.CleaningStepFunction`) und sind damit für
die Pipeline austauschbar. Sie sind quellenunabhängig: Ab hier sind Garmin-
und Apple-Daten auf dasselbe Schema harmonisiert, quellenspezifisches Wissen
steckt ausschliesslich in :mod:`running_data.cleaning.garmin_typing` und
:mod:`running_data.cleaning.apple_typing`.

Reihenfolge der Schritte
------------------------
Die Reihenfolge ist nicht beliebig. Duplikate werden vor den
Plausibilitätsprüfungen entfernt, damit die Statistik nicht durch Kopien
verzerrt wird. Die Kalorien-Imputation läuft nach der Herzfrequenz-
Bereinigung, weil sie die Herzfrequenz zur Gruppenbildung braucht.
"""

import numpy as np
import pandas as pd

from ..config import (
    CATEGORICAL_COLUMNS,
    DUPLICATE_KEY_COLUMNS,
    ESSENTIAL_COLUMNS,
    DataCleaningConfig,
)
from ..logging_setup import get_logger
from ..pipeline.report import CleaningReport
from .imputation import count_changed, impute_grouped_calories
from .validators import DataValidator

logger = get_logger(__name__)

#: Obergrenze, oberhalb derer ein Herzfrequenzwert als Messfehler gilt und
#: verworfen wird, bevor die eigentliche Plausibilitätsprüfung greift.
HR_IMPLAUSIBLE_ABOVE = 300


def step_impute_dates(
    df: pd.DataFrame, config: DataCleaningConfig, report: CleaningReport
) -> pd.DataFrame:
    """Schritt 1 — ergänzt fehlende Datumsangaben aus dem Exportdatum.

    Fehlt der Zeitstempel eines Laufs, wird ersatzweise das Exportdatum des
    Ordners verwendet (auf 12:00 Uhr gesetzt, um eine Tagesmitte
    anzunehmen). Das vermeidet, dass Läufe allein wegen eines fehlenden
    Zeitstempels verloren gehen.

    .. warning::
       **Bekannter Fehler (TODO 1), hier bewusst unverändert übernommen.**
       ``pd.to_datetime`` wird ohne Formatangabe aufgerufen. Garmin liefert
       Datumswerte im europäischen Format ``TT.MM.JJJJ HH:MM``, das pandas
       ohne ``dayfirst=True`` als ``MM.TT.JJJJ`` liest. Folge: Bei Tagen
       ≤ 12 werden Tag und Monat vertauscht ("11.07.2025" wird zum
       7. November), bei Tagen > 12 entsteht ``NaT`` — und diese Zeilen
       erhalten anschliessend hier alle dasselbe Exportdatum.

       Die Korrektur gehört in ``clean_garmin_typing`` (explizites
       ``format="%d.%m.%Y %H:%M"``) und ist nicht Teil dieses
       Refactorings, das das Verhalten unverändert lassen soll.
    """
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    export_dt = pd.to_datetime(df["export_date"], errors="coerce")

    mask_date_missing = df["date"].isna() & export_dt.notna()
    df.loc[mask_date_missing, "date"] = export_dt.loc[mask_date_missing] + pd.Timedelta(
        hours=12
    )

    logger.info("Imputiert: %d Datumsangaben aus export_date", mask_date_missing.sum())
    return df


def step_remove_duplicates(
    df: pd.DataFrame, config: DataCleaningConfig, report: CleaningReport
) -> pd.DataFrame:
    """Schritt 2 — entfernt doppelt erfasste Läufe.

    Ein Lauf gilt als Duplikat, wenn Quelle, Zeitpunkt, Distanz und Dauer
    übereinstimmen (:data:`~running_data.config.DUPLICATE_KEY_COLUMNS`). Die
    Quelle ist Teil des Schlüssels, weil derselbe Lauf durchaus von zwei
    Geräten aufgezeichnet worden sein darf.
    """
    return df.drop_duplicates(subset=DUPLICATE_KEY_COLUMNS)


def step_validate_essentials(
    df: pd.DataFrame, config: DataCleaningConfig, report: CleaningReport
) -> pd.DataFrame:
    """Schritt 3 — verwirft Zeilen ohne Distanz oder Dauer.

    Diese beiden Werte lassen sich nicht sinnvoll schätzen; ohne sie ist ein
    Eintrag kein auswertbarer Lauf. Der Schritt ist deshalb als kritisch
    markiert.
    """
    return df.dropna(subset=ESSENTIAL_COLUMNS)


def step_validate_plausibility(
    df: pd.DataFrame, config: DataCleaningConfig, report: CleaningReport
) -> pd.DataFrame:
    """Schritt 4 — filtert unrealistische Distanz-, Dauer- und Pace-Werte.

    Die drei Masken werden einzeln berechnet, damit im Log ersichtlich ist,
    welche Regel wie oft gegriffen hat, und erst danach kombiniert.
    """
    validator = DataValidator()

    mask_distance = validator.validate_distance(df, config)
    mask_duration = validator.validate_duration(df, config)
    mask_pace = validator.validate_pace(df, config)

    # "~" negiert die Maske, zaehlt also die jeweils unplausiblen Zeilen.
    logger.info(
        "Plausibility failures by reason: %s",
        {
            "distance": int((~mask_distance).sum()),
            "duration": int((~mask_duration).sum()),
            "pace": int((~mask_pace).sum()),
        },
    )

    return df[mask_distance & mask_duration & mask_pace].copy()


def step_clean_heart_rate(
    df: pd.DataFrame, config: DataCleaningConfig, report: CleaningReport
) -> pd.DataFrame:
    """Schritt 5 — bereinigt und ergänzt Herzfrequenzwerte.

    Ablauf:

    1. Offensichtliche Messfehler (≤ 0 oder > 300 bpm) werden zu ``NaN``.
    2. Widersprüche ``max < avg`` werden aufgelöst: innerhalb der
       Rundungstoleranz wird ``max`` auf ``avg`` gesetzt, darüber hinaus
       gelten beide Werte als unglaubwürdig und werden verworfen.
    3. Die verbleibenden Lücken werden mit dem Median **je Quelle** gefüllt.
    """
    df = df.copy()
    validator = DataValidator()

    for col in ("avg_heart_rate", "max_heart_rate"):
        df.loc[(df[col] <= 0) | (df[col] > HR_IMPLAUSIBLE_ABOVE), col] = np.nan

    hr_check = validator.validate_hr_consistency(df, config)

    # Rundungsabweichung: max auf avg anheben.
    df.loc[hr_check["tolerance_mask"], "max_heart_rate"] = df.loc[
        hr_check["tolerance_mask"], "avg_heart_rate"
    ]
    # Echter Widerspruch: beide Werte verwerfen, sie werden unten imputiert.
    df.loc[hr_check["conflict_mask"], ["avg_heart_rate", "max_heart_rate"]] = np.nan

    logger.info(
        "HR Konflikte: %d total, %d toleriert, %d hart (→ NaN)",
        hr_check["inverted_mask"].sum(),
        hr_check["tolerance_mask"].sum(),
        hr_check["conflict_mask"].sum(),
    )

    for col in ("avg_heart_rate", "max_heart_rate"):
        before_nan = df[col].isna().sum()
        df[col] = df[col].fillna(df.groupby("source")[col].transform("median"))
        after_nan = df[col].isna().sum()
        logger.info(
            "%s: %d NaN → %d NaN (imputiert: %d)",
            col,
            before_nan,
            after_nan,
            before_nan - after_nan,
        )

    return df


def step_impute_calories(
    df: pd.DataFrame, config: DataCleaningConfig, report: CleaningReport
) -> pd.DataFrame:
    """Schritt 6 — ergänzt fehlende Kalorien und begrenzt Ausreisser.

    Zuerst greift die gruppenbasierte Imputation (siehe
    :mod:`running_data.cleaning.imputation`), danach werden Ausreisser
    winsorisiert — also auf die Grenzwerte gesetzt statt entfernt, um keine
    ansonsten gültigen Läufe zu verlieren. Winsorisiert wird zweifach: gegen
    absolute Grenzen und gegen ein plausibles Verhältnis kcal pro Kilometer.
    """
    df = df.copy()

    df["calories"] = pd.to_numeric(df["calories"], errors="coerce")
    before_bad = int((df["calories"].isna() | (df["calories"] <= 0)).sum())
    df.loc[df["calories"] <= 0, "calories"] = np.nan

    cal_before_impute = df["calories"].isna().sum()
    df = impute_grouped_calories(df, config)
    cal_after_impute = df["calories"].isna().sum()

    logger.info(
        "Calories: %d fehlerhaft/fehlend, Imputation: %d NaN → %d NaN",
        before_bad,
        cal_before_impute,
        cal_after_impute,
    )

    # Winsorising 1: absolute Ober- und Untergrenze.
    cal_before_clip = df["calories"].copy()
    df["calories"] = df["calories"].clip(
        lower=config.CALORIES_MIN, upper=config.CALORIES_MAX
    )
    wins_abs = count_changed(cal_before_clip, df["calories"])

    # Winsorising 2: ueber das Verhaeltnis kcal/km. Faengt Werte ab, die
    # absolut plausibel, fuer die gelaufene Distanz aber unmoeglich sind.
    kcal_per_km = (df["calories"] / df["distance_km"]).clip(
        lower=config.CALORIES_PER_KM_MIN, upper=config.CALORIES_PER_KM_MAX
    )
    cal_before_ratio = df["calories"].copy()
    df["calories"] = (kcal_per_km * df["distance_km"]).round(0)
    wins_ratio = count_changed(cal_before_ratio, df["calories"])

    logger.info("Winsorising: absolut=%d, kcal/km=%d", wins_abs, wins_ratio)
    return df


def step_final_hr_sweep(
    df: pd.DataFrame, config: DataCleaningConfig, report: CleaningReport
) -> pd.DataFrame:
    """Schritt 7 — entfernt Zeilen mit unphysiologischer Herzfrequenz.

    Abschliessende Kontrolle nach der Imputation: Werte ausserhalb des
    konfigurierten Bereichs (80–210 bpm) führen zum Verwerfen der Zeile.
    """
    validator = DataValidator()
    return df[validator.validate_heart_rate(df, config)].copy()


def step_finalize_types(
    df: pd.DataFrame, config: DataCleaningConfig, report: CleaningReport
) -> pd.DataFrame:
    """Schritt 8 — setzt die endgültigen Datentypen.

    Die kategorialen Spalten werden erst hier typisiert, weil vorangegangene
    Filterschritte sonst ungenutzte Kategorien zurücklassen würden.
    """
    df = df.copy()
    for col in CATEGORICAL_COLUMNS:
        df[col] = df[col].astype("category")
    return df
