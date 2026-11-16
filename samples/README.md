# Dane testowe

Małe, ręcznie przygotowane pliki. Polecenia uruchamiaj z katalogu projektu.

| Plik | Co sprawdza | Polecenie | Oczekiwany wynik |
|---|---|---|---|
| `housing_comma.csv` | separator „,”; 1 pełny duplikat, 2 braki liczbowe (`total_bedrooms`), 1 brak tekstowy (`ocean_proximity`), wiek `-5` poza zakresem, dochód `95.0` jako outlier | `python -m datastudio.pipeline samples/housing_comma.csv --range housing_median_age:0:100 --outlier-columns median_income` | 14 → 13 rekordów; 1 duplikat usunięty; 1 wartość poza zakresem zamieniona na brak; braki uzupełnione (3 medianą, 1 dominantą); 1 outlier oznaczony w kolumnie `median_income_outlier` |
| `housing_semicolon.csv` | te same dane z separatorem „;” | `python -m datastudio.pipeline samples/housing_semicolon.csv` | 10 kolumn, wynik jak wyżej (bez reguły zakresu i oznaczania outlierów) |
| `broken_row.csv` | wiersz z nadmiarowym polem | `python -m datastudio.pipeline samples/broken_row.csv` | `Błąd: Wadliwy wiersz...` z numerem wiersza, kod wyjścia 1, brak plików wynikowych |
| `header_only.csv` | sam nagłówek, bez danych | `python -m datastudio.pipeline samples/header_only.csv` | `Błąd: Plik nie zawiera rekordów...`, kod wyjścia 1 |

Wyniki (`cleaned.csv`, `report.txt`, `audit_log.csv`) trafiają do katalogu `output/`.
