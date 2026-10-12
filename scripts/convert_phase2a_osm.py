"""Project/clip real OSM roads and Kiba Park boundary into the shared local frame."""
from __future__ import annotations
import json, math, re, sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET
from pyproj import Transformer
from shapely.geometry import LineString, Polygon, box
from shapely.ops import unary_union, triangulate
from shapely.validation import make_valid
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, load_config, area, write_json

PARK_RELATION_ID = '14273608'
ROAD_WIDTH_M = {
    'motorway': 12.0, 'trunk': 10.0, 'primary': 8.0, 'secondary': 7.0,
    'tertiary': 6.0, 'unclassified': 4.5, 'residential': 4.0,
    'living_street': 4.0, 'service': 3.0, 'pedestrian': 3.0,
    'cycleway': 2.5, 'footway': 2.0, 'path': 2.0, 'steps': 1.5,
    'track': 3.0, 'bridleway': 2.0,
}


def tags(element):
    return {t.attrib['k']: t.attrib['v'] for t in element.findall('tag')}


def encode_polygons(geom):
    if geom.is_empty:
        return []
    if geom.geom_type == 'Polygon':
        polys = [geom]
    elif geom.geom_type == 'MultiPolygon':
        polys = list(geom.geoms)
    elif geom.geom_type == 'GeometryCollection':
        polys = [g for g in geom.geoms if g.geom_type == 'Polygon']
    else:
        return []
    return [
        {
            'exterior': [[round(float(x), 4), round(float(y), 4)] for x, y in p.exterior.coords],
            'interiors': [[[round(float(x), 4), round(float(y), 4)] for x, y in r.coords] for r in p.interiors],
        }
        for p in polys if p.area > 1e-5
    ]


def mesh_data(polygons):
    """Pre-triangulate clipped surfaces so Blender's bundled Python needs no GIS packages."""
    vertices, faces, index = [], [], {}
    def vertex(x, y):
        key=(round(float(x),4),round(float(y),4))
        if key not in index:
            index[key]=len(vertices); vertices.append([key[0],key[1]])
        return index[key]
    for item in polygons:
        poly=Polygon(item['exterior'],item.get('interiors',[]))
        for tri in triangulate(poly):
            if not poly.covers(tri) or tri.area<1e-8: continue
            points=list(tri.exterior.coords)[:3]
            signed=sum(points[i][0]*points[(i+1)%3][1]-points[(i+1)%3][0]*points[i][1] for i in range(3))
            if signed<0: points.reverse()
            face=[vertex(x,y) for x,y in points]
            if len(set(face))==3: faces.append(face)
    return {'mesh_vertices_xy_m':vertices,'mesh_faces':faces}


def parse_width(value):
    if not value:
        return None
    match = re.match(r'^\s*(\d+(?:\.\d+)?)\s*(ft|feet|m|metres?|meters?)?\s*$', value, re.I)
    if not match:
        return None
    width = float(match.group(1))
    if (match.group(2) or '').lower() in {'ft', 'feet'}:
        width *= 0.3048
    return width if 0.5 <= width <= 100 else None


def main():
    cfg = load_config()
    raw = ROOT / 'data/raw/kiba_osm_phase2a.osm'
    source_meta = ROOT / 'data/processed/phase2a_source.json'
    if not raw.is_file() or not source_meta.is_file():
        raise SystemExit('Missing OSM raw extract or source manifest; run scripts/download_phase2a_data.py first.')
    meta = json.loads(source_meta.read_text(encoding='utf-8'))
    root = ET.parse(raw).getroot()
    if root.attrib.get('version') != '0.6' or 'odbl/1-0' not in root.attrib.get('license', '').lower():
        raise SystemExit('OSM API XML does not declare the expected version/license; no v02 will be built.')
    nodes = {n.attrib['id']: n for n in root.findall('node')}
    ways = {w.attrib['id']: w for w in root.findall('way')}
    relations = {r.attrib['id']: r for r in root.findall('relation')}
    if PARK_RELATION_ID not in relations:
        raise SystemExit(f'Kiba Park relation/{PARK_RELATION_ID} missing from OSM extract; no substitute boundary will be generated.')
    to_project = Transformer.from_crs('EPSG:4326', cfg['local_crs'], always_xy=True)
    cx, cy = area(cfg)[1]
    xy_rounding_errors=[]
    half = cfg['extent_m'] / 2
    clip = box(-half, -half, half, half)
    processed = json.loads((ROOT / cfg['processed_file']).read_text(encoding='utf-8'))
    buildings = [Polygon(ring) for b in processed['buildings'] for ring in b['footprints']]
    building_union = unary_union(buildings)

    def node_xy(node_id):
        n = nodes.get(node_id)
        if n is None:
            raise ValueError(f'OSM node/{node_id} is missing from downloaded map extract')
        x, y = to_project.transform(float(n.attrib['lon']), float(n.attrib['lat']))
        lx,ly=x-cx,y-cy
        xy_rounding_errors.append(math.hypot(round(lx,4)-lx,round(ly,4)-ly))
        return (lx,ly)

    roads = []
    road_area = []
    for way in ways.values():
        prop = tags(way)
        hw = prop.get('highway')
        if not hw or hw in {'proposed', 'construction', 'raceway', 'platform'} or prop.get('access') == 'no':
            continue
        refs = [nd.attrib['ref'] for nd in way.findall('nd')]
        if len(refs) < 2 or any(ref not in nodes for ref in refs):
            continue
        line = LineString([node_xy(ref) for ref in refs])
        if line.is_empty or line.length <= 0:
            continue
        way_id = way.attrib['id']
        explicit_width = parse_width(prop.get('width'))
        is_mapped_area = refs[0] == refs[-1] and prop.get('area') == 'yes'
        if is_mapped_area:
            surface = make_valid(Polygon(list(line.coords))).intersection(clip)
            width = explicit_width
            width_source = 'OSM area geometry'
        else:
            width = explicit_width or ROAD_WIDTH_M.get(hw, 2.5)
            width_source = 'OSM width tag' if explicit_width else 'estimated by OSM highway class'
            surface = line.buffer(width / 2.0, cap_style='flat', join_style='mitre').intersection(clip)
        source_surface=make_valid(surface)
        polys = encode_polygons(source_surface)
        if not polys:
            continue
        rec = {
            'osm_id': f'way/{way_id}', 'name': prop.get('name'), 'highway': hw,
            'surface': prop.get('surface'), 'width_m': width,
            'width_source': width_source, 'geometry_type': 'mapped_area' if is_mapped_area else 'buffered_centerline',
            'tags': prop, 'polygons': polys, 'z_m': 0.02,
            'z_status': 'OSM provides no elevation; nominal shared ground level, visual offset +0.02 m',
            'source_surface_area_m2': round(source_surface.area,3),
        }
        display_polys=encode_polygons(source_surface.difference(building_union))
        rec['display_polygons']=display_polys
        rec['building_clearance']='visual surface clipped to Phase 1 footprints; OSM centerline/ID/tags are retained'
        rec['mesh_surface_area_m2']=round(sum(Polygon(p['exterior'],p.get('interiors',[])).area for p in display_polys),3)
        rec.update(mesh_data(display_polys))
        roads.append(rec)
        road_area.append(surface)

    relation = relations[PARK_RELATION_ID]
    park_tags = tags(relation)
    if park_tags.get('name') != '木場公園' or park_tags.get('leisure') != 'park' or park_tags.get('type') != 'multipolygon':
        raise SystemExit('The selected OSM relation is not tagged as the Kiba Park multipolygon; no v02 will be built.')
    outer, inner = [], []
    for member in relation.findall('member'):
        if member.attrib.get('type') != 'way' or member.attrib.get('ref') not in ways:
            raise SystemExit('Kiba Park relation has a missing/unsupported member; no partial park boundary will be used.')
        member_way = ways[member.attrib['ref']]
        coords = [node_xy(nd.attrib['ref']) for nd in member_way.findall('nd')]
        if len(coords) < 4 or coords[0] != coords[-1]:
            raise SystemExit(f'Park boundary way/{member.attrib["ref"]} is not a complete closed ring.')
        ring = Polygon(coords)
        (outer if member.attrib.get('role') == 'outer' else inner if member.attrib.get('role') == 'inner' else []).append(ring)
    if not outer:
        raise SystemExit('No outer rings in Kiba Park relation; no v02 will be built.')
    holes_by_outer = []
    for exterior in outer:
        holes = [list(h.exterior.coords) for h in inner if exterior.covers(h.representative_point())]
        holes_by_outer.append(Polygon(exterior.exterior.coords, holes))
    park = make_valid(unary_union(holes_by_outer)).intersection(clip)
    park_polys = encode_polygons(make_valid(park))
    if not park_polys:
        raise SystemExit('Kiba Park relation has no polygon inside the target extent; no v02 will be built.')

    roads_union = unary_union(road_area) if road_area else Polygon()
    road_building_overlap = roads_union.intersection(building_union).area
    park_building_overlap = park.intersection(building_union).area
    result = {
        'crs': cfg['local_crs'], 'origin_projected_m': list((cx, cy)),
        'bounds_local_m': [-half, -half, half, half],
        'coordinate_precision': {'stored_xy_decimals_m':4,'max_xy_rounding_error_m':max(xy_rounding_errors,default=0.0)},
        'source': meta,
        'roads': roads, 'park': {
            'osm_id': f'relation/{PARK_RELATION_ID}', 'name': '木場公園', 'tags': park_tags,
            'member_way_ids': [m.attrib['ref'] for m in relation.findall('member') if m.attrib.get('type') == 'way'],
            'polygons': park_polys, 'z_m': 0.01,
            'z_status': 'OSM provides boundary but no elevation; nominal shared ground level, visual offset +0.01 m',
        },
        'summary': {
            'osm_way_count_in_extract': len(ways), 'osm_relation_count_in_extract': len(relations),
            'highway_ways_in_extent': len(roads),
            'highway_class_counts': dict(sorted(Counter(r['highway'] for r in roads).items())),
            'road_mapped_area_count': sum(r['geometry_type'] == 'mapped_area' for r in roads),
            'road_width_estimated_count': sum(r['width_source'] == 'estimated by OSM highway class' for r in roads),
            'road_width_from_osm_count': sum(r['width_source'] == 'OSM width tag' for r in roads),
            'road_source_surface_area_m2': round(sum(r['source_surface_area_m2'] for r in roads),2),
            'road_display_surface_area_after_building_clearance_m2': round(sum(r['mesh_surface_area_m2'] for r in roads),2),
            'park_relation_id': PARK_RELATION_ID, 'park_outer_member_count': len(outer),
            'park_inner_member_count': len(inner), 'park_intersection_area_m2': round(park.area, 2),
            'park_display_surface_area_after_building_clearance_m2': round(park.difference(building_union).area,2),
            'road_surface_building_overlap_area_m2': round(road_building_overlap, 3),
            'park_building_overlap_area_m2': round(park_building_overlap, 3),
            'all_features_clipped_to_extent': all(-half-1e-5 <= x <= half+1e-5 and -half-1e-5 <= y <= half+1e-5
                for rec in roads for poly in rec['polygons'] for ring in [poly['exterior']] for x,y in ring)
                and all(-half-1e-5 <= x <= half+1e-5 and -half-1e-5 <= y <= half+1e-5
                for poly in park_polys for x,y in poly['exterior']),
            'building_count_used_for_overlap_check': len(processed['buildings']),
            'max_xy_rounding_error_m': max(xy_rounding_errors,default=0.0),
        },
    }
    park_display_polys=encode_polygons(park.difference(building_union))
    result['park']['display_polygons']=park_display_polys
    result['park']['source_area_m2']=round(park.area,2)
    result['park']['mesh_surface_area_m2']=round(sum(Polygon(p['exterior'],p.get('interiors',[])).area for p in park_display_polys),2)
    result['park']['building_clearance']='park boundary is preserved; display surface is cut around buildings without changing any building geometry'
    result['park'].update(mesh_data(park_display_polys))
    write_json('data/processed/phase2a_features.json', result)
    print(json.dumps(result['summary'], ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
