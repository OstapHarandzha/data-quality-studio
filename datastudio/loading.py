"""Loading CSV files.

The separator is chosen by counting candidates in the header line, so the result
is predictable. Encoding: UTF-8 (with or without BOM) first, then Windows-1250.
A row with too many fields stops the load with a controlled error; a row with
too few fields is filled with missing values (standard pandas behaviour).
"""

from pathlib import Path

import pandas as pd

from datastudio.errors import LoadError

SEPARATORS = (",", ";", "\t")
ENCODINGS = ("utf-8-sig", "cp1250")


def read_text(path: Path) -> tuple[str, str]:
    """Return the file content and the encoding that decoded it."""
    try:
        data = path.read_bytes()
    except OSError as error:
        raise LoadError(
            f"Nie można otworzyć pliku: {path}",
            "Sprawdź, czy plik istnieje i czy masz do niego dostęp.",
        ) from error
    for encoding in ENCODINGS:
        try:
            return data.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    raise LoadError(
        f"Nieobsługiwane kodowanie pliku: {path.name}",
        "Zapisz plik w kodowaniu UTF-8 i wczytaj go ponownie.",
    )


def detect_separator(header: str) -> str:
    """Pick the candidate that occurs most often in the header line."""
    return max(SEPARATORS, key=header.count)


def load_csv(path: Path) -> pd.DataFrame:
    """Read a CSV file into a DataFrame or raise LoadError."""
    text, encoding = read_text(path)
    if not text.strip():
        raise LoadError(f"Plik jest pusty: {path.name}", "Wybierz plik CSV z nagłówkiem i danymi.")
    separator = detect_separator(text.splitlines()[0])
    try:
        frame = pd.read_csv(path, sep=separator, encoding=encoding)
    except pd.errors.ParserError as error:
        raise LoadError(
            f"Wadliwy wiersz w pliku {path.name}: {error}",
            "Popraw liczbę pól we wskazanym wierszu i wczytaj plik ponownie.",
        ) from error
    if frame.empty:
        raise LoadError(
            f"Plik nie zawiera rekordów: {path.name}",
            "Wybierz plik, który oprócz nagłówka ma co najmniej jeden wiersz danych.",
        )
    return frame
