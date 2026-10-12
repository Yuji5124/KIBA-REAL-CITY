"""Shared configuration and geometry helpers."""
from __future__ import annotations
import json
from pathlib import Path
from pyproj import Transformer

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "kiba_park.json"


def load_config():
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def area(config):
    c = config["center"]
    to_local = Transformer.from_crs("EPSG:4326", config["local_crs"], always_xy=True)
    cx, cy = to_local.transform(c["longitude"], c["latitude"])
    h = config["extent_m"] / 2
    return (cx - h, cy - h, cx + h, cy + h), (cx, cy)


def mesh_1km_codes(bounds):
    """Return official 8-digit Japanese third-level mesh codes intersecting bounds.

    Mesh grid definitions: first mesh 40' latitude x 1 degree longitude;
    second mesh 5' x 7'30"; third mesh 30" x 45".
    """
    from pyproj import Transformer
    west, south, east, north = bounds
    tr = Transformer.from_crs("EPSG:6677", "EPSG:4326", always_xy=True)
    back = Transformer.from_crs("EPSG:4326", "EPSG:6677", always_xy=True)
    # Densify all four edges so projected rectangular edges are represented in geographic space.
    coords = []
    for i in range(101):
        t = i / 100
        coords.extend([(west+(east-west)*t, south), (west+(east-west)*t, north),
                       (west, south+(north-south)*t), (east, south+(north-south)*t)])
    ll = [tr.transform(x, y) for x, y in coords]
    lons, lats = zip(*ll)
    minlon, maxlon, minlat, maxlat = min(lons), max(lons), min(lats), max(lats)
    # Expand one cell at edges to avoid floating-point exclusion; exact intersection follows.
    imin = int(minlat * 60 / 40) - 1
    imax = int(maxlat * 60 / 40) + 1
    jmin = int(minlon) - 1
    jmax = int(maxlon) + 1
    codes = set()
    for p in range(imin, imax + 1):
        for q in range(jmin, jmax + 1):
            lat0 = p * 40 / 60
            lon0 = q
            lat1 = lat0 + 40 / 60
            lon1 = lon0 + 1
            # second mesh divisions: 8 rows x 8 columns
            for r in range(8):
                a0 = lat0 + r * 5 / 60
                a1 = a0 + 5 / 60
                for s in range(8):
                    b0 = lon0 + s * 7.5 / 60
                    b1 = b0 + 7.5 / 60
                    # third mesh: 10 rows x 10 columns
                    for u in range(10):
                        c0 = a0 + u * 0.5 / 60
                        c1 = c0 + 0.5 / 60
                        for v in range(10):
                            d0 = b0 + v * 0.75 / 60
                            d1 = d0 + 0.75 / 60
                            # Approximate projected intersection with a densified mesh boundary.
                            xs, ys = [], []
                            for lon, lat in [(d0,c0),(d0,c1),(d1,c0),(d1,c1)]:
                                x,y = back.transform(lon,lat)
                                xs.append(x); ys.append(y)
                            if max(xs) < west or min(xs) > east or max(ys) < south or min(ys) > north:
                                continue
                            codes.add(f"{p:02d}{q-100:02d}{r}{s}{u}{v}")
    return sorted(codes)


def write_json(path, data):
    p = ROOT / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
