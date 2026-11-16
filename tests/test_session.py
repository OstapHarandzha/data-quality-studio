import pandas as pd
import pytest

from datastudio.session import DataSession


def make_session() -> DataSession:
    return DataSession(
        pd.DataFrame(
            {
                "id": [1, 2, 2, 3, 4, 5],
                "age": [10.0, 20.0, 20.0, None, 30.0, 200.0],
                "city": ["Kraków", "Gdańsk", "Gdańsk", "Kraków", None, "Kraków"],
            }
        )
    )


def test_only_full_duplicates_are_removed_and_logged():
    session = make_session()
    assert session.drop_duplicates() == 1
    assert list(session.current["id"]) == [1, 2, 3, 4, 5]
    entry = session.audit_log[-1]
    assert (entry.rows_before, entry.rows_after, entry.affected) == (6, 5, 1)


@pytest.mark.parametrize(
    ("column", "strategy", "expected"),
    [("age", "median", 20.0), ("city", "mode", "Kraków")],
    ids=["numeric_median", "text_mode"],
)
def test_missing_values_are_filled_only_in_the_chosen_column(column, strategy, expected):
    session = make_session()
    assert session.fill_missing(column, strategy) == 1
    assert session.current[column].isna().sum() == 0
    assert expected in list(session.current[column])
    others = session.raw.columns.drop(column)
    pd.testing.assert_frame_equal(session.current[others], session.raw[others])


def test_range_rule_is_detected_without_changing_data():
    session = make_session()
    assert session.count_out_of_range("age", 0, 100) == 1
    pd.testing.assert_frame_equal(session.current, session.raw)
    assert session.audit_log == []


def test_iqr_outlier_is_flagged_and_its_value_is_kept():
    session = DataSession(pd.DataFrame({"x": [1.0, 2.0, 3.0, 4.0, 5.0, 100.0]}))
    assert session.handle_outliers("x", "flag") == 1  # fences: [-1.5, 8.5]
    assert list(session.current["x_outlier"]) == [False] * 5 + [True]
    assert list(session.current["x"]) == list(session.raw["x"])


def test_reset_restores_raw_data():
    session = make_session()
    session.drop_duplicates()
    session.handle_out_of_range("age", 0, 100, "remove")
    session.reset()
    pd.testing.assert_frame_equal(session.current, make_session().raw)
