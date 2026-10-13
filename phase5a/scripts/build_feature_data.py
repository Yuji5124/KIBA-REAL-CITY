#!/usr/bin/env python3
"""Build local Phase 5A editable OSM layers from the retained OSM XML extract.

Derived OSM data is intentionally local-only. The script never downloads data,
modifies v07, or overwrites an existing edit file.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pyproj import Transformer
from shapely import transform as transform_geometry
from shapely.geometry import LineString, Polygon, box, mapping
from shapely.ops import polygonize, unary_union
from shapely.validation import make_valid

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OSM = ROOT / "data/raw/kiba_phase3d_osm_map.osm"
DEFAULT_GEO = ROOT / "output/geo_reference_v07.json"
OUT = ROOT / "phase5a"
VEGETATION_TAGS = {
    ("natural", "wood"), ("natural", "scrub"), ("natural", "heath"),
    ("natural", "grassland"), ("landuse", "forest"), ("landuse", "grass"),
    ("landuse", "flowerbed"), ("landuse", "meadow"), ("landuse", "orchard"),
    ("landuse", "vineyard"), ("landuse", "plant_nursery"), ("leisure", "garden"),
}
TREE_ROW_TAG = ("natural", "tree_row")
ROAD_WIDTH_ESTIMATES = {
    "motorway": 12.0, "motorway_link": 7.0, "trunk": 10.0, "trunk_link": 7.0,
    "primary": 8.0, "primary_link": 6.0, "secondary": 7.0, "secondary_link": 6.0,
    "tertiary": 6.0, "tertiary_link": 5.0, "residential": 5.5, "unclassified": 5.0,
    "living_street": 4.0, "service": 3.5, "track": 2.5, "cycleway": 2.0,
    "footway": 2.0, "path": 1.8, "pedestrian": 4.0, "steps": 1.8,
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def tags_of(element: ET.Element) -> dict[str, str]:
    return {item.attrib["k"]: item.attrib["v"] for item in element.findall("tag")}


def is_vegetation(tags: dict[str, str]) -> bool:
    return any((key, value) in VEGETATION_TAGS for key, value in tags.items())


def number_tag(tags: dict[str, str], key: str) -> float | None:
    value = tags.get(key)
    if value is None:
        return None
    try:
        result = float(value.lower().replace("m", "").strip())
        return result if math.isfinite(result) and result > 0 else None
    except ValueError:
        return None


def json_geometry(geom: Any) -> dict[str, Any]:
    if geom.geom_type == "Polygon":
        return mapping(geom)
    if geom.geom_type == "MultiPolygon":
        return mapping(geom)
    return mapping(geom)


def rings_for(geom: Any) -> list[list[list[float]]]:
    if geom.is_empty:
        return []
    polygons = [geom] if geom.geom_type == "Polygon" else list(geom.geoms) if geom.geom_type == "MultiPolygon" else []
    result: list[list[list[float]]] = []
    for polygon in polygons:
        result.append([[round(float(x), 4), round(float(y), 4)] for x, y in polygon.exterior.coords])
        for ring in polygon.interiors:
            result.append([[round(float(x), 4), round(float(y), 4)] for x, y in ring.coords])
    return result


def polygon_sets_for(geom: Any) -> list[dict[str, list[list[float]]]]:
    if geom.is_empty:
        return []
    polygons = [geom] if geom.geom_type == "Polygon" else list(geom.geoms) if geom.geom_type == "MultiPolygon" else []
    return [{
        "outer": [[round(float(x), 4), round(float(y), 4)] for x, y in poly.exterior.coords],
        "holes": [[[round(float(x), 4), round(float(y), 4)] for x, y in ring.coords] for ring in poly.interiors],
    } for poly in polygons]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--osm", type=Path, default=DEFAULT_OSM)
    parser.add_argument("--georef", type=Path, default=DEFAULT_GEO)
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()
    if not args.osm.is_file() or not args.georef.is_file():
        parser.error(f"missing source input: {args.osm if not args.osm.is_file() else args.georef}")

    geo = json.loads(args.georef.read_text(encoding="utf-8"))
    if geo.get("local_crs") != "EPSG:6677" or geo.get("phase3d", {}).get("crs") != "EPSG:6677":
        raise SystemExit("v07 georeference must declare EPSG:6677")
    origin_x, origin_y = map(float, geo["center_projected_m"])
    min_e, min_n, max_e, max_n = map(float, geo["phase3d"]["bounds_local_m"])
    bounds = box(min_e, min_n, max_e, max_n)
    transformer = Transformer.from_crs("EPSG:4326", "EPSG:6677", always_xy=True)
    nodes: dict[str, dict[str, Any]] = {}
    ways: dict[str, dict[str, Any]] = {}
    relations: list[dict[str, Any]] = []
    for event, element in ET.iterparse(args.osm, events=("end",)):
        if element.tag == "node":
            node_id = element.attrib["id"]
            lon, lat = float(element.attrib["lon"]), float(element.attrib["lat"])
            px, py = transformer.transform(lon, lat)
            nodes[node_id] = {"lon": lon, "lat": lat, "x": px-origin_x, "north": py-origin_y, "tags": tags_of(element)}
        elif element.tag == "way":
            way_id = element.attrib["id"]
            ways[way_id] = {"id": way_id, "node_ids": [nd.attrib["ref"] for nd in element.findall("nd")], "tags": tags_of(element)}
        elif element.tag == "relation":
            relations.append({"id": element.attrib["id"], "tags": tags_of(element), "members": [
                {"type": m.attrib["type"], "ref": m.attrib["ref"], "role": m.attrib.get("role", "")} for m in element.findall("member")
            ]})

    def node_coord(node_id: str) -> tuple[float, float] | None:
        node = nodes.get(node_id)
        return (float(node["x"]), float(node["north"])) if node else None

    def way_coords(way: dict[str, Any]) -> list[tuple[float, float]]:
        return [coord for ref in way["node_ids"] if (coord := node_coord(ref)) is not None]

    roads: list[dict[str, Any]] = []
    road_geo: list[dict[str, Any]] = []
    vegetation: list[dict[str, Any]] = []
    vegetation_geo: list[dict[str, Any]] = []
    trees: list[dict[str, Any]] = []
    features_by_id: dict[str, dict[str, Any]] = {}
    counted_relation_members: set[str] = set()

    for node_id, node in nodes.items():
        tags = node["tags"]
        if tags.get("natural") != "tree" or not (min_e <= node["x"] <= max_e and min_n <= node["north"] <= max_n):
            continue
        feature_id = f"node/{node_id}"
        feature = {
            "featureId": feature_id, "treeId": f"osm:{feature_id}", "sourceOsmId": feature_id,
            "latitude": node["lat"], "longitude": node["lon"],
            "projectedX": round(origin_x + node["x"], 4), "projectedY": round(origin_y + node["north"], 4),
            "localX": round(node["x"], 4), "localNorth": round(node["north"], 4),
            "height": number_tag(tags, "height"), "crownDiameter": number_tag(tags, "diameter_crown"),
            "trunkDiameter": number_tag(tags, "diameter"), "species": tags.get("species"), "genus": tags.get("genus"),
            "modelType": "generic-tree", "rotation": 0.0, "source": "OpenStreetMap", "confidence": "position-observed; dimensions may be missing",
            "edited": False, "tags": tags,
        }
        feature["sourceHash"] = hashlib.sha256(json.dumps(feature, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        trees.append(feature)
        features_by_id[feature_id] = {"kind": "tree", "sourceHash": feature["sourceHash"]}

    def way_feature(way: dict[str, Any], kind: str, geom: Any) -> dict[str, Any]:
        way_id, tags = way["id"], way["tags"]
        coords = way_coords(way)
        osm_id = f"way/{way_id}"
        raw_line = [[round(float(nodes[ref]["lon"]), 8), round(float(nodes[ref]["lat"]), 8)] for ref in way["node_ids"] if ref in nodes]
        projected = [[round(float(x), 4), round(float(y), 4)] for x, y in coords]
        if kind == "road":
            highway = tags.get("highway", tags.get("area:highway", "unknown"))
            tagged_width = number_tag(tags, "width")
            width = tagged_width or ROAD_WIDTH_ESTIMATES.get(highway, 3.0)
            width_source = "OSM width tag" if tagged_width else "estimated by highway class" if highway in ROAD_WIDTH_ESTIMATES else "estimated fallback; unknown class"
            feature = {"featureId": osm_id, "osmId": osm_id, "nodeIds": way["node_ids"], "tags": tags,
                       "highway": highway, "name": tags.get("name"), "surface": tags.get("surface"),
                       "widthM": width, "widthSource": width_source, "observedWidthM": tagged_width,
                       "geometryType": "area" if geom.geom_type in {"Polygon", "MultiPolygon"} else "line",
                       "coordinatesLocalEN": projected,
                       "polygonsLocalEN": polygon_sets_for(geom) if geom.geom_type in {"Polygon", "MultiPolygon"} else [],
                       "sourceCoordinatesLonLat": raw_line,
                       "source": "OpenStreetMap", "edited": False}
            source_for_hash = {"osmId": osm_id, "nodeIds": way["node_ids"], "tags": tags, "coordinates": raw_line}
            feature["sourceHash"] = hashlib.sha256(json.dumps(source_for_hash, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
            roads.append(feature)
            features_by_id[osm_id] = {"kind": "road", "sourceHash": feature["sourceHash"]}
            # Standard GeoJSON retains the original WGS84 way coordinates and ordered node references.
            source_geom = Polygon(raw_line) if is_area and len(raw_line) >= 4 else LineString(raw_line) if len(raw_line) >= 2 else geom
            if not source_geom.is_valid:
                source_geom = make_valid(source_geom)
            road_geo.append({"type": "Feature", "id": osm_id, "geometry": json_geometry(source_geom),
                             "properties": {"osm_id": osm_id, "node_ids": way["node_ids"], "tags": tags,
                                            "width_m": width, "width_source": width_source, "source": "OpenStreetMap"}})
        else:
            rings = rings_for(geom)
            feature = {"featureId": osm_id, "osmId": osm_id, "wayIds": [way_id], "nodeIds": way["node_ids"],
                       "tags": tags, "vegetationClass": next((v for k, v in tags.items() if (k, v) in VEGETATION_TAGS), "tree_row"),
                       "geometryType": "line" if geom.geom_type in {"LineString", "MultiLineString"} else "area",
                       "ringsLocalEN": rings if rings else projected, "polygonsLocalEN": polygon_sets_for(geom), "coordinatesLocalEN": projected,
                       "source": "OpenStreetMap", "edited": False}
            vegetation_hash = hashlib.sha256(json.dumps({"osmId": osm_id, "nodeIds": way["node_ids"], "tags": tags, "coordinates": raw_line}, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
            feature["sourceHash"] = vegetation_hash
            vegetation.append(feature)
            features_by_id[osm_id] = {"kind": "vegetation", "sourceHash": vegetation_hash}
            source_geom = Polygon(raw_line) if is_area and len(raw_line) >= 4 else LineString(raw_line) if len(raw_line) >= 2 else geom
            if not source_geom.is_valid:
                source_geom = make_valid(source_geom)
            vegetation_geo.append({"type": "Feature", "id": osm_id, "geometry": json_geometry(source_geom),
                                   "properties": {"osm_id": osm_id, "node_ids": way["node_ids"], "tags": tags,
                                                  "vegetation_class": feature["vegetationClass"], "source": "OpenStreetMap"}})
        return feature

    for way in ways.values():
        tags, coords = way["tags"], way_coords(way)
        if len(coords) < 2:
            continue
        feature_id = f"way/{way['id']}"
        is_closed = len(way["node_ids"]) >= 4 and way["node_ids"][0] == way["node_ids"][-1]
        is_area = is_closed and (tags.get("area") == "yes" or "area:highway" in tags or is_vegetation(tags))
        geom = Polygon(coords) if is_area else LineString(coords)
        if not geom.is_valid:
            geom = make_valid(geom)
        if geom.is_empty or not geom.intersects(bounds):
            continue
        if "highway" in tags or "area:highway" in tags:
            way_feature(way, "road", geom)
        elif tags.get(TREE_ROW_TAG[0]) == TREE_ROW_TAG[1]:
            way_feature(way, "vegetation", geom)
        elif is_vegetation(tags) and is_area:
            way_feature(way, "vegetation", geom)

    # Reassemble mapped vegetation and plaza multipolygons from their source member ways.
    for relation in relations:
        tags = relation["tags"]
        is_road_area = "highway" in tags or "area:highway" in tags
        if not is_road_area and not is_vegetation(tags):
            continue
        members = [m for m in relation["members"] if m["type"] == "way" and m["ref"] in ways and m["role"] in {"outer", "inner"}]
        outer_lines, inner_lines = [], []
        for member in members:
            way = ways[member["ref"]]
            coords = way_coords(way)
            if len(coords) >= 2:
                (outer_lines if member["role"] == "outer" else inner_lines).append(LineString(coords))
                counted_relation_members.add(member["ref"])
        if not outer_lines:
            continue
        outer_polys = list(polygonize(unary_union(outer_lines)))
        inner_polys = list(polygonize(unary_union(inner_lines))) if inner_lines else []
        geom = unary_union(outer_polys)
        if inner_polys:
            geom = geom.difference(unary_union(inner_polys))
        geom = make_valid(geom)
        if geom.is_empty or not geom.intersects(bounds):
            continue
        inverse = Transformer.from_crs("EPSG:6677", "EPSG:4326", always_xy=True)
        source_geom = transform_geometry(geom, inverse.transform, interleaved=False)
        rel_id = f"relation/{relation['id']}"
        member_ids = [m["ref"] for m in members]
        feature = {"featureId": rel_id, "osmId": rel_id, "memberWayIds": member_ids, "tags": tags,
                   "geometryType": "area", "ringsLocalEN": rings_for(geom), "polygonsLocalEN": polygon_sets_for(geom),
                   "vegetationClass": next((v for k, v in tags.items() if (k, v) in VEGETATION_TAGS), "public-space"),
                   "coordinatesLocalEN": [], "source": "OpenStreetMap", "edited": False}
        if is_road_area:
            feature["highway"] = tags.get("highway", tags.get("area:highway", "pedestrian"))
            width = number_tag(tags, "width")
            feature.update({"widthM": width or ROAD_WIDTH_ESTIMATES.get(feature["highway"], 4.0),
                            "observedWidthM": width, "widthSource": "OSM width tag" if width else "estimated area display width"})
            roads.append(feature)
            road_geo.append({"type": "Feature", "id": rel_id, "geometry": json_geometry(source_geom),
                             "properties": {"osm_id": rel_id, "member_way_ids": member_ids, "tags": tags,
                                            "width_m": feature["widthM"], "width_source": feature["widthSource"], "source": "OpenStreetMap"}})
        else:
            vegetation.append(feature)
            vegetation_geo.append({"type": "Feature", "id": rel_id, "geometry": json_geometry(source_geom),
                                   "properties": {"osm_id": rel_id, "member_way_ids": member_ids, "tags": tags,
                                                  "vegetation_class": feature["vegetationClass"], "source": "OpenStreetMap"}})
        feature["sourceHash"] = hashlib.sha256(json.dumps({"osmId": rel_id, "members": member_ids, "tags": tags, "rings": feature["ringsLocalEN"]}, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        features_by_id[rel_id] = {"kind": "road" if is_road_area else "vegetation", "sourceHash": feature["sourceHash"]}

    source_sha = sha256_file(args.osm)
    retrieved = "2026-10-12T22:51:51.059747+00:00" if args.osm.resolve() == (ROOT / "data/raw/kiba_phase3d_osm_map.osm").resolve() else None
    meta = {
        "phase": "KIBA REAL CITY Phase 5A local OSM layer build", "status": "OSM_READY_TERRAIN_BLOCKED",
        "source": {"provider": "OpenStreetMap", "rawPath": str(args.osm.relative_to(ROOT) if args.osm.is_relative_to(ROOT) else args.osm),
                   "sha256": source_sha, "retrievedAtUtc": retrieved, "apiUrl": "https://api.openstreetmap.org/api/0.6/map",
                   "license": "ODbL 1.0 (declared in retained OSM API metadata)",
                   "licenseUrl": "https://opendatacommons.org/licenses/odbl/1-0/",
                   "attribution": "© OpenStreetMap contributors", "attributionUrl": "https://www.openstreetmap.org/copyright",
                   "licenseReview": "The extract declares ODbL 1.0; the full current terms were not reachable in this restricted environment. Derived features are kept local and excluded from Git."},
        "crs": "EPSG:6677", "sourceCrs": "EPSG:4326", "centerProjectedM": [origin_x, origin_y],
        "boundsLocalM": [min_e, min_n, max_e, max_n], "threeAxes": "X=east, Y=up, Z=-north",
        "sourceElementCounts": {"nodes": len(nodes), "ways": len(ways), "relations": len(relations)},
        "counts": {"roads": len(roads), "individualTrees": len(trees), "vegetation": len(vegetation),
                   "treeRows": sum(x["vegetationClass"] == "tree_row" for x in vegetation),
                   "speciesKnown": sum(t["species"] is not None for t in trees),
                   "heightKnown": sum(t["height"] is not None for t in trees),
                   "crownDiameterKnown": sum(t["crownDiameter"] is not None for t in trees),
                   "roadWidthsObserved": sum(r.get("observedWidthM") is not None for r in roads),
                   "roadWidthsEstimated": sum(r.get("observedWidthM") is None for r in roads)},
        "treeClassification": {"A_individualOsmPositions": len(trees), "B_rowsOrPlantingAreas": sum(x["vegetationClass"] == "tree_row" for x in vegetation),
                               "C_manualOrFieldAdded": 0},
        "warnings": ["OSM map extract is a 2026-10-12 snapshot; a fresh request was not made because api.openstreetmap.org is absent from the effective network allowlist.",
                     "OSM tree positions do not establish that unmapped individual trees are absent.",
                     "Tree model dimensions use display-only defaults when source dimensions are null."],
    }
    viewer = {"schemaVersion": 1, "sourceSha256": source_sha, "crs": "EPSG:6677", "centerProjectedM": [origin_x, origin_y],
              "boundsLocalM": [min_e, min_n, max_e, max_n], "threeAxes": "X=east, Y=up, Z=-north", "source": meta["source"],
              "roads": roads, "trees": trees, "vegetation": vegetation,
              "terrain": {"status": "BLOCKED", "sourceCandidateDirectory": "data/raw/gsi_dem_tiles", "reason": "Official PNG layer specification, vertical datum, and usage terms remain unverified; no terrain mesh or editable elevation surface is produced."}}

    phase5 = args.output
    for folder in [phase5 / "processed", phase5 / "metadata", phase5 / "edits"]:
        folder.mkdir(parents=True, exist_ok=True)
    outputs = {
        "roads.geojson": {"type": "FeatureCollection", "name": "Kiba Park Phase 5A OSM roads", "source_crs": "EPSG:4326", "features": road_geo},
        "vegetation.geojson": {"type": "FeatureCollection", "name": "Kiba Park Phase 5A OSM vegetation", "source_crs": "EPSG:4326", "features": vegetation_geo},
        "trees.json": {"schemaVersion": 1, "source": meta["source"], "crs": "EPSG:6677", "centerProjectedM": [origin_x, origin_y], "features": trees},
        "viewer_features.json": viewer,
    }
    for filename, payload in outputs.items():
        target = phase5 / "processed" / filename
        target.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    (phase5 / "metadata" / "sources.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    georef_out = {"source": str(args.georef.relative_to(ROOT) if args.georef.is_relative_to(ROOT) else args.georef),
                  "crs": "EPSG:6677", "centerProjectedM": [origin_x, origin_y], "boundsLocalM": [min_e, min_n, max_e, max_n],
                  "threeAxes": "X=east, Y=up, Z=-north", "v07Sha256": {name: sha256_file(ROOT / name) for name in ["output/KIBA_REAL_CITY_v07.blend", "output/KIBA_REAL_CITY_v07.glb", "output/geo_reference_v07.json"]}}
    (phase5 / "metadata" / "georeference.json").write_text(json.dumps(georef_out, indent=2) + "\n", encoding="utf-8")
    edits_path = phase5 / "edits" / "edits.json"
    if not edits_path.exists():
        edits_path.write_text(json.dumps({"schemaVersion": 1, "baseSourceSha256": source_sha, "edits": {}, "additions": {}, "deleted": []}, indent=2) + "\n", encoding="utf-8")
    else:
        saved = json.loads(edits_path.read_text(encoding="utf-8"))
        conflicts = []
        for feature_id, patch in saved.get("edits", {}).items():
            current = features_by_id.get(feature_id)
            if current is None:
                conflicts.append({"featureId": feature_id, "reason": "feature ID missing from refreshed OSM data"})
            elif patch.get("baseFeatureHash") != current["sourceHash"]:
                conflicts.append({"featureId": feature_id, "reason": "source geometry/tags changed since edit was made"})
        if saved.get("baseSourceSha256") != source_sha or conflicts:
            (phase5 / "metadata" / "import_conflicts.json").write_text(json.dumps({"newSourceSha256": source_sha, "savedBaseSourceSha256": saved.get("baseSourceSha256"), "conflicts": conflicts, "status": "CONFLICTS" if conflicts else "SOURCE_UPDATED_NO_FEATURE_CONFLICTS"}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    report = {"generatedAtUtc": datetime.now(timezone.utc).isoformat(), "sourceSha256": source_sha, "counts": meta["counts"],
              "outputFiles": [str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p) for p in [phase5 / "processed" / x for x in outputs] + [phase5 / "metadata/sources.json", phase5 / "metadata/georeference.json"]],
              "editsPreserved": edits_path.exists(), "terrainStatus": viewer["terrain"]["status"], "status": meta["status"]}
    (phase5 / "metadata" / "generated_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
