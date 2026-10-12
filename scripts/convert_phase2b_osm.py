"""Convert tagged OSM vegetation, green areas, water and bridge footprints for Phase 2B."""
from __future__ import annotations
import hashlib
import json
import math
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

from pyproj import Transformer
from shapely import constrained_delaunay_triangles
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union
from shapely.validation import make_valid

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, area, load_config, write_json

RAW = ROOT / 'data/raw/kiba_osm_phase2a.osm'
SOURCE = ROOT / 'data/processed/phase2a_source.json'
PHASE2A = ROOT / 'data/processed/phase2a_features.json'
BUILDINGS = ROOT / 'data/processed/buildings.json'
OUT = ROOT / 'data/processed/phase2b_features.json'
PATH_CLASSES = {'footway', 'path', 'pedestrian', 'steps', 'cycleway'}
GREEN_KEYS = {'landuse': {'grass', 'meadow', 'forest', 'recreation_ground'},
              'leisure': {'garden'}, 'natural': {'grassland', 'wood', 'scrub', 'heath'}}
WATER_KEYS = {'natural': {'water', 'wetland'},
              'waterway': {'river', 'stream', 'canal', 'ditch'}}
WATER_WIDTH_M = {'river': 8.0, 'canal': 6.0, 'stream': 2.0, 'ditch': 1.5}


def get_tags(element):
    return {t.attrib['k']: t.attrib['v'] for t in element.findall('tag')}


def encode_polygons(geom):
    geom = make_valid(geom)
    if geom.is_empty:
        return []
    if geom.geom_type == 'Polygon':
        geoms = [geom]
    elif geom.geom_type == 'MultiPolygon':
        geoms = list(geom.geoms)
    elif geom.geom_type == 'GeometryCollection':
        geoms = [g for g in geom.geoms if g.geom_type == 'Polygon' and not g.is_empty]
    else:
        return []
    result = []
    for p in geoms:
        if p.area <= 1e-5:
            continue
        result.append({'exterior': [[round(x, 4), round(y, 4)] for x, y in p.exterior.coords],
                       'interiors': [[[round(x, 4), round(y, 4)] for x, y in ring.coords]
                                     for ring in p.interiors]})
    return result


def mesh_data(polygons):
    vertices, faces, indices = [], [], {}
    for record in polygons:
        geom = Polygon(record['exterior'], record['interiors'])
        # Constrained triangulation partitions concave polygons and holes
        # without bridging across park paths or cleared road corridors.
        for tri in constrained_delaunay_triangles(geom).geoms:
            if not geom.covers(tri) or tri.area <= 1e-6:
                continue
            face = []
            for x, y in list(tri.exterior.coords)[:3]:
                key = (round(x, 4), round(y, 4))
                if key not in indices:
                    indices[key] = len(vertices)
                    vertices.append(key)
                face.append(indices[key])
            if len(set(face)) == 3:
                a, b, c = [vertices[i] for i in face]
                if (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]) < 0:
                    face.reverse()
                faces.append(face)
    mesh_area = 0.0
    for face in faces:
        a, b, c = [vertices[i] for i in face]
        mesh_area += abs((b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]))/2
    expected_area = sum(Polygon(p['exterior'], p['interiors']).area for p in polygons)
    error = abs(mesh_area-expected_area)
    if error > max(0.02, expected_area*1e-5):
        raise ValueError(f'Triangulation area mismatch: polygons={expected_area:.3f} m2, mesh={mesh_area:.3f} m2')
    return {'mesh_vertices_xy_m': vertices, 'mesh_faces': faces,
            'triangulated_area_m2': round(mesh_area, 4), 'triangulation_area_error_m2': round(error, 5)}


def is_tagged(tags, rules):
    return any(tags.get(k) in values for k, values in rules.items())


def main():
    for path in (RAW, SOURCE, PHASE2A, BUILDINGS):
        if not path.is_file():
            raise SystemExit(f'Required real-data input missing: {path.relative_to(ROOT)}')
    raw_bytes = RAW.read_bytes()
    root = ET.fromstring(raw_bytes)
    if root.attrib.get('version') != '0.6' or 'odbl/1-0' not in root.attrib.get('license', '').lower():
        raise SystemExit('OSM XML does not declare ODbL 1.0; refusing to create Phase 2B features.')
    source = json.loads(SOURCE.read_text(encoding='utf-8'))
    phase2a = json.loads(PHASE2A.read_text(encoding='utf-8'))
    building_data = json.loads(BUILDINGS.read_text(encoding='utf-8'))
    cfg = load_config()
    _, (cx, cy) = area(cfg)
    half = cfg['extent_m'] / 2
    extent = box(-half, -half, half, half)
    transformer = Transformer.from_crs('EPSG:4326', cfg['local_crs'], always_xy=True)
    nodes = {n.attrib['id']: n for n in root.findall('node')}
    ways = {w.attrib['id']: w for w in root.findall('way')}

    def project_lonlat(lon, lat):
        x, y = transformer.transform(float(lon), float(lat))
        return (x-cx, y-cy)

    def node_xy(node_id):
        n = nodes.get(str(node_id))
        if n is None:
            raise ValueError(f'Missing OSM node/{node_id} referenced by an in-area feature')
        return project_lonlat(n.attrib['lon'], n.attrib['lat'])

    def way_geometry(way):
        refs = [nd.attrib['ref'] for nd in way.findall('nd')]
        if len(refs) < 2 or any(ref not in nodes for ref in refs):
            return None
        coords = [node_xy(ref) for ref in refs]
        if refs[0] == refs[-1] and len(refs) >= 4:
            return make_valid(Polygon(coords))
        return LineString(coords)

    park_records = phase2a['park']['polygons']
    park = unary_union([Polygon(p['exterior'], p.get('interiors', [])) for p in park_records])
    road_geoms = [Polygon(p['exterior'], p.get('interiors', []))
                  for r in phase2a['roads'] for p in r['polygons']]
    road_union = unary_union(road_geoms) if road_geoms else Polygon()
    building_geoms = [Polygon(ring) for b in building_data['buildings'] for ring in b['footprints']]
    building_union = unary_union(building_geoms)

    # Existing Phase 2A path/sidewalk objects are reclassified into a dedicated
    # collection at build time; their IDs and polygon meshes remain byte-for-byte intact.
    park_path_ids = []
    for r in phase2a['roads']:
        if r.get('highway') in PATH_CLASSES:
            geom = unary_union([Polygon(p['exterior'], p.get('interiors', [])) for p in r['polygons']])
            if geom.intersection(park).area > 0.01:
                park_path_ids.append(r['osm_id'])

    trees = []
    for node in root.findall('node'):
        tags = get_tags(node)
        if tags.get('natural') != 'tree':
            continue
        xy = project_lonlat(node.attrib['lon'], node.attrib['lat'])
        point = Point(xy)
        if not extent.covers(point):
            continue
        observed_height = _positive(tags.get('height'))
        observed_crown = _positive(tags.get('diameter_crown'))
        trees.append({
            'osm_id': f"node/{node.attrib['id']}", 'x_m': round(xy[0], 4), 'y_m': round(xy[1], 4),
            'tags': tags, 'species': tags.get('species') or tags.get('taxon'),
            'height_observed_m': observed_height, 'crown_diameter_observed_m': observed_crown,
            'height_display_m': observed_height or 6.0,
            'height_display_source': 'OSM height tag' if observed_height else 'estimated generic visualization value',
            'crown_diameter_display_m': observed_crown or 4.0,
            'crown_diameter_display_source': 'OSM diameter_crown tag' if observed_crown else 'estimated generic visualization value',
            'position_source': 'OpenStreetMap node tagged natural=tree',
        })

    green, water, bridges = [], [], []
    area_kind_counts = Counter()
    excluded = Counter()
    for way in ways.values():
        tags = get_tags(way)
        geom = way_geometry(way)
        if geom is None:
            continue
        way_id = f"way/{way.attrib['id']}"
        clipped = geom.intersection(extent)
        if clipped.is_empty:
            continue

        if isinstance(geom, Polygon) and is_tagged(tags, GREEN_KEYS):
            in_park = make_valid(clipped.intersection(park))
            if in_park.area > 0.5:
                display = make_valid(in_park.difference(road_union).difference(building_union))
                polys = encode_polygons(display)
                if polys:
                    kind = next((tags[k] for k in ('landuse', 'leisure', 'natural') if tags.get(k)), 'green')
                    area_kind_counts[kind] += 1
                    green.append({'osm_id': way_id, 'tags': tags, 'area_class': kind,
                                  'source_area_m2': round(in_park.area, 3),
                                  'display_area_m2': round(display.area, 3), 'polygons': polys,
                                  'geometry_source': 'OSM mapped polygon clipped to park boundary and cleared of existing roads/buildings',
                                  **mesh_data(polys)})
            else:
                excluded['green_no_park_intersection'] += 1

        if (isinstance(geom, Polygon) and is_tagged(tags, WATER_KEYS)) or tags.get('waterway') in WATER_KEYS['waterway']:
            if isinstance(geom, Polygon):
                water_geom = clipped
                width_m = _positive(tags.get('width'))
                width_source = 'OSM mapped water polygon'
            elif geom.geom_type in ('LineString', 'MultiLineString'):
                waterway = tags.get('waterway')
                width_m = _positive(tags.get('width')) or WATER_WIDTH_M.get(waterway, 3.0)
                width_source = 'OSM width tag' if _positive(tags.get('width')) else 'estimated generic width by waterway class'
                water_geom = clipped.buffer(width_m / 2, cap_style='flat', join_style='mitre').intersection(extent)
            else:
                water_geom = Polygon()
                width_m = None
                width_source = 'unusable geometry'
            water_display = make_valid(water_geom.difference(road_union).difference(building_union))
            polys = encode_polygons(water_display)
            if polys:
                water.append({'osm_id': way_id, 'tags': tags, 'width_m': width_m,
                              'width_source': width_source, 'source_area_m2': round(water_geom.area, 3),
                              'display_area_m2': round(water_display.area, 3), 'polygons': polys,
                              'geometry_source': 'OSM mapped water geometry; line corridors buffered only where width is not mapped',
                              **mesh_data(polys)})

        if isinstance(geom, Polygon) and tags.get('man_made') == 'bridge' and clipped.area > 0.5:
            polys = encode_polygons(clipped)
            layer = _positive(tags.get('layer'))
            display_z = 3.0 * layer if layer is not None and layer > 0 else 0.0
            bridges.append({'osm_id': way_id, 'tags': tags, 'name': tags.get('name'),
                            'source_area_m2': round(clipped.area, 3), 'polygons': polys,
                            'display_z_m': display_z,
                            'display_z_source': 'estimated 3 m per OSM layer above ground' if layer else 'not vertically resolved in source; placed at shared local ground level',
                            'geometry_source': 'OSM mapped bridge footprint', **mesh_data(polys)})

    for collection in (green, water, bridges):
        for feature in collection:
            if not feature.get('mesh_faces'):
                raise SystemExit(f"Feature {feature['osm_id']} did not triangulate; refusing to silently drop it.")

    result = {
        'crs': cfg['local_crs'], 'origin_projected_m': [cx, cy],
        'local_axes': 'X east, Y north, Z up', 'bounds_local_m': [-half, -half, half, half],
        'source': source, 'source_sha256': hashlib.sha256(raw_bytes).hexdigest(),
        'trees': trees, 'green_areas': green, 'water_areas': water, 'bridge_footprints': bridges,
        'park_path_osm_ids_reclassified_from_phase2a': sorted(park_path_ids),
        'counts': {'tree_points': len(trees), 'trees_with_species': sum(bool(t['species']) for t in trees),
                   'trees_with_observed_height': sum(t['height_observed_m'] is not None for t in trees),
                   'trees_with_observed_crown_diameter': sum(t['crown_diameter_observed_m'] is not None for t in trees),
                   'green_areas': len(green), 'green_classes': dict(sorted(area_kind_counts.items())),
                   'water_areas': len(water), 'bridges': len(bridges),
                   'park_paths_reclassified': len(park_path_ids), 'phase2a_road_and_path_total': len(phase2a['roads'])},
        'estimation_policy': {'tree_height_default_m': 6.0, 'tree_crown_diameter_default_m': 4.0,
                              'bridge_layer_visual_height_m': 3.0, 'water_width_by_class_m': WATER_WIDTH_M,
                              'all_defaults_are_visual_estimates': True},
        'excluded_features': dict(sorted(excluded.items())),
        'license': {'name': 'Open Data Commons Open Database License (ODbL) 1.0',
                    'attribution': 'OpenStreetMap and contributors',
                    'attribution_url': 'https://www.openstreetmap.org/copyright',
                    'license_url': 'https://opendatacommons.org/licenses/odbl/1-0/'},
    }
    write_json('data/processed/phase2b_features.json', result)
    print(json.dumps(result['counts'], ensure_ascii=False, indent=2))
    print(f"OSM source SHA-256: {result['source_sha256']}")


def _positive(value):
    if not value:
        return None
    try:
        number = float(value.replace('m', '').strip())
        return number if math.isfinite(number) and number > 0 else None
    except (ValueError, AttributeError):
        return None


if __name__ == '__main__':
    main()
