# USOS Room Finder

Narzędzie CLI do wyszukiwania wolnych sal na AGH na podstawie danych z USOSweb. Skrypt pobiera plany zajęć dla wybranych budynków, zapisuje je w cache lokalnie i pozwala na szybkie znalezienie dostępnych pomieszczeń w określonym czasie.

## Funkcje

- **Pobieranie danych:** Automatyczne pobieranie planów zajęć bezpośrednio z USOSweb.
- **Inteligentny Cache:** Przechowywanie pobranych stron HTML w celu przyspieszenia kolejnych wyszukiwań. Skrypt parsuje tylko dane z tygodnia, którego dotyczy zapytanie, co zapobiega błędom w harmonogramie.
- **Automatyczne czyszczenie:** Usuwanie nieaktualnych plików cache (starszych niż bieżący tydzień).
- **Filtrowanie:** Możliwość wyszukiwania po budynku, minimalnej pojemności sali, dacie i godzinie.
- **Naturalne Sortowanie:** Wyniki są sortowane alfabetycznie i numerycznie według numeru sali (np. sala 10 przed 100).
- **Eksport danych:** Obsługa formatów CSV i JSON bezpośrednio do standardowego wyjścia (stdout).

## Instalacja

Wymagany Python 3.6+.

```bash
git clone https://github.com/zgredinzyyy/usos-room-finder.git
cd usos-room-finder
```
## Użycie
```
usage: usos_room_finder.py [-h] --date DATE --start START --end END [--capacity CAPACITY] [--building BUILDING] [--dir DIR] [--renew] [--verbose] [--no-cleanup] [--csv] [--json]

USOS Room Finder - Znajdź wolną salę.

options:
  -h, --help           show this help message and exit
  --date DATE          Data (DD-MM-RRRR), np. 11-05-2026
  --start START        Godzina rozpoczęcia (GG:MM), np. 12:00
  --end END            Godzina zakończenia (GG:MM), np. 14:00
  --capacity CAPACITY  Minimalna liczba miejsc
  --building BUILDING  Kod budynku lub lista (np. B9, D4)
  --dir DIR            Katalog na pobrane dane (domyślnie 'data')
  --renew              Wymuś odświeżenie danych (pobierz ponownie)
  --verbose            Wyświetlaj szczegółowe informacje o pobieraniu
  --no-cleanup         Wyłącz automatyczne czyszczenie starego cache'u
  --csv                Wyświetl wyniki w formacie CSV
  --json               Wyświetl wyniki w formacie JSON
```


## Przykłady użycia

### 1. Podstawowe wyszukiwanie
Znajdź wolną salę na dzisiaj (np. 11-05-2026) w godzinach 12:00 - 14:00:
```bash
python3 usos_room_finder.py --date 11-05-2026 --start 12:00 --end 14:00
```

### 2. Wyszukiwanie w konkretnych budynkach
Szukaj tylko w budynkach B9 i D5:
```bash
python3 usos_room_finder.py --date 11-05-2026 --start 08:00 --end 10:00 --building B9,D5
```

### 3. Eksport do JSON
Zapisz wyniki wyszukiwania do pliku JSON:
```bash
python3 usos_room_finder.py --date 11-05-2026 --start 10:00 --end 12:00 --json > wyniki.json
```

### 4. Eksport do CSV
Wyświetl wyniki w formacie CSV:
```bash
python3 usos_room_finder.py --date 11-05-2026 --start 10:00 --end 12:00 --csv
```

### 5. Odświeżenie danych
Jeśli chcesz wymusić ponowne pobranie planów (np. gdy plan w USOS się zmienił):
```bash
python3 usos_room_finder.py --date 11-05-2026 --start 12:00 --end 14:00 --renew
```

### 6. Tryb szczegółowy (Verbose)
Zobacz szczegóły procesu pobierania i parsowania:
```bash
python3 usos_room_finder.py --date 11-05-2026 --start 12:00 --end 14:00 --verbose
```

## Jak to działa?

1. **Mapowanie budynków:** Skrypt próbuje dopasować fizyczny kod budynku (np. B9) do wewnętrznego ID USOS.
2. **Cache:** Pobrane plany sal są zapisywane w katalogu `data/` z datą poniedziałku danego tygodnia.
3. **Czyszczenie:** Przy każdym uruchomieniu skrypt sprawdza daty w nazwach plików i usuwa te, które odnoszą się do przeszłych tygodni.
4. **Analiza:** Parser HTML analizuje tagi `<timetable-entry>` w celu wyznaczenia zajętości sali. Podczas wyszukiwania wczytywane są tylko pliki dotyczące konkretnego tygodnia zapytania.

## Ostrzeżenie

Narzędzie służy do celów edukacyjnych. Pamiętaj o zachowaniu rozsądnych odstępów między zapytaniami do serwerów USOSweb (skrypt ma wbudowane opóźnienia `time.sleep`).
