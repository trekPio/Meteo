#!/usr/bin/env python3
"""Pobiera bieżący pomiar ze stacji Ecowitt (API v3, real_time).

Zmienne środowiskowe (GitHub Secrets): ECOWITT_APP_KEY, ECOWITT_API_KEY, ECOWITT_MAC
"""
import json
import os
import sys
from datetime import datetime

import store


def flatten(node, prefix=""):
    """{'outdoor': {'temperature': {'value': '5.1', 'unit': '℃', 'time': '...'}}}
    -> {'outdoor.temperature': (5.1, '℃', 1731400000)}"""
    out = {}
    for k, v in node.items():
        key = f"{prefix}{k}"
        if isinstance(v, dict) and "value" in v:
            try:
                out[key] = (float(v["value"]), v.get("unit", ""), int(v.get("time") or 0))
            except (TypeError, ValueError):
                pass
        elif isinstance(v, dict):
            out.update(flatten(v, key + "."))
    return out


flat = flatten(store.api("real_time", call_back="all"))
if not flat:
    sys.exit("Brak danych w odpowiedzi API")

ts = max(t for _, _, t in flat.values()) or int(datetime.now().timestamp())
values = {k: v for k, (v, _, _) in flat.items()}
units = {k: u for k, (_, u, _) in flat.items()}

store.ROOT.mkdir(exist_ok=True)
(store.ROOT / "latest.json").write_text(
    json.dumps({"t": ts, "src": os.environ.get("FETCH_SOURCE", "auto"), "fetched": int(datetime.now().timestamp()), "values": values, "units": units}, ensure_ascii=False, indent=1), encoding="utf-8")

months = store.merge_rows([{"t": ts, **values}])
store.rebuild_hourly(months)
store.rebuild_index()
store.rebuild_rain_norms()
print(f"Zapisano pomiar {datetime.fromtimestamp(ts, store.TZ)} ({len(values)} wartości)")
