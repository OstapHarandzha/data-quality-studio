"""Command-line cleaning pipeline: python -m datastudio.pipeline FILE [options].

Writes cleaned.csv, report.txt (before/after) and audit_log.csv to the output
directory. Order of steps: full duplicates -> range rules -> missing values ->
outliers. Range violations become missing values by default, so the next step
can fill them. Outliers are only counted unless columns are named explicitly.
"""

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from datastudio import profile
from datastudio.errors import DataStudioError, RuleError
from datastudio.session import BOUND_ACTIONS, DataSession

MISSING_STRATEGIES = ("median", "mean", "mode", "drop")


@dataclass(frozen=True)
class RangeRule:
    column: str
    minimum: float | None
    maximum: float | None


@dataclass(frozen=True)
class PipelineConfig:
    missing: str = "median"
    ranges: tuple[RangeRule, ...] = ()
    range_action: str = "missing"
    outlier_columns: tuple[str, ...] = ()
    outlier_action: str = "flag"
    iqr_factor: float = 1.5


def parse_range(text: str) -> RangeRule:
    """Parse COLUMN:MIN:MAX; an empty MIN or MAX means no bound on that side."""
    parts = text.rsplit(":", 2)
    try:
        column, low, high = parts
        return RangeRule(column, float(low) if low else None, float(high) if high else None)
    except ValueError as error:
        raise RuleError(
            f"Niepoprawna reguła zakresu: {text}",
            "Użyj formatu KOLUMNA:MIN:MAX, np. housing_median_age:0:100.",
        ) from error


def quality_findings(session: DataSession, config: PipelineConfig) -> list[str]:
    """Describe detected problems without changing the data."""
    lines = []
    for rule in config.ranges:
        count = session.count_out_of_range(rule.column, rule.minimum, rule.maximum)
        lines.append(f"Zakres {rule.column} [{rule.minimum}, {rule.maximum}]: rekordy poza zakresem: {count}")
    for column in profile.numeric_columns(session.current):
        count = session.count_outliers(column, config.iqr_factor)
        lines.append(f"Outliery IQR (k={config.iqr_factor}) w {column}: {count}")
    return lines


def handle_missing(session: DataSession, strategy: str) -> None:
    if strategy == "drop":
        session.drop_missing()
        return
    numeric = profile.numeric_columns(session.current)
    for column in session.current.columns:
        if session.current[column].isna().any():
            # Mean and median do not exist for text, so text columns use the mode.
            session.fill_missing(column, strategy if column in numeric else "mode")


def clean(session: DataSession, config: PipelineConfig) -> None:
    session.drop_duplicates()
    for rule in config.ranges:
        session.handle_out_of_range(rule.column, rule.minimum, rule.maximum, config.range_action)
    handle_missing(session, config.missing)
    for column in config.outlier_columns:
        session.handle_outliers(column, config.outlier_action, config.iqr_factor)


def table_section(title: str, frame: pd.DataFrame) -> list[str]:
    stats = profile.overview(frame)
    return [
        f"== {title} ==",
        f"Rekordy: {stats['rows']}, kolumny: {stats['columns']}, "
        f"pełne duplikaty: {stats['duplicates']}, brakujące komórki: {stats['missing_cells']}",
        "",
        profile.column_profile(frame).to_string(),
        "",
        profile.describe_numeric(frame).to_string(),
        "",
    ]


def build_report(source: Path, session: DataSession, findings: list[str]) -> str:
    lines = ["RAPORT JAKOŚCI DANYCH", f"Plik: {source.name}", ""]
    lines += table_section("Przed czyszczeniem", session.raw)
    lines += ["== Reguły jakości (dane surowe) ==", *findings, ""]
    lines += ["== Wykonane operacje ==", session.audit_frame().to_string(index=False), ""]
    lines += table_section("Po czyszczeniu", session.current)
    return "\n".join(lines)


def run(source: Path, output: Path, config: PipelineConfig) -> DataSession:
    if config.missing not in MISSING_STRATEGIES:
        raise RuleError(
            f"Nieznana strategia braków: {config.missing}",
            f"Dostępne strategie: {', '.join(MISSING_STRATEGIES)}.",
        )
    session = DataSession.from_csv(source)
    findings = quality_findings(session, config)
    clean(session, config)
    try:
        output.mkdir(parents=True, exist_ok=True)
        session.current.to_csv(output / "cleaned.csv", index=False, encoding="utf-8-sig")
        session.audit_frame().to_csv(output / "audit_log.csv", index=False, encoding="utf-8-sig")
        (output / "report.txt").write_text(build_report(source, session, findings), encoding="utf-8")
    except OSError as error:
        raise DataStudioError(
            f"Nie można zapisać wyników w {output}: {error}",
            "Zamknij pliki otwarte w innym programie albo wybierz inny katalog.",
        ) from error
    return session


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m datastudio.pipeline", description="Czyszczenie pliku CSV.")
    parser.add_argument("source", type=Path, help="plik CSV")
    parser.add_argument("--output", type=Path, default=Path("output"), help="katalog wyników")
    parser.add_argument("--missing", choices=MISSING_STRATEGIES, default="median", help="strategia braków")
    parser.add_argument("--range", action="append", default=[], metavar="KOLUMNA:MIN:MAX", help="reguła zakresu")
    parser.add_argument("--range-action", choices=BOUND_ACTIONS, default="missing")
    parser.add_argument("--outlier-columns", nargs="*", default=[], help="kolumny, w których obsłużyć outliery")
    parser.add_argument("--outlier-action", choices=BOUND_ACTIONS, default="flag")
    parser.add_argument("--iqr-factor", type=float, default=1.5)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        config = PipelineConfig(
            missing=args.missing,
            ranges=tuple(parse_range(text) for text in args.range),
            range_action=args.range_action,
            outlier_columns=tuple(args.outlier_columns),
            outlier_action=args.outlier_action,
            iqr_factor=args.iqr_factor,
        )
        session = run(args.source, args.output, config)
    except DataStudioError as error:
        print(f"Błąd: {error.message}", file=sys.stderr)
        if error.hint:
            print(error.hint, file=sys.stderr)
        return 1
    print(session.audit_frame().to_string(index=False))
    print(f"Rekordy: {len(session.raw)} -> {len(session.current)}. Wyniki zapisano w: {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
