from pathlib import Path

import pytest

from datastudio.errors import LoadError
from datastudio.loading import load_csv

SAMPLES = Path(__file__).parent.parent / "samples"


@pytest.mark.parametrize("name", ["housing_comma.csv", "housing_semicolon.csv"], ids=["comma", "semicolon"])
def test_separator_is_detected_and_gives_all_columns(name):
    assert load_csv(SAMPLES / name).shape == (14, 10)


def test_broken_row_gives_controlled_error_with_hint():
    with pytest.raises(LoadError, match="Wadliwy wiersz") as info:
        load_csv(SAMPLES / "broken_row.csv")
    assert info.value.hint
