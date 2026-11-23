"""Charts built from parameters: histogram, scatter, box, bar and correlation heatmap.

Every chart type is registered with the roles its columns must have, so the same
rules both validate a request and tell a user interface which columns to offer:

- numeric:  numeric column (not bool) with at least two different values,
- category: text, bool or integer column with 2..MAX_CATEGORIES different values
            (a float column is continuous and is not treated as categories).

A constant or non-numeric column is rejected with ColumnError before anything is
drawn. Missing values are left out of a chart (only rows complete in the chosen
columns are drawn). Functions return a matplotlib Figure, so the same chart can be
embedded in Tkinter or saved to PNG, PDF or SVG. Box plot whiskers use the same
1.5 * IQR rule as the outlier detection in cleaning.py.
"""

import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import seaborn as sns
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from pandas.api.types import is_float_dtype

from datastudio import cleaning
from datastudio.errors import ColumnError, DataStudioError, RuleError

NUMERIC = "numeric"
CATEGORY = "category"
MAX_CATEGORIES = 20
EXPORT_FORMATS = ("png", "pdf", "svg")

CAUSATION_NOTE = (
    "Uwaga: korelacja mierzy tylko liniową współzmienność dwóch kolumn. Nie oznacza, że jedna "
    "wielkość powoduje drugą – obie mogą zależeć od trzeciej, "
    "nieuwzględnionej zmiennej albo być zbiegiem okoliczności."
)


@dataclass(frozen=True)
class ChartSpec:
    """What to draw: chart kind and the columns on the X and Y axes."""

    kind: str
    x: str | None = None
    y: str | None = None


@dataclass(frozen=True)
class Slot:
    role: str
    required: bool = True


@dataclass(frozen=True)
class ChartType:
    key: str
    label: str
    x: Slot | None
    y: Slot | None
    draw: Callable[[Axes, pd.DataFrame, ChartSpec], None]
    figsize: tuple[float, float] = (7, 4.5)


CHART_TYPES: dict[str, ChartType] = {}


def chart_type(key: str, label: str, x: Slot | None = None, y: Slot | None = None, figsize=(7, 4.5)):
    """Register a drawing function as a chart type."""

    def register(draw: Callable[[Axes, pd.DataFrame, ChartSpec], None]):
        CHART_TYPES[key] = ChartType(key, label, x, y, draw, figsize)
        return draw

    return register


def get_chart_type(kind: str) -> ChartType:
    if kind not in CHART_TYPES:
        raise RuleError(f"Nieznany rodzaj wykresu: {kind}", f"Dostępne rodzaje: {', '.join(CHART_TYPES)}.")
    return CHART_TYPES[kind]


# --- column roles -----------------------------------------------------------------


def _require_variation(series: pd.Series, column: str) -> None:
    distinct = series.nunique(dropna=True)
    if distinct == 0:
        raise ColumnError(f"Kolumna {column} nie zawiera żadnej wartości", "Wybierz kolumnę z danymi.")
    if distinct == 1:
        raise ColumnError(
            f"Kolumna {column} jest stała (jedyna wartość: {series.dropna().iloc[0]}) – wykres nic nie pokaże",
            "Wybierz kolumnę, której wartości się różnią.",
        )


def check_role(frame: pd.DataFrame, column: str, role: str) -> None:
    """Raise ColumnError when `column` cannot play `role` in a chart."""
    if role == NUMERIC:
        _require_variation(cleaning.require_numeric(frame, column), column)
        return
    series = cleaning.require_column(frame, column)
    if is_float_dtype(series):
        raise ColumnError(
            f"Kolumna {column} zawiera liczby ciągłe i nie nadaje się na kategorie",
            "Wybierz kolumnę tekstową albo użyj histogramu lub wykresu punktowego.",
        )
    if series.nunique(dropna=True) > MAX_CATEGORIES:
        raise ColumnError(
            f"Kolumna {column} ma {series.nunique(dropna=True)} kategorii (maksymalnie {MAX_CATEGORIES})",
            "Wybierz kolumnę z mniejszą liczbą różnych wartości.",
        )
    _require_variation(series, column)


def columns_for(frame: pd.DataFrame, role: str) -> list[str]:
    """Columns that can play `role` – used to fill the column lists of a chart."""
    valid = []
    for column in frame.columns:
        try:
            check_role(frame, column, role)
        except ColumnError:
            continue
        valid.append(column)
    return valid


def validate(frame: pd.DataFrame, spec: ChartSpec) -> ChartType:
    """Check the chart kind and the selected columns; return the chart type."""
    chart = get_chart_type(spec.kind)
    for axis, slot, column in (("X", chart.x, spec.x), ("Y", chart.y, spec.y)):
        if slot is None:
            if column is not None:
                raise RuleError(
                    f"Wykres „{chart.label}” nie używa osi {axis}", f"Usuń kolumnę {column} z osi {axis}."
                )
            continue
        if column is None:
            if slot.required:
                raise RuleError(
                    f"Nie wybrano kolumny dla osi {axis} (wykres: {chart.label})",
                    f"Wybierz kolumnę typu: {'liczbowa' if slot.role == NUMERIC else 'kategoria'}.",
                )
            continue
        check_role(frame, column, slot.role)
    if spec.x is not None and spec.x == spec.y:
        raise RuleError(f"Ta sama kolumna na obu osiach: {spec.x}", "Wybierz dwie różne kolumny.")
    return chart


def _complete(frame: pd.DataFrame, columns: list[str | None]) -> pd.DataFrame:
    """Rows without missing values in the used columns."""
    used = [column for column in columns if column is not None]
    data = frame[used].dropna()
    if data.empty:
        raise RuleError(
            "Brak rekordów z kompletnymi wartościami w wybranych kolumnach",
            "Uzupełnij braki albo wybierz inne kolumny.",
        )
    return data


def _rotate_x_labels(ax: Axes, angle: int) -> None:
    """Rotate tick labels so that their right end points at the tick."""
    for label in ax.get_xticklabels():
        label.set(rotation=angle, horizontalalignment="right", rotation_mode="anchor")


def _categories(data: pd.DataFrame, column: str) -> list:
    return sorted(data[column].unique(), key=str)


# --- chart types --------------------------------------------------------------------


@chart_type("histogram", "Histogram", x=Slot(NUMERIC))
def draw_histogram(ax: Axes, frame: pd.DataFrame, spec: ChartSpec) -> None:
    data = _complete(frame, [spec.x])
    sns.histplot(x=data[spec.x], bins="auto", ax=ax)
    ax.set(title=f"Rozkład: {spec.x}", xlabel=spec.x, ylabel="Liczba rekordów")


@chart_type("scatter", "Wykres punktowy", x=Slot(NUMERIC), y=Slot(NUMERIC))
def draw_scatter(ax: Axes, frame: pd.DataFrame, spec: ChartSpec) -> None:
    data = _complete(frame, [spec.x, spec.y])
    sns.scatterplot(data=data, x=spec.x, y=spec.y, s=14, alpha=0.5, edgecolor=None, ax=ax)
    ax.set(title=f"{spec.y} względem {spec.x}", xlabel=spec.x, ylabel=spec.y)


@chart_type("box", "Wykres pudełkowy", x=Slot(CATEGORY, required=False), y=Slot(NUMERIC))
def draw_box(ax: Axes, frame: pd.DataFrame, spec: ChartSpec) -> None:
    data = _complete(frame, [spec.x, spec.y])
    if spec.x is None:
        sns.boxplot(y=data[spec.y], ax=ax)
        ax.set(title=f"Rozkład: {spec.y}", xlabel="Wszystkie rekordy", ylabel=spec.y)
        return
    sns.boxplot(data=data, x=spec.x, y=spec.y, order=_categories(data, spec.x), ax=ax)
    ax.set(title=f"{spec.y} według {spec.x}", xlabel=spec.x, ylabel=spec.y)
    _rotate_x_labels(ax, 20)


@chart_type("bar", "Wykres słupkowy", x=Slot(CATEGORY), y=Slot(NUMERIC, required=False))
def draw_bar(ax: Axes, frame: pd.DataFrame, spec: ChartSpec) -> None:
    """Without Y: number of records per category. With Y: mean of Y per category."""
    data = _complete(frame, [spec.x, spec.y])
    order = _categories(data, spec.x)
    if spec.y is None:
        sns.countplot(data=data, x=spec.x, order=order, ax=ax)
        ax.set(title=f"Liczba rekordów według {spec.x}", xlabel=spec.x, ylabel="Liczba rekordów")
    else:
        sns.barplot(data=data, x=spec.x, y=spec.y, order=order, estimator="mean", errorbar=None, ax=ax)
        ax.set(title=f"Średnia {spec.y} według {spec.x}", xlabel=spec.x, ylabel=f"Średnia: {spec.y}")
    _rotate_x_labels(ax, 20)


@chart_type("correlation", "Macierz korelacji", figsize=(8, 6.5))
def draw_correlation(ax: Axes, frame: pd.DataFrame, spec: ChartSpec) -> None:
    matrix = correlation_matrix(frame)
    sns.heatmap(
        matrix,
        vmin=-1,
        vmax=1,
        center=0,
        cmap="coolwarm",
        annot=True,
        fmt=".2f",
        annot_kws={"size": 7},
        square=True,
        cbar_kws={"label": "współczynnik r Pearsona"},
        ax=ax,
    )
    ax.set(title="Macierz korelacji (Pearson)", xlabel="", ylabel="")
    _rotate_x_labels(ax, 45)
    ax.tick_params(axis="y", labelrotation=0)


# --- building figures -----------------------------------------------------------------


def build_chart(frame: pd.DataFrame, spec: ChartSpec) -> Figure:
    """Validate the request and draw one chart."""
    chart = validate(frame, spec)
    figure = Figure(figsize=chart.figsize, dpi=100)
    chart.draw(figure.add_subplot(), frame, spec)
    figure.tight_layout()
    return figure


def before_after_chart(before: pd.DataFrame, after: pd.DataFrame, spec: ChartSpec) -> Figure:
    """The same chart for the data before and after cleaning, side by side."""
    chart = validate(before, spec)
    validate(after, spec)
    width, height = chart.figsize
    figure = Figure(figsize=(2 * width, height), dpi=100)
    for ax, frame, stage in zip(figure.subplots(1, 2), (before, after), ("przed czyszczeniem", "po czyszczeniu")):
        chart.draw(ax, frame, spec)
        ax.set_title(f"{ax.get_title()}\n({stage}, rekordy: {len(frame)})")
    figure.tight_layout()
    return figure


def save_figure(figure: Figure, path: Path) -> Path:
    """Save to PNG, PDF or SVG (by extension). Writes a temporary file first."""
    fmt = path.suffix.lower().lstrip(".")
    if fmt not in EXPORT_FORMATS:
        raise RuleError(
            f"Nieobsługiwany format wykresu: {path.suffix or '(brak)'}", "Użyj rozszerzenia .png, .pdf albo .svg."
        )
    temporary = path.with_name(f"{path.stem}.tmp.{fmt}")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        figure.savefig(temporary, format=fmt)
        os.replace(temporary, path)
    except OSError as error:
        temporary.unlink(missing_ok=True)
        raise DataStudioError(
            f"Nie można zapisać wykresu {path}: {error}",
            "Zamknij plik otwarty w innym programie albo wybierz inny katalog.",
        ) from error
    return path


# --- correlation ----------------------------------------------------------------------


def correlation_matrix(frame: pd.DataFrame, method: str = "pearson") -> pd.DataFrame:
    """Correlation of the numeric, non-constant columns (rows with missing values skipped pairwise)."""
    if method not in ("pearson", "spearman"):
        raise RuleError(f"Nieznana metoda korelacji: {method}", "Użyj pearson albo spearman.")
    columns = columns_for(frame, NUMERIC)
    if len(columns) < 2:
        raise ColumnError(
            "Do analizy korelacji potrzebne są co najmniej dwie niestałe kolumny liczbowe",
            "Wczytaj plik z większą liczbą kolumn liczbowych.",
        )
    return frame[columns].corr(method=method)


def describe_strength(r: float) -> str:
    size = abs(r)
    strength = "słaba" if size < 0.3 else "umiarkowana" if size < 0.7 else "silna"
    return f"{strength} {'dodatnia' if r > 0 else 'ujemna'}"


def correlation_summary(frame: pd.DataFrame, top: int = 5) -> list[str]:
    """The `top` strongest pairs (by |r|) in words, followed by the causation note."""
    matrix = correlation_matrix(frame)
    columns = list(matrix.columns)
    pairs = [
        (first, second, matrix.loc[first, second])
        for index, first in enumerate(columns)
        for second in columns[index + 1 :]
        if pd.notna(matrix.loc[first, second])
    ]
    pairs.sort(key=lambda pair: abs(pair[2]), reverse=True)
    lines = [f"{first} – {second}: r = {r:+.2f} ({describe_strength(r)})" for first, second, r in pairs[:top]]
    return [*lines, CAUSATION_NOTE]
