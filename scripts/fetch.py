#!/usr/bin/env python3
"""Pobiera bieżące dane ze stacji Ecowitt (API v3) i dopisuje je do plików JSON.

Wymagane zmienne środowiskowe (GitHub Secrets):
  ECOWITT_APP_KEY, ECOWITT_API_KEY, ECOWITT_MAC
"""
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo(os.environ.get("TZ_NAME", "Europe/Warsaw"))
ROOT = Path(__file__).resolve().parent.parent / "data"
DAYS = ROOT / "days"

params = {
    "application_key": os.environ["ECOWITT_APP_KEY"],
    "api_key": os.environ["ECOWITT_API_KEY"],
    "mac": os.environ["ECOWITT_MAC"],
    "call_back": "all",
    "temp_unitid": 1,              # °C
    "pressure_unitid": 3,          # hPa
    "wind_speed_unitid": 6,        # m/s  (7 = km/h)
    "rainfall_unitid": 12,         # mm
    "solar_irradiance_unitid": 16, # W/m²
}
url = "https://api.ecowitt.net/api/v3/device/real_time?" + urllib.parse.urlencode(params)

with urllib.request.urlopen(url, timeout=30) as r:
    resp = json.load(r)

if resp.get("code") != 0:
    sys.exit(f"Błąd API Ecowitt: {resp.get('code')} {resp.get('msg')}")


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


flat = flatten(resp.get("data") or {})
if not flat:
    sys.exit("Brak danych w odpowiedzi API")

ts = max(t for _, _, t in flat.values()) or int(datetime.now().timestamp())
values = {k: v for k, (v, _, _) in flat.items()}
units = {k: u for k, (_, u, _) in flat.items()}

# --- latest.json: bieżący stan ---
ROOT.mkdir(exist_ok=True)
(ROOT / "latest.json").write_text(
    json.dumps({"t": ts, "values": values, "units": units}, ensure_ascii=False, indent=1),
    encoding="utf-8",
)

# --- days/YYYY-MM-DD.json: historia dnia ---
DAYS.mkdir(exist_ok=True)
day = datetime.fromtimestamp(ts, TZ).strftime("%Y-%m-%d")
day_file = DAYS / f"{day}.json"
rows = json.loads(day_file.read_text(encoding="utf-8")) if day_file.exists() else []
if rows and rows[-1]["t"] >= ts:
    print("Brak nowego pomiaru – pomijam.")
else:
    rows.append({"t": ts, **values})
    day_file.write_text(json.dumps(rows, separators=(",", ":")), encoding="utf-8")
    print(f"Zapisano pomiar {datetime.fromtimestamp(ts, TZ)} ({len(values)} wartości)")

# --- index.json: lista dostępnych dni ---
days = sorted(p.stem for p in DAYS.glob("*.json"))
(ROOT / "index.json").write_text(json.dumps({"days": days}), encoding="utf-8")
