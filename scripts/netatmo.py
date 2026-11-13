#!/usr/bin/env python3
"""Pobiera dane publicznych stacji Netatmo z okolicy (getpublicdata) do data/netatmo.json.

Zmienne środowiskowe (GitHub Secrets):
  NETATMO_CLIENT_ID, NETATMO_CLIENT_SECRET, NETATMO_REFRESH_TOKEN
  GH_TOKEN (opcjonalnie) – PAT z prawem zapisu sekretów; gdy Netatmo zwróci nowy
           refresh token, skrypt podmienia sekret NETATMO_REFRESH_TOKEN w repo.
"""
import json
import math
import os
import subprocess
import sys
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "data"

# Punkt odniesienia (Kowal) i prostokąt: Kowal – Janowo – Włocławek – Szpetal
HOME = (52.531, 19.146)
BOX = {"lat_ne": 52.72, "lon_ne": 19.20, "lat_sw": 52.45, "lon_sw": 18.90}

API = "https://api.netatmo.com"


def post(url, data):
    req = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode(), method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def get(url, token, params):
    req = urllib.request.Request(f"{url}?{urllib.parse.urlencode(params)}",
                                 headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def refresh_token():
    old = os.environ["NETATMO_REFRESH_TOKEN"].strip()
    tok = post(f"{API}/oauth2/token", {
        "grant_type": "refresh_token",
        "refresh_token": old,
        "client_id": os.environ["NETATMO_CLIENT_ID"],
        "client_secret": os.environ["NETATMO_CLIENT_SECRET"],
    })
    access, new = tok["access_token"], tok.get("refresh_token", old)
    print(f"::add-mask::{access}")
    print(f"::add-mask::{new}")
    if new != old:
        if os.environ.get("GH_TOKEN"):
            subprocess.run(["gh", "secret", "set", "NETATMO_REFRESH_TOKEN"],
                           input=new.encode(), check=True)
            print("Refresh token zmieniony – sekret zaktualizowany")
        else:
            print("::warning::Netatmo zwróciło nowy refresh token, a brak GH_TOKEN – zaktualizuj sekret ręcznie")
    return access


def dist_km(lat, lon):
    r = 6371
    p1, p2 = math.radians(HOME[0]), math.radians(lat)
    dp, dl = p2 - p1, math.radians(lon - HOME[1])
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return round(2 * r * math.asin(math.sqrt(a)), 1)


def parse(st):
    lon, lat = st["place"]["location"]
    s = {
        "id": st["_id"],
        "city": st["place"].get("city"),
        "street": st["place"].get("street"),
        "lat": lat, "lon": lon,
        "alt": st["place"].get("altitude"),
        "km": dist_km(lat, lon),
        "t": None,
    }
    for m in st.get("measures", {}).values():
        if "res" in m:                       # temperatura / wilgotność / ciśnienie
            ts, vals = max(m["res"].items(), key=lambda kv: int(kv[0]))
            for typ, v in zip(m.get("type", []), vals):
                s[{"temperature": "temp", "humidity": "hum", "pressure": "pres"}.get(typ, typ)] = v
            s["t"] = max(s["t"] or 0, int(ts))
        if "rain_60min" in m:                # deszczomierz
            s.update(rain_1h=m.get("rain_60min"), rain_24h=m.get("rain_24h"), rain_live=m.get("rain_live"))
        if "wind_strength" in m:             # wiatromierz
            s.update(wind=m.get("wind_strength"), wind_dir=m.get("wind_angle"),
                     gust=m.get("gust_strength"), gust_dir=m.get("gust_angle"))
    return s


access = refresh_token()
body = get(f"{API}/api/getpublicdata", access, {**BOX, "filter": "true"}).get("body", [])
if not body:
    sys.exit("Brak stacji w odpowiedzi getpublicdata")

stations = sorted((parse(st) for st in body), key=lambda s: s["km"])
ROOT.mkdir(exist_ok=True)
(ROOT / "netatmo.json").write_text(json.dumps({
    "fetched": int(datetime.now().timestamp()),
    "home": HOME,
    "stations": stations,
}, ensure_ascii=False, indent=1), encoding="utf-8")

full = sum(1 for s in stations if "wind" in s and "rain_1h" in s)
print(f"Netatmo: {len(stations)} stacji, w tym {full} z wiatrem i opadem")
