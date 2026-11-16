# Studio jakości i wizualizacji danych

Projekt 2 – Programowanie V. Aplikacja desktopowa (Python 3 + Tkinter/ttk), która prowadzi użytkownika
od wczytania pliku CSV przez diagnozę i czyszczenie danych do wizualizacji i eksportu wyników.

Repozytorium (historia zmian): https://github.com/OstapHarandzha/data-quality-studio

> **Status:** Lab 6 – wczytywanie CSV, profil danych, reguły jakości i pipeline czyszczenia
> uruchamiany z wiersza poleceń. Wykresy (Lab 7) i GUI (Lab 8–9) są w przygotowaniu.

## Wymagania

- Python 3.10+ (testowane na 3.13, Windows) z modułem Tkinter
- Biblioteki z `requirements.txt`: `pandas`, `matplotlib`, `seaborn`, `pytest`

## Instalacja

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Uruchomienie – pipeline czyszczenia

```powershell
python -m datastudio.pipeline samples/housing_comma.csv --range housing_median_age:0:100 --outlier-columns median_income
```

W katalogu `output/` powstają: `cleaned.csv` (oczyszczone dane), `report.txt` (profil przed i po,
wykryte problemy, lista operacji) oraz `audit_log.csv` (ślad zmian).

| Opcja | Znaczenie | Domyślnie |
|---|---|---|
| `--output KATALOG` | katalog wyników | `output` |
| `--missing` | strategia braków: `median`, `mean`, `mode`, `drop` | `median` |
| `--range KOLUMNA:MIN:MAX` | reguła zakresu (można podać kilka; pusta granica = brak ograniczenia) | brak |
| `--range-action` | co zrobić z wartością poza zakresem: `missing`, `clip`, `remove`, `flag` | `missing` |
| `--outlier-columns K1 K2` | kolumny, w których outliery mają zostać obsłużone | brak |
| `--outlier-action` | co zrobić z outlierem: `flag`, `clip`, `remove`, `missing` | `flag` |
| `--iqr-factor` | współczynnik k w regule IQR | `1.5` |

## Reguły czyszczenia

Kolejność kroków: duplikaty → reguły zakresu → braki → outliery.

- **Wczytywanie:** separator (`,` `;` lub tabulator) jest wybierany po liczbie wystąpień w nagłówku;
  kodowanie UTF-8, a gdy się nie uda – Windows-1250. Wiersz z nadmiarowym polem przerywa wczytywanie
  z komunikatem; wiersz z brakującymi polami jest uzupełniany brakami.
- **Duplikaty:** usuwane są tylko pełne duplikaty (zostaje pierwszy rekord).
- **Zakres:** wartość poza zakresem jest błędem pojedynczej komórki, dlatego domyślnie staje się brakiem
  i jest uzupełniana w następnym kroku – reszta rekordu zostaje.
- **Braki:** kolumny liczbowe są uzupełniane medianą (odporna na wartości skrajne), średnią albo
  dominantą; kolumny tekstowe zawsze dominantą. `drop` usuwa rekordy z jakimkolwiek brakiem.
- **Outliery:** reguła IQR – wartość poniżej Q1 − k·IQR lub powyżej Q3 + k·IQR. Wartość odstająca nie
  musi być błędem, więc pipeline tylko je zlicza w raporcie. Zmiana następuje wyłącznie w kolumnach
  wskazanych w `--outlier-columns`, domyślnie przez oznaczenie w kolumnie `<kolumna>_outlier`.
- **Ślad zmian:** każda operacja zapisuje czas, parametry, liczbę rekordów przed i po oraz liczbę
  rekordów, których dotyczyła. Dane surowe nie są modyfikowane.

## Testy

```powershell
python -m pytest
```

Testy działają na małych, ręcznie przygotowanych tabelach i plikach z katalogu `samples/`
(opis plików i oczekiwanych wyników: `samples/README.md`).

## Struktura projektu

```
datastudio/
  errors.py     # model błędów: przyczyna + wskazówka
  loading.py    # wczytywanie CSV
  profile.py    # profil danych
  cleaning.py   # operacje czyszczenia (czyste funkcje)
  session.py    # sesja: dane surowe, dane aktualne, ślad zmian
  pipeline.py   # pipeline uruchamiany z wiersza poleceń
samples/        # dane testowe
tests/          # testy pytest
```

## Znane ograniczenia

- Liczby z przecinkiem dziesiętnym (np. `3,14` w pliku ze średnikami) są wczytywane jako tekst.

## Źródła i narzędzia

- Dokumentacja pandas: https://pandas.pydata.org/docs/
- Narzędzia AI: przy pisaniu kodu, testów i dokumentacji korzystałem z asystenta Claude (Anthropic).

## Autor

Ostap Harandzha
