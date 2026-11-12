"""Wspólny zapis danych: pliki dzienne, indeks i agregaty godzinowe (dla widoku rocznego)."""
import json
import os
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo(os.environ.get("TZ_NAME", "Europe/Warsaw"))
ROOT = Path(__file__).resolve().parent.parent / "data"
DAYS = ROOT / "days"
HOURLY = ROOT / "hourly"

UNITS = {
    "temp_unitid": 1,              # °C
    "pressure_unitid": 3,          # hPa
    "wind_speed_unitid": 6,        # m/s  (7 = km/h)
    "rainfall_unitid": 12,         # mm
    "solar_irradiance_unitid": 16, # W/m²
}
# Wartości narastające (sumy opadu) agregujemy maksimum, resztę średnią
CUMULATIVE = ("daily", "weekly", "monthly", "yearly", "event", "hour", "24_hours")


def api(endpoint, **extra):
    params = {
        "application_key": os.environ["ECOWITT_APP_KEY"],
        "api_key": os.environ["ECOWITT_API_KEY"],
        "mac": os.environ["ECOWITT_MAC"],
        **UNITS, **extra,
    }
    url = f"https://api.ecowitt.net/api/v3/device/{endpoint}?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=60) as r:
        resp = json.load(r)
    if resp.get("code") != 0:
        raise RuntimeError(f"Błąd API Ecowitt: {resp.get('code')} {resp.get('msg')}")
    data = resp.get("data")
    return data if isinstance(data, dict) else {}


def day_of(ts):
    return datetime.fromtimestamp(ts, TZ).strftime("%Y-%m-%d")


def merge_rows(rows):
    """Dopisuje rekordy {t, klucz: wartość} do plików dziennych (scalanie po czasie)."""
    by_day = defaultdict(list)
    for r in rows:
        by_day[day_of(r["t"])].append(r)
    DAYS.mkdir(parents=True, exist_ok=True)
    for day, new in by_day.items():
        f = DAYS / f"{day}.json"
        merged = {r["t"]: r for r in (json.loads(f.read_text()) if f.exists() else [])}
        for r in new:
            merged[r["t"]] = {**merged.get(r["t"], {}), **r}
        f.write_text(json.dumps([merged[t] for t in sorted(merged)], separators=(",", ":")))
    return sorted({d[:7] for d in by_day})


def rebuild_hourly(months):
    """Przelicza agregaty godzinowe dla podanych miesięcy (RRRR-MM)."""
    HOURLY.mkdir(parents=True, exist_ok=True)
    for month in months:
        buckets = defaultdict(lambda: defaultdict(list))
        for f in sorted(DAYS.glob(f"{month}-*.json")):
            for r in json.loads(f.read_text()):
                h = r["t"] - r["t"] % 3600
                for k, v in r.items():
                    if k != "t" and v is not None:
                        buckets[h][k].append(v)
        out = []
        for h in sorted(buckets):
            rec = {"t": h + 1800}
            for k, vals in buckets[h].items():
                rec[k] = round(max(vals) if any(c in k for c in CUMULATIVE) else sum(vals) / len(vals), 2)
            out.append(rec)
        (HOURLY / f"{month}.json").write_text(json.dumps(out, separators=(",", ":")))


def rebuild_index():
    days = sorted(p.stem for p in DAYS.glob("*.json"))
    months = sorted(p.stem for p in HOURLY.glob("*.json"))
    (ROOT / "index.json").write_text(json.dumps({"days": days, "months": months}))
