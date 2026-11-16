import pandas as pd

from datastudio import profile


def test_profile_reports_size_duplicates_missing_and_unique_values():
    frame = pd.DataFrame(
        {
            "age": [10.0, None, 30.0, 10.0],
            "city": ["Kraków", "Gdańsk", None, "Kraków"],
        }
    )
    assert profile.overview(frame) == {"rows": 4, "columns": 2, "duplicates": 1, "missing_cells": 2}
    columns = profile.column_profile(frame)
    assert columns.loc["age", "dtype"] == "float64"
    assert columns.loc["age", "missing_pct"] == 25.0
    assert columns.loc["city", "unique"] == 2
