#!/usr/bin/env python3
"""Podkład mapy „Stacje w okolicy”: rzeki, główne drogi i miejscowości z OpenStreetMap (Overpass API).

Zapis: data/near_map.json (uproszczone linie, współrzędne zaokrąglone do 4 miejsc).
Uruchamiany ręcznie workflow „Odśwież podkład mapy” – podkład zmienia się rzadko.
"""
import json
import math
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "data" / "near_map.json"
BBOX = (52.40, 18.80, 52.84, 19.28)          # S, W, N, E – z zapasem wokół stacji
MIRRORS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]
bb = ",".join(map(str, BBOX))
QUERY = f"""[out:json][timeout:120];
(
  way["waterway"="river"]({bb});
  way["waterway"~"^(stream|canal)$"]["name"]({bb});
  way["highway"~"^(motorway|trunk|primary|secondary)$"]({bb});
  node["place"~"^(town|village)$"]({bb});
);
out geom;"""


def overpass():
    for i in range(3):
        for url in MIRRORS:
            try:
                req = urllib.request.Request(url, data=urllib.parse.urlencode({"data": QUERY}).encode(),
                                             headers={"User-Agent": "trekPio-Meteo/1.0 (github.com/trekPio/Meteo)"})
                with urllib.request.urlopen(req, timeout=150) as r:
                    return json.load(r)
            except Exception as e:                                   # noqa: BLE001
                print(f"{url}: {e}")
        time.sleep(20 * (i + 1))
    sys.exit("Overpass niedostępny")


def simplify(pts, tol):
    """Douglas-Peucker na współrzędnych (lon, lat)."""
    if len(pts) < 3:
        return pts
    (x1, y1), (x2, y2) = pts[0], pts[-1]
    dx, dy = x2 - x1, y2 - y1
    norm = math.hypot(dx, dy) or 1e-12
    dmax, idx = 0, 0
    for i in range(1, len(pts) - 1):
        x, y = pts[i]
        d = abs(dy * x - dx * y + x2 * y1 - y2 * x1) / norm
        if d > dmax:
            dmax, idx = d, i
    if dmax <= tol:
        return [pts[0], pts[-1]]
    return simplify(pts[:idx + 1], tol)[:-1] + simplify(pts[idx:], tol)


def line(el, tol=0.00025):
    k = math.cos(math.radians(52.6))
    pts = [(p["lon"] * k, p["lat"]) for p in el.get("geometry", [])]   # tolerancja w jednakowych metrach
    pts = simplify(pts, tol)
    return [[round(x / k, 4), round(y, 4)] for x, y in pts]


data = overpass()
rivers, roads, places = [], [], []
RANK = {"motorway": 0, "trunk": 1, "primary": 2, "secondary": 3}
for el in data.get("elements", []):
    t = el.get("tags", {})
    if el["type"] == "node":
        if t.get("name"):
            places.append({"n": t["name"], "t": t["place"], "lat": round(el["lat"], 4), "lon": round(el["lon"], 4)})
        continue
    c = line(el)
    if len(c) < 2:
        continue
    if "waterway" in t:
        rivers.append({"n": t.get("name", ""), "t": t["waterway"], "c": c})
    elif t.get("highway") in RANK:
        roads.append({"t": t["highway"], "ref": t.get("ref", ""), "c": c})

roads.sort(key=lambda r: -RANK[r["t"]])                   # ważniejsze drogi rysowane na wierzchu
OUT.parent.mkdir(exist_ok=True)
OUT.write_text(json.dumps({"bbox": BBOX, "src": "© OpenStreetMap contributors (ODbL)",
                           "rivers": rivers, "roads": roads, "places": places},
                          ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
names = sorted({r["n"] for r in rivers if r["n"]})
print(f"Podkład: {len(rivers)} odcinków rzek ({', '.join(names)}), {len(roads)} dróg, {len(places)} miejscowości, "
      f"{OUT.stat().st_size // 1024} KB")
