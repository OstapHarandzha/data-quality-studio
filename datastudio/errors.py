"""Error model: every expected failure carries a cause and a next step for the user."""


class DataStudioError(Exception):
    """Base error. `message` says what went wrong, `hint` says what to do next."""

    def __init__(self, message: str, hint: str = "") -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint


class LoadError(DataStudioError):
    """The file could not be read as a CSV table."""


class ColumnError(DataStudioError):
    """The column is missing or has the wrong type for the operation."""


class RuleError(DataStudioError):
    """The parameters of a quality rule or cleaning operation are invalid."""
