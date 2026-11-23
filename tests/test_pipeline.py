from pathlib import Path

import pandas as pd

from datastudio.loading import load_csv
from datastudio.pipeline import main

SAMPLES = Path(__file__).parent.parent / "samples"


def test_pipeline_writes_cleaned_csv_and_audit_log(tmp_path):
    source = SAMPLES / "housing_comma.csv"
    assert main([str(source), "--output", str(tmp_path), "--range", "housing_median_age:0:100"]) == 0

    cleaned = load_csv(tmp_path / "cleaned.csv")  # the export can be loaded again
    assert cleaned.shape == (13, 10)
    assert cleaned.isna().sum().sum() == 0
    assert cleaned["housing_median_age"].min() >= 0

    audit = pd.read_csv(tmp_path / "audit_log.csv")
    assert list(audit["affected"]) == [1, 1, 1, 2, 1]


def test_pipeline_saves_before_after_charts(tmp_path):
    source = SAMPLES / "housing_comma.csv"
    assert main([str(source), "--output", str(tmp_path), "--chart", "histogram:median_income"]) == 0
    assert (tmp_path / "charts" / "01_histogram_median_income.png").exists()
