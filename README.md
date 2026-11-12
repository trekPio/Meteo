# Moje meteo – strona stacji Ecowitt na GitHub Pages

GitHub Actions co ~10 min pobiera dane z API Ecowitt i zapisuje je do `data/`.
Statyczna strona `index.html` rysuje z nich wykresy (amCharts 5). Bez serwera i bez PHP.

## Uruchomienie

1. **Klucze Ecowitt**: na ecowitt.net → *User Profile* → *Private Center*:
   utwórz **Application Key** i **API Key**. Adres **MAC** stacji znajdziesz w *My Devices*.
2. **Repozytorium**: utwórz nowe repo na GitHubie (publiczne, bo Pages za darmo działa tylko dla publicznych)
   i wgraj do niego zawartość tego folderu.
3. **Sekrety**: *Settings → Secrets and variables → Actions → New repository secret*:
   `ECOWITT_APP_KEY`, `ECOWITT_API_KEY`, `ECOWITT_MAC` (format `AA:BB:CC:DD:EE:FF`).
4. **Uprawnienia**: *Settings → Actions → General → Workflow permissions* → **Read and write permissions**.
5. **Pierwsze pobranie**: *Actions → Pobierz dane Ecowitt → Run workflow*. Po chwili w `data/` pojawi się `latest.json`.
6. **Strona**: *Settings → Pages → Source: Deploy from a branch → `main` / `(root)`*.
   Strona będzie pod adresem `https://<login>.github.io/<repo>/`.

## Dostosowanie

- **Częstotliwość**: `cron` w `.github/workflows/fetch.yml`. Nie ustawiaj częściej niż co 10 min,
  bo GitHub Pages ma limit ok. 10 przebudowań strony na godzinę.
- **Jednostki**: parametry `*_unitid` w `scripts/fetch.py`, np. `wind_speed_unitid: 7` to km/h.
  Po zmianie popraw też jednostki w tablicach `GAUGES` i `CHARTS` w `index.html`.
- **Czujniki**: skrypt zapisuje wszystko, co zwraca API. Żeby dodać wykres, np. dla czujnika `temp_and_humidity_ch1.temperature`,
  dopisz klucz do `K` i serię do `CHARTS` w `index.html`. Pełną listę kluczy masz w `data/latest.json`.

## Uwagi

- GitHub uruchamia zaplanowane zadania z opóźnieniem (czasem 10–30 min), więc to nie jest podgląd na żywo.
- Każdy pomiar to jeden commit. Dane zajmują mało miejsca (ok. 20–40 KB na dzień), ale historia commitów rośnie.
