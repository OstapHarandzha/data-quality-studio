import pandas as pd
import pytest

from datastudio import charts
from datastudio.charts import CATEGORY, NUMERIC, ChartSpec
from datastudio.errors import ColumnError, RuleError


def make_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "income": [1.0, 2.0, 3.0, 4.0, 5.0, None],
            "value": [12.0, 19.0, 31.0, 42.0, 50.0, 60.0],
            "city": ["Kraków", "Gdańsk", "Kraków", "Lublin", "Gdańsk", "Kraków"],
            "constant": [7.0] * 6,
            "rooms": [1, 2, 2, 3, 3, 3],
        }
    )


@pytest.mark.parametrize(
    "spec",
    [
        ChartSpec("histogram", x="income"),
        ChartSpec("scatter", x="income", y="value"),
        ChartSpec("box", x="city", y="value"),
        ChartSpec("bar", x="city"),
    ],
    ids=["histogram", "scatter", "box", "bar"],
)
def test_chart_has_title_and_axis_labels(spec):
    ax = charts.build_chart(make_frame(), spec).axes[0]
    assert ax.get_title() and ax.get_xlabel() and ax.get_ylabel()


@pytest.mark.parametrize(
    ("spec", "error", "message"),
    [
        (ChartSpec("histogram", x="city"), ColumnError, "nie jest liczbowa"),
        (ChartSpec("histogram", x="constant"), ColumnError, "jest stała"),
        (ChartSpec("scatter", x="income"), RuleError, "Nie wybrano kolumny"),
    ],
    ids=["text_column", "constant_column", "no_selection"],
)
def test_invalid_chart_is_blocked_with_message_and_hint(spec, error, message):
    with pytest.raises(error, match=message) as info:
        charts.build_chart(make_frame(), spec)
    assert info.value.hint


def test_column_lists_match_chart_roles():
    frame = make_frame()
    assert charts.columns_for(frame, NUMERIC) == ["income", "value", "rooms"]
    assert charts.columns_for(frame, CATEGORY) == ["city", "rooms"]


def test_correlation_summary_starts_with_strongest_pair_and_warns_about_causation():
    lines = charts.correlation_summary(make_frame())
    assert lines[0].startswith("income – value")
    assert "Nie oznacza" in lines[-1]


def test_saved_chart_files_have_the_right_format(tmp_path):
    figure = charts.build_chart(make_frame(), ChartSpec("correlation"))
    for fmt, magic in [("png", b"\x89PNG"), ("pdf", b"%PDF"), ("svg", b"<?xml")]:
        assert charts.save_figure(figure, tmp_path / f"corr.{fmt}").read_bytes().startswith(magic)
