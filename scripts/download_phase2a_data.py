"""Download current OSM ways/relations for Phase 2A's projected Kiba extent."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import load_config, area, ROOT, write_json
from pyproj import Transformer


def main():
    cfg = load_config()
    bounds, center = area(cfg)
    back = Transformer.from_crs(cfg['local_crs'], 'EPSG:4326', always_xy=True)
    west, south, east, north = bounds
    corners = [back.transform(x, y) for x, y in ((west, south), (west, north), (east, south), (east, north))]
    lat0 = cfg['center']['latitude']
    margin_lat = 12.0 / 111320.0
    margin_lon = 12.0 / (111320.0 * __import__('math').cos(__import__('math').radians(lat0)))
    bbox = (min(x for x, _ in corners)-margin_lon, min(y for _, y in corners)-margin_lat,
            max(x for x, _ in corners)+margin_lon, max(y for _, y in corners)+margin_lat)
    bbox_text = ','.join(f'{v:.8f}' for v in bbox)
    url = f'https://api.openstreetmap.org/api/0.6/map?bbox={bbox_text}'
    req = Request(url, headers={'User-Agent': 'KIBA-REAL-CITY/Phase2A (OpenStreetMap API map extract)'})
    with urlopen(req, timeout=60) as response:
        payload = response.read()
        server_date = response.headers.get('Date')
        if response.status != 200:
            raise SystemExit(f'OSM API failed with HTTP {response.status}; no v02 will be built.')
    raw = ROOT / 'data/raw/kiba_osm_phase2a.osm'
    raw.parent.mkdir(parents=True, exist_ok=True)
    raw.write_bytes(payload)
    osm_root=ET.fromstring(payload)
    license_declared=osm_root.attrib.get('license','')
    copyright_declared=osm_root.attrib.get('copyright','')
    attribution_url=osm_root.attrib.get('attribution','')
    if 'odbl/1-0' not in license_declared.lower() or not copyright_declared or not attribution_url:
        raise SystemExit('OSM API response did not provide license/copyright/attribution metadata; no v02 should be built.')
    manifest = {
        'dataset': 'OpenStreetMap current API map extract',
        'retrieved_at_utc': datetime.now(timezone.utc).isoformat(),
        'server_date': server_date,
        'snapshot_year': datetime.now(timezone.utc).year,
        'api_url': url,
        'request_bbox_wgs84_lon_lat': list(bbox),
        'clip_extent_epsg6677_local_m': [-cfg['extent_m']/2, -cfg['extent_m']/2, cfg['extent_m']/2, cfg['extent_m']/2],
        'source_crs': 'EPSG:4326',
        'target_crs': cfg['local_crs'],
        'local_origin_projected_m': list(center),
        'license_declared_by_osm_api_xml': license_declared,
        'license_name': 'Open Data Commons Open Database License (ODbL) 1.0',
        'license_url': license_declared.replace('http://','https://'),
        'copyright_declared_by_osm_api_xml': copyright_declared,
        'attribution_declared_by_osm_api_xml': attribution_url,
        'attribution_display': copyright_declared,
        'attribution_url': attribution_url.replace('http://','https://'),
        'raw_file': str(raw.relative_to(ROOT)),
        'raw_bytes': len(payload),
        'park_feature_id': 'relation/14273608',
        'park_name': '木場公園 (Kiba Park)',
        'park_reference_website': 'https://www.tokyo-park.or.jp/park/kiba/',
        'notes': 'OSM is a live database, not an annual release; snapshot_year is retrieval year. The exact 500 m projected square is clipped after transforming geometry.'
    }
    write_json('data/processed/phase2a_source.json', manifest)
    print(f'Downloaded {len(payload)} bytes to {raw.relative_to(ROOT)} (server date {server_date})')


if __name__ == '__main__':
    main()
