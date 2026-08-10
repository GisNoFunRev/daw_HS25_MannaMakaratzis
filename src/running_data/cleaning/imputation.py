"""Imputation fehlender Kalorienwerte.

Fachliche Idee
--------------
Der Kalorienverbrauch eines Laufs hängt im Wesentlichen von zwei Grössen ab:
wie weit gelaufen wurde und wie intensiv. Ein globaler Mittelwert würde diesen
Zusammenhang ignorieren und einem 3-km-Lauf denselben Wert zuweisen wie einem
Marathon.

Stattdessen wird der Median vergleichbarer Läufe verwendet. "Vergleichbar"
heisst: gleiche Quelle, ähnliche Distanz, ähnliche Herzfrequenz. Weil eine so
enge Gruppe leer sein kann, greift eine vierstufige Fallback-Kette:

=======  ======================================  ===================
Ebene    Gruppierung                             Genauigkeit
=======  ======================================  ===================
level3   source + Distanzklasse + HF-Quartil     am höchsten
level2   source + Distanzklasse                  hoch
level1   source                                  mittel
level0   gesamter Datensatz                      niedrig, aber immer da
=======  ======================================  ===================

Nachvollziehbarkeit
-------------------
Imputierte Werte sind keine Messwerte. Damit das in der Auswertung sichtbar
bleibt, ergänzt die Imputation zwei Spalten: ``calories_imputed`` (wurde der
Wert ersetzt?) und ``imputation_level`` (auf welcher Ebene?).
"""

import numpy as np
import pandas as pd

from ..config import DataCleaningConfig
from ..logging_setup import get_logger

logger = get_logger(__name__)


def _build_distance_bins(s: pd.Series, config: DataCleaningConfig) -> pd.Series:
    """Teilt die Distanzen in die in der Konfiguration definierten Klassen ein.

    Args:
        s: Distanzwerte in Kilometern.
        config: Liefert die Klassengrenzen über ``DISTANCE_BINS``.

    Returns:
        Kategoriale Serie mit der Distanzklasse je Zeile.
    """
    s_num = pd.to_numeric(s, errors="coerce").clip(lower=0)
    return pd.cut(s_num, bins=config.DISTANCE_BINS, right=False, include_lowest=True)


def _build_hr_bins_per_source(
    df: pd.DataFrame, config: DataCleaningConfig, col: str = "avg_heart_rate"
) -> pd.Series:
    """Bildet Herzfrequenz-Quantile **je Datenquelle**.

    Die Quantile werden bewusst pro Quelle gebildet: Garmin- und Apple-Geräte
    messen unterschiedlich, ein quellenübergreifendes Quartil würde diese
    Kalibrierungsunterschiede als Intensitätsunterschiede fehlinterpretieren.

    Reichen die Daten einer Quelle nicht für die konfigurierte Anzahl
    Quantile, wird auf zwei gleich breite Klassen ausgewichen; bei weniger als
    zwei verschiedenen Werten bleibt die Klasse leer.

    Args:
        df: Datensatz mit den Spalten ``source`` und ``col``.
        config: Liefert die Anzahl Quantile über ``HR_QUANTILES``.
        col: Name der Herzfrequenzspalte.

    Returns:
        Serie mit den Klassencodes 1..n als ``float``; ``NaN``, wo keine
        Klasse gebildet werden konnte.
    """
    hr_bin = pd.Series(np.nan, index=df.index, dtype="float")

    for _, sub in df.groupby("source"):
        x = pd.to_numeric(sub[col], errors="coerce").dropna()
        n_unique = x.nunique()

        if n_unique >= config.HR_QUANTILES:
            q = pd.qcut(x, config.HR_QUANTILES, duplicates="drop")
            codes = q.cat.codes.replace(-1, np.nan) + 1
            hr_bin.loc[q.index] = codes.astype("float")
        elif n_unique >= 2:
            c = pd.cut(x, 2)
            codes = c.cat.codes.replace(-1, np.nan) + 1
            hr_bin.loc[c.index] = codes.astype("float")

    return hr_bin


def count_changed(series_old: pd.Series, series_new: pd.Series) -> int:
    """Zählt, in wie vielen Zeilen sich zwei Serien unterscheiden.

    Wird verwendet, um die Wirkung des Winsorisings zu protokollieren.
    """
    return int(np.count_nonzero(series_old.ne(series_new)))


def impute_grouped_calories(
    df: pd.DataFrame, config: DataCleaningConfig
) -> pd.DataFrame:
    """Füllt fehlende Kalorienwerte über die vierstufige Fallback-Kette.

    Args:
        df: Datensatz mit den Spalten ``source``, ``distance_km``,
            ``avg_heart_rate`` und ``calories``.
        config: Klassengrenzen und Anzahl Quantile.

    Returns:
        Kopie des Datensatzes mit gefüllter ``calories``-Spalte sowie den
        Zusatzspalten ``calories_imputed`` und ``imputation_level``. Die
        temporären Klassenspalten werden wieder entfernt.
    """
    out = df.copy()

    # Hilfsklassen für die Gruppierung; werden am Ende wieder entfernt.
    out["_dist_bin"] = _build_distance_bins(out["distance_km"], config)
    out["_hr_bin"] = _build_hr_bins_per_source(out, config, "avg_heart_rate")

    # Fehlende und unmögliche Werte einheitlich als NaN markieren, damit die
    # Mediane unten nicht durch Nullwerte verfälscht werden.
    out["calories"] = pd.to_numeric(out["calories"], errors="coerce")
    out.loc[out["calories"].isna() | (out["calories"] <= 0), "calories"] = np.nan

    # Mediantabellen aller vier Ebenen einmalig vorberechnen.
    medians = {
        "level3": out.groupby(["source", "_dist_bin", "_hr_bin"], dropna=False)[
            "calories"
        ].median(),
        "level2": out.groupby(["source", "_dist_bin"], dropna=False)[
            "calories"
        ].median(),
        "level1": out.groupby(["source"], dropna=False)["calories"].median(),
        "level0": out["calories"].median(),
    }

    def _fill_row(row: pd.Series) -> tuple:
        """Liefert (Wert, wurde_imputiert, verwendete_Ebene) für eine Zeile."""
        if pd.notna(row["calories"]):
            return row["calories"], False, pd.NA

        value = medians["level3"].get(
            (row["source"], row["_dist_bin"], row["_hr_bin"]), np.nan
        )
        if pd.notna(value):
            return value, True, "level3"

        value = medians["level2"].get((row["source"], row["_dist_bin"]), np.nan)
        if pd.notna(value):
            return value, True, "level2"

        value = medians["level1"].get(row["source"], np.nan)
        if pd.notna(value):
            return value, True, "level1"

        return medians["level0"], True, "level0"

    result = out.apply(_fill_row, axis=1, result_type="expand")
    out["calories"] = result[0]
    out["calories_imputed"] = result[1]
    out["imputation_level"] = result[2]

    if out["calories_imputed"].any():
        summary = out.loc[out["calories_imputed"], "imputation_level"].value_counts()
        logger.info("Calories imputation summary:\n%s", summary)

    out.drop(columns=["_dist_bin", "_hr_bin"], inplace=True)
    return out
