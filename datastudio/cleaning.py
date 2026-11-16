"""Cleaning operations as pure functions.

Every function returns a new DataFrame or a boolean mask and never changes its
input, so the raw data of a session stays intact. Detection (masks) is separate
from the decision what to do with the detected rows.

Outliers use the IQR rule: a value is an outlier when it lies below
Q1 - k * IQR or above Q3 + k * IQR (k = 1.5 by default). Missing values are
never reported as out of range or as outliers.
"""

import math

import pandas as pd
from pandas.api.types import is_bool_dtype, is_numeric_dtype

from datastudio.errors import ColumnError, RuleError

FILL_STRATEGIES = ("mean", "median", "mode")


def require_column(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        raise ColumnError(
            f"Brak kolumny: {column}",
            f"Wybierz jedną z kolumn: {', '.join(map(str, frame.columns))}.",
        )
    return frame[column]


def require_numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    series = require_column(frame, column)
    if not is_numeric_dtype(series) or is_bool_dtype(series):
        raise ColumnError(
            f"Kolumna {column} nie jest liczbowa (typ: {series.dtype})",
            "Wybierz kolumnę liczbową.",
        )
    return series


def drop_duplicates(frame: pd.DataFrame, subset: list[str] | None = None) -> pd.DataFrame:
    """Remove repeated rows, keeping the first one. `subset` = key columns, None = full rows."""
    for column in subset or []:
        require_column(frame, column)
    return frame.drop_duplicates(subset=subset).copy()


def drop_missing(frame: pd.DataFrame, columns: list[str] | None = None) -> pd.DataFrame:
    """Remove rows with a missing value in `columns` (None = in any column)."""
    for column in columns or []:
        require_column(frame, column)
    return frame.dropna(subset=columns).copy()


def fill_value(frame: pd.DataFrame, column: str, strategy: str):
    """Value used to fill missing cells of a column: mean, median or mode."""
    if strategy not in FILL_STRATEGIES:
        raise RuleError(
            f"Nieznana strategia uzupełniania: {strategy}",
            f"Dostępne strategie: {', '.join(FILL_STRATEGIES)}.",
        )
    series = require_column(frame, column) if strategy == "mode" else require_numeric(frame, column)
    if series.dropna().empty:
        raise RuleError(
            f"Kolumna {column} nie zawiera żadnej wartości",
            "Usuń tę kolumnę z operacji albo usuń rekordy z brakami.",
        )
    if strategy == "mean":
        return series.mean()
    if strategy == "median":
        return series.median()
    return series.mode().iloc[0]


def fill_missing(frame: pd.DataFrame, column: str, value) -> pd.DataFrame:
    result = frame.copy()
    result[column] = result[column].fillna(value)
    return result


def validate_bounds(lower: float | None, upper: float | None) -> None:
    if lower is None and upper is None:
        raise RuleError("Reguła zakresu nie ma żadnej granicy", "Podaj minimum, maksimum albo obie wartości.")
    if any(bound is not None and math.isnan(bound) for bound in (lower, upper)):
        raise RuleError("Granica zakresu nie jest liczbą", "Podaj granice jako liczby, np. 0 i 100.")
    if lower is not None and upper is not None and lower > upper:
        raise RuleError(
            f"Minimum ({lower}) jest większe od maksimum ({upper})",
            "Zamień granice miejscami.",
        )


def outside_mask(frame: pd.DataFrame, column: str, lower: float | None, upper: float | None) -> pd.Series:
    """True for rows whose value lies below `lower` or above `upper`."""
    validate_bounds(lower, upper)
    values = require_numeric(frame, column)
    mask = pd.Series(False, index=frame.index)
    if lower is not None:
        mask |= values < lower
    if upper is not None:
        mask |= values > upper
    return mask


def iqr_bounds(frame: pd.DataFrame, column: str, factor: float = 1.5) -> tuple[float, float]:
    """Outlier fences of a column. A constant or empty column gets infinite fences (no outliers)."""
    if not factor > 0:
        raise RuleError(f"Współczynnik IQR musi być dodatni (podano {factor})", "Użyj np. 1.5 albo 3.")
    values = require_numeric(frame, column)
    q1, q3 = values.quantile(0.25), values.quantile(0.75)
    iqr = q3 - q1
    if pd.isna(iqr) or iqr == 0:
        return -math.inf, math.inf
    return float(q1 - factor * iqr), float(q3 + factor * iqr)


def remove_rows(frame: pd.DataFrame, mask: pd.Series) -> pd.DataFrame:
    return frame[~mask].copy()


def set_missing(frame: pd.DataFrame, column: str, mask: pd.Series) -> pd.DataFrame:
    result = frame.copy()
    result[column] = result[column].mask(mask)
    return result


def clip_column(frame: pd.DataFrame, column: str, lower: float | None, upper: float | None) -> pd.DataFrame:
    result = frame.copy()
    result[column] = result[column].clip(lower, upper)
    return result


def flag_rows(frame: pd.DataFrame, mask: pd.Series, flag_column: str) -> pd.DataFrame:
    result = frame.copy()
    result[flag_column] = mask
    return result
