"""Download mapped OSM inputs for the exact expanded Phase 3D study area."""
from __future__ import annotations
import hashlib,json
from datetime import datetime,timezone
from pathlib import Path
from urllib.request import Request,urlopen
from xml.etree import ElementTree as ET
from phase3d_common import (ROOT,ORIGIN,MUSEUM_RELATION,PARK_RELATION,
                            TO_GEO,projected_bounds_to_wgs84,target_extent,extent_metadata)

RAW=ROOT/'data/raw'
PROCESSED=ROOT/'data/processed'
USER_AGENT='KIBA-REAL-CITY/Phase3D (public-data research)'

def fetch(url):
    req=Request(url,headers={'User-Agent':USER_AGENT})
    with urlopen(req,timeout=90) as response:
        return response.read(),response.headers

def sha(data): return hashlib.sha256(data).hexdigest()

def main():
    out_paths=[RAW/'kiba_phase3d_osm_map.osm',RAW/'kiba_phase3d_museum_relation.osm',
               RAW/'kiba_phase3d_park_relation.osm',PROCESSED/'phase3d_source.json']
    if any(p.exists() for p in out_paths):
        raise SystemExit('Phase 3D source outputs already exist; refusing to overwrite.')
    v04_geo=json.loads((ROOT/'output/geo_reference_v04.json').read_text(encoding='utf-8'))
    origin=tuple(v04_geo['center_projected_m'])
    if any(abs(a-b)>1e-6 for a,b in zip(origin,ORIGIN)):
        raise SystemExit('v04 georeference origin differs from the Phase 3D shared origin.')
    museum_url=f'https://api.openstreetmap.org/api/0.6/relation/{MUSEUM_RELATION}/full'
    park_url=f'https://api.openstreetmap.org/api/0.6/relation/{PARK_RELATION}/full'
    museum_bytes,museum_headers=fetch(museum_url)
    park_bytes,park_headers=fetch(park_url)
    # Construct a temp directory only after both OSM feature responses parse and
    # identify the requested real-world features.
    import tempfile
    with tempfile.TemporaryDirectory(prefix='kiba-phase3d-') as tmp:
        tmp=Path(tmp); museum_path=tmp/'museum.osm';park_path=tmp/'park.osm'
        museum_path.write_bytes(museum_bytes);park_path.write_bytes(park_bytes)
        extent=target_extent(museum_path,park_path)
        meta=extent_metadata(extent['bounds_local_m'])
        bbox=projected_bounds_to_wgs84(meta['bounds_projected_epsg6677_m'],pad_m=75.0)
        bbox_text=','.join(f'{x:.10f}' for x in bbox)
        map_url=f'https://api.openstreetmap.org/api/0.6/map?bbox={bbox_text}'
        map_bytes,map_headers=fetch(map_url)
        osm=ET.fromstring(map_bytes)
        if osm.attrib.get('version')!='0.6' or 'odbl/1-0' not in osm.attrib.get('license','').lower():
            raise SystemExit('OSM extract did not declare ODbL 1.0; refusing to use it.')
        museum_root=ET.fromstring(museum_bytes);park_root=ET.fromstring(park_bytes)
        mtags={x.attrib['k']:x.attrib['v'] for x in museum_root.find('relation').findall('tag')}
        ptags={x.attrib['k']:x.attrib['v'] for x in park_root.find('relation').findall('tag')}
        mb=extent['museum_bounds_local_m']
        museum_wgs=[TO_GEO.transform(ORIGIN[0]+x,ORIGIN[1]+y)
                    for x in (mb[0],mb[2]) for y in (mb[1],mb[3])]
        museum_wgs_bbox=[min(x for x,y in museum_wgs),min(y for x,y in museum_wgs),
                         max(x for x,y in museum_wgs),max(y for x,y in museum_wgs)]
        map_ids={(e.tag,e.attrib.get('id')) for e in osm}
        museum_in_map=('relation',MUSEUM_RELATION) in map_ids
        park_in_map=('relation',PARK_RELATION) in map_ids
        created=datetime.now(timezone.utc).isoformat()
        manifest={
          'phase':'3D','created_at_utc':created,'crs':'EPSG:6677',
          'origin_projected_m':list(ORIGIN),'axes':'X east, Y north, Z up',
          'extent':meta,'extent_method':'smallest axis-aligned EPSG:6677 rectangle containing the original v04 square, full OSM Kiba Park multipolygon, and full OSM museum multipolygon',
          'museum':{'osm_id':f'relation/{MUSEUM_RELATION}','tags':mtags,
             'relation_full_url':museum_url,'response_sha256':sha(museum_bytes),
             'bounds_wgs84_lonlat':museum_wgs_bbox,
             'bounds_local_m':list(extent['museum_bounds_local_m']),
             'separate_museum_parcel_boundary':'not separately mapped; whole Kiba Park boundary used as site-context geometry'},
          'park':{'osm_id':f'relation/{PARK_RELATION}','tags':ptags,'relation_full_url':park_url,
             'response_sha256':sha(park_bytes),'bounds_local_m':list(extent['park_bounds_local_m'])},
          'osm_extract':{'url':map_url,'request_bbox_wgs84_lonlat':list(bbox),
             'padding_m':75.0,'retrieved_at_utc':created,
             'server_date':map_headers.get('Date'),
             'license_declared_by_osm_api_xml':osm.attrib.get('license'),
             'attribution':osm.attrib.get('attribution'),'copyright':osm.attrib.get('copyright'),
             'bytes':len(map_bytes),'sha256':sha(map_bytes),
             'node_count':sum(e.tag=='node' for e in osm),
             'way_count':sum(e.tag=='way' for e in osm),
             'relation_count':sum(e.tag=='relation' for e in osm),
             'museum_relation_in_map_extract':museum_in_map,'park_relation_in_map_extract':park_in_map},
          'files':{'map':'data/raw/kiba_phase3d_osm_map.osm',
             'museum_relation':'data/raw/kiba_phase3d_museum_relation.osm',
             'park_relation':'data/raw/kiba_phase3d_park_relation.osm'}
        }
    RAW.mkdir(parents=True,exist_ok=True);PROCESSED.mkdir(parents=True,exist_ok=True)
    RAW.joinpath('kiba_phase3d_osm_map.osm').write_bytes(map_bytes)
    RAW.joinpath('kiba_phase3d_museum_relation.osm').write_bytes(museum_bytes)
    RAW.joinpath('kiba_phase3d_park_relation.osm').write_bytes(park_bytes)
    (PROCESSED/'phase3d_source.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'extent':meta,'osm':manifest['osm_extract'],'files':manifest['files']},ensure_ascii=False,indent=2))
if __name__=='__main__': main()
