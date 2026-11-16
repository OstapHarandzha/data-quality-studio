"""Data profile: size, types, missing values, duplicates, uniqueness, statistics."""

import pandas as pd


def numeric_columns(frame: pd.DataFrame) -> list[str]:
    return list(frame.select_dtypes("number").columns)


def overview(frame: pd.DataFrame) -> dict[str, int]:
    """Table-level numbers: size, full duplicates and missing cells."""
    return {
        "rows": len(frame),
        "columns": frame.shape[1],
        "duplicates": int(frame.duplicated().sum()),
        "missing_cells": int(frame.isna().sum().sum()),
    }


def column_profile(frame: pd.DataFrame) -> pd.DataFrame:
    """One row per column: type, missing count and percent, unique values."""
    return pd.DataFrame(
        {
            "dtype": frame.dtypes.astype(str),
            "missing": frame.isna().sum(),
            "missing_pct": frame.isna().mean().mul(100).round(2),
            "unique": frame.nunique(dropna=True),
        }
    )


def describe_numeric(frame: pd.DataFrame) -> pd.DataFrame:
    """Descriptive statistics of numeric columns (empty frame if there are none)."""
    numeric = frame[numeric_columns(frame)]
    if numeric.shape[1] == 0:
        return pd.DataFrame()
    return numeric.describe().T.round(3)
