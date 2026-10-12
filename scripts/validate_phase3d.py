"""Run v04/v05 geometry comparison and write the Phase 3D JSON/Markdown report."""
from __future__ import annotations
import json,os,shutil,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
    blender=os.environ.get('BLENDER_EXE') or shutil.which('blender')
    if not blender:raise SystemExit('Blender not found; set BLENDER_EXE or add Blender to PATH.')
    v04=ROOT/'output/KIBA_REAL_CITY_v04.blend';v05=ROOT/'output/KIBA_REAL_CITY_v05.blend';glb=ROOT/'output/KIBA_REAL_CITY_v05.glb'
    features=ROOT/'data/processed/phase3d_features.json';catalog=ROOT/'data/processed/phase3d_plateau_catalog.json'
    report=ROOT/'reports/phase3d_report.json';markdown=ROOT/'reports/phase3d_report.md'
    for p in (v04,v05,glb,features,catalog):
        if not p.is_file():raise SystemExit(f'Missing required input: {p.relative_to(ROOT)}')
    preview_paths=[ROOT/'reports'/name for name in (
      'KIBA_REAL_CITY_v05_overview.png','KIBA_REAL_CITY_v05_museum.png',
      'KIBA_REAL_CITY_v05_kiba_bridge.png','KIBA_REAL_CITY_v05_top.png',
      'KIBA_REAL_CITY_v05_extent_comparison.png')]
    missing_previews=[p.name for p in preview_paths if not p.is_file() or p.stat().st_size==0]
    if missing_previews:raise SystemExit('Render all four views and the extent map first: '+', '.join(missing_previews))
    if report.exists() or markdown.exists():raise SystemExit('Phase 3D report exists; refusing to overwrite.')
    subprocess.run([blender,'--background','--python',str(ROOT/'scripts/blender_validate_phase3d.py'),'--',
       str(v04),str(v05),str(glb),str(features),str(report)],check=True,cwd=ROOT)
    data=json.loads(report.read_text(encoding='utf-8'))
    features_data=json.loads(features.read_text(encoding='utf-8'))
    source_data=json.loads((ROOT/'data/processed/phase3d_source.json').read_text(encoding='utf-8'))
    plateau=json.loads(catalog.read_text(encoding='utf-8'))
    data['sources']={
      'plateau_dataset':features_data['sources']['plateau'],
      'citygml_source_files':features_data['sources']['citygml_source_files'],
      'catalog_query_url':plateau['region_query_url'],
      'osm_extract':source_data['osm_extract'],
      'museum_relation':source_data['museum']['osm_id'],
      'park_relation':source_data['park']['osm_id']}
    data['new_building_details']=[{
      'citygml_id':b['citygml_id'],'source_file':b['source_file'],
      'base_z_m':b['base_z_m'],'height_m':b['height_m'],
      'measured_height_m':b['measured_height_m'],
      'bounds_local_m':b['geometry_bounds_local_m']} for b in features_data['buildings']['new']]
    counts=features_data['counts']
    data['added_osm_counts']={
      'road_extension_pieces':counts['road_extension_pieces'],
      'new_road_source_ids':counts['road_extension_source_ids']-counts['road_continuations'],
      'road_pieces_continuing_old_ids':counts['road_continuations'],
      'new_tree_positions':counts['new_tree_positions'],
      'green_extension_pieces':counts['green_extension_pieces'],
      'new_green_source_ids':counts['green_extension_pieces']-counts['green_continuations'],
      'water_extension_pieces':counts['water_extension_pieces'],
      'new_water_source_ids':counts['water_extension_pieces']-counts['water_continuations'],
      'bridge_extension_pieces':counts['new_bridges'],
      'new_bridge_source_ids':counts['new_bridges']-counts['bridge_continuations'],
      'park_boundary_extension_polygons':counts['park_extension_polygons']}
    data['preview_sizes_bytes']={p.name:p.stat().st_size for p in preview_paths}
    report.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    source=source_data
    lines=['# KIBA REAL CITY Phase 3D report','',
      'All geospatial positions use EPSG:6677 with the unchanged v04 local origin. New building/road/park additions use real PLATEAU CityGML and OpenStreetMap source geometry; display-only ground partitions do not replace source meshes.','',
      '## Extent','',
      f"- Local bounds: `{data['extent']['bounds_local_m']}` m; {data['extent']['width_m']:.3f} m E–W × {data['extent']['height_m']:.3f} m N–S.",
      f"- EPSG:6677 bounds: `{data['extent']['bounds_projected_epsg6677_m']}` m.",
      f"- WGS84 bounds: `{data['extent']['bounds_wgs84_lonlat']}`; 1 km meshes `{', '.join(data['extent']['mesh_codes_1km'])}`.",
      '- Extent is the smallest axis-aligned rectangle containing the full mapped Kiba Park boundary, the mapped museum footprint, and the original 500 m v04 square.',
      '', '## Sources and additions','',
      f"- PLATEAU: Koto City 2023, CityGML LOD1, source meshes `53394604` and `53394614`; extracted GML files `{', '.join(x['path'] for x in source['files'])}`.",
      f"- OSM extract retrieved {source['osm_extract']['retrieved_at_utc']} UTC ({source['osm_extract']['bytes']:,} bytes; SHA-256 `{source['osm_extract']['sha256']}`); OSM relation IDs `relation/14273608` (Kiba Park), `relation/12077221` (museum). Attribution: {source['osm_extract']['copyright']}.",
      f"- Added {data['new_building_citygml_ids']} unique CityGML buildings; {data['building_continuation_piece_count']} outside-square continuation meshes retain parent CityGML IDs. Roads: {data['extensions']['road_extension_pieces']} extension pieces ({data['extensions']['road_continuations']} continue existing OSM IDs); trees: {data['extensions']['new_tree_positions']} new mapped points; green: {data['extensions']['green_extension_pieces']}; water: {data['extensions']['water_extension_pieces']}; bridge extensions: {data['extensions']['new_bridges']}; park boundary extension polygons: {data['extensions']['park_extension_polygons']}.",
      f"- Unique new OSM IDs vs geometry pieces: `{json.dumps(data['added_osm_counts'],ensure_ascii=False)}`.",
      f"- Museum model: `{data['museum']['citygml_id']}` from `{data['museum']['source_file']}`, real PLATEAU LOD1. Solid height {data['museum']['lod1_height_m']:.3f} m vs CityGML measuredHeight {data['museum']['measured_height_m']:.3f} m (LOD1 − measuredHeight {data['museum']['lod1_minus_measured_height_m']:.3f} m); footprint IoU with OSM relation {data['museum']['footprint_iou_osm']:.6f}.",
      f"- LOD2 check: official 2025 API reports {next(m['lod2'] for m in plateau['mesh_files'] if m['mesh']=='53394614')} CityGML LOD2 features in museum mesh 53394614; Koto 2025 LOD2 3D Tiles are catalogued, but direct asset host access was blocked, so no 2025 LOD2 museum geometry was used.",
      '', '## Preservation and validation','',
      f"- v04 baseline inventory: {json.dumps(data['source_counts_v04'],ensure_ascii=False)}.",
      f"- Per-feature IDs unchanged: `{data['source_geometry_ids_equal_v04']}`.",
      f"- Per-feature vertex/face hashes unchanged: `{data['source_geometry_hashes_equal_v04']}`.",
      f"- Existing tree positions unchanged: `{data['tree_positions_equal_v04']}`; all mesh coordinates finite: `{data['all_coordinates_finite']}`.",
      f"- Museum full model footprint inside target extent: `{data['museum']['entire_model_inside_extent']}`.",
      f"- GLB reimport: `{data['glb_reimported']}`; meshes {data['glb_mesh_count']}; buildings {data['glb_citygml_building_id_count']}; faces valid: `{data['glb_all_meshes_have_faces']}`; existing building bounds max difference {data['glb_existing_building_bounds_max_error_m']:.8f} m.",
      f"- v05 sizes: BLEND {data['v05_sizes_bytes']['blend']:,} bytes; GLB {data['v05_sizes_bytes']['glb']:,} bytes.",
      f"- Previews: `{json.dumps(data['preview_sizes_bytes'],ensure_ascii=False)}` bytes.",
      f"- Source ground overlap was removed only in separate display surfaces; post-partition overlap areas: `{data['display_overlap_areas_m2']}` m². Original v04 source meshes remain hidden in `99_REFERENCE`.",
      '', '## Known limits','',
      '- OSM does not provide an independent cadastral boundary for the museum parcel in this extract; the museum relation is used for the actual mapped building footprint, and the complete mapped Kiba Park multipolygon defines the larger context. The extent is not a legal land boundary.',
      '- Some OSM roads, linear waterways, and new tree dimensions lack measured widths/heights; per-object widths and tree dimensions are estimates when source tags are absent.',
      '- The OSM API provides the ODbL declaration; the full ODbL and PLATEAU dataset-specific license text were not independently accessible from this environment. See LICENSE_DATA.md. No v05 model, GLB, raw extract, or data-derived report is eligible for public upload until terms are resolved.',
      '- Rendering and extent overlay are generated by `render_phase3d_previews.py`; preview sizes are added after that command succeeds.']
    markdown.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(f'Wrote {report.relative_to(ROOT)} and {markdown.relative_to(ROOT)}')
if __name__=='__main__':main()
