#!/usr/bin/env python3
"""Jednorazowe pobranie historii ze stacji Ecowitt (API v3, history).

Ecowitt przechowuje dane 5-minutowe ok. 90 dni, a 30-minutowe ok. 365 dni,
więc dla ostatnich 90 dni pobieramy co 5 min, dla starszych co 30 min.
Użycie: python3 scripts/backfill.py [liczba_dni]   (domyślnie 365)
"""
import sys
import time
from datetime import datetime, timedelta

import store

CALL_BACK = "outdoor,indoor,solar_and_uvi,rainfall,rainfall_piezo,wind,pressure"
days = int(sys.argv[1]) if len(sys.argv) > 1 else 365
today = datetime.now(store.TZ).replace(hour=0, minute=0, second=0, microsecond=0)


def flatten_history(node, prefix=""):
    """{'outdoor': {'temperature': {'unit': '℃', 'list': {'1731400000': '5.2'}}}}
    -> {ts: {'outdoor.temperature': 5.2}}"""
    rows = {}
    for k, v in node.items():
        key = f"{prefix}{k}"
        if isinstance(v, dict) and isinstance(v.get("list"), dict):
            for t, val in v["list"].items():
                try:
                    rows.setdefault(int(t), {})[key] = float(val)
                except (TypeError, ValueError):
                    pass
        elif isinstance(v, dict):
            for t, rec in flatten_history(v, key + ".").items():
                rows.setdefault(t, {}).update(rec)
    return rows


all_months, total, errors = set(), 0, 0
for i in range(days, -1, -1):
    start = today - timedelta(days=i)
    cycle = "5min" if i < 89 else "30min"
    try:
        data = store.api("history", call_back=CALL_BACK, cycle_type=cycle,
                         start_date=start.strftime("%Y-%m-%d 00:00:00"),
                         end_date=start.strftime("%Y-%m-%d 23:59:59"))
        rows = [{"t": t, **rec} for t, rec in flatten_history(data).items()]
        if rows:
            all_months.update(store.merge_rows(rows))
            total += len(rows)
        print(f"{start:%Y-%m-%d} [{cycle}]: {len(rows)} rekordów", flush=True)
    except Exception as e:  # pojedynczy dzień nie powinien przerywać całości
        errors += 1
        print(f"{start:%Y-%m-%d}: BŁĄD {e}", flush=True)
        if errors > 20:
            sys.exit("Zbyt wiele błędów – przerywam.")
    time.sleep(1.2)  # limit zapytań API

store.rebuild_hourly(sorted(all_months))
store.rebuild_index()
store.rebuild_rain_norms()
print(f"Gotowe: {total} rekordów, {len(all_months)} miesięcy, błędów: {errors}")
