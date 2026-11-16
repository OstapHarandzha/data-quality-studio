"""Session model: raw data, current data and the audit log of operations.

`raw` is never modified. Every operation replaces `current` with a new frame and
appends one AuditEntry with its parameters, time, row counts and the number of
affected records. Detection methods (count_*) change nothing and log nothing.
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import pandas as pd

from datastudio import cleaning
from datastudio.errors import RuleError
from datastudio.loading import load_csv

BOUND_ACTIONS = ("flag", "missing", "clip", "remove")


def _bound(value: float | None) -> str:
    return "brak" if value is None else f"{value:g}"


@dataclass(frozen=True)
class AuditEntry:
    time: str
    operation: str
    parameters: str
    rows_before: int
    rows_after: int
    affected: int


@dataclass
class DataSession:
    raw: pd.DataFrame
    current: pd.DataFrame = field(init=False)
    audit_log: list[AuditEntry] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.current = self.raw.copy(deep=True)

    @classmethod
    def from_csv(cls, path: Path) -> "DataSession":
        return cls(load_csv(path))

    def _commit(self, result: pd.DataFrame, operation: str, parameters: str, affected: int) -> int:
        """Make `result` the current data and record the operation."""
        entry = AuditEntry(
            time=datetime.now().isoformat(timespec="seconds"),
            operation=operation,
            parameters=parameters,
            rows_before=len(self.current),
            rows_after=len(result),
            affected=affected,
        )
        self.current = result
        self.audit_log.append(entry)
        return affected

    def drop_duplicates(self, subset: list[str] | None = None) -> int:
        result = cleaning.drop_duplicates(self.current, subset)
        key = ", ".join(subset) if subset else "pełne rekordy"
        return self._commit(result, "Usunięcie duplikatów", f"klucz: {key}", len(self.current) - len(result))

    def drop_missing(self, columns: list[str] | None = None) -> int:
        result = cleaning.drop_missing(self.current, columns)
        scope = ", ".join(columns) if columns else "wszystkie"
        return self._commit(
            result, "Usunięcie rekordów z brakami", f"kolumny: {scope}", len(self.current) - len(result)
        )

    def fill_missing(self, column: str, strategy: str) -> int:
        value = cleaning.fill_value(self.current, column, strategy)
        missing = int(self.current[column].isna().sum())
        result = cleaning.fill_missing(self.current, column, value)
        shown = f"{value:g}" if isinstance(value, float) else value
        return self._commit(
            result, "Uzupełnienie braków", f"kolumna: {column}, strategia: {strategy}, wartość: {shown}", missing
        )

    def count_out_of_range(self, column: str, minimum: float | None, maximum: float | None) -> int:
        return int(cleaning.outside_mask(self.current, column, minimum, maximum).sum())

    def handle_out_of_range(self, column: str, minimum: float | None, maximum: float | None, action: str) -> int:
        return self._apply_bounds("Reguła zakresu", column, minimum, maximum, action, f"{column}_out_of_range")

    def count_outliers(self, column: str, factor: float = 1.5) -> int:
        lower, upper = cleaning.iqr_bounds(self.current, column, factor)
        return int(cleaning.outside_mask(self.current, column, lower, upper).sum())

    def handle_outliers(self, column: str, action: str, factor: float = 1.5) -> int:
        lower, upper = cleaning.iqr_bounds(self.current, column, factor)
        return self._apply_bounds(f"Outliery IQR (k={factor})", column, lower, upper, action, f"{column}_outlier")

    def _apply_bounds(
        self, operation: str, column: str, lower: float | None, upper: float | None, action: str, flag_column: str
    ) -> int:
        """Apply the chosen action to the rows of `column` outside [lower, upper]."""
        if action not in BOUND_ACTIONS:
            raise RuleError(f"Nieznane działanie: {action}", f"Dostępne działania: {', '.join(BOUND_ACTIONS)}.")
        mask = cleaning.outside_mask(self.current, column, lower, upper)
        if action == "flag":
            result = cleaning.flag_rows(self.current, mask, flag_column)
        elif action == "missing":
            result = cleaning.set_missing(self.current, column, mask)
        elif action == "clip":
            result = cleaning.clip_column(self.current, column, lower, upper)
        else:
            result = cleaning.remove_rows(self.current, mask)
        parameters = f"kolumna: {column}, zakres: [{_bound(lower)}, {_bound(upper)}], działanie: {action}"
        return self._commit(result, operation, parameters, int(mask.sum()))

    def reset(self) -> None:
        self._commit(self.raw.copy(deep=True), "Przywrócenie danych surowych", "", 0)

    def audit_frame(self) -> pd.DataFrame:
        return pd.DataFrame(self.audit_log, columns=list(AuditEntry.__dataclass_fields__))
