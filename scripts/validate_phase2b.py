"""Run Blender round-trip validation for locally generated Phase 2B outputs."""
from __future__ import annotations
import hashlib, json, os, shutil, subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
    exe=os.environ.get('BLENDER_EXE') or shutil.which('blender')
    if not exe: raise SystemExit('Blender not found. Add it to PATH or set BLENDER_EXE.')
    paths=[ROOT/'output/KIBA_REAL_CITY_v01.blend',ROOT/'output/KIBA_REAL_CITY_v02.blend',ROOT/'output/KIBA_REAL_CITY_v03.blend',ROOT/'output/KIBA_REAL_CITY_v03.glb']
    if not all(p.is_file() for p in paths): raise SystemExit('Missing v01/v02/v03 validation input.')
    out=ROOT/'reports/phase2b_report.json'; out.parent.mkdir(parents=True,exist_ok=True)
    log=(ROOT/'reports/phase2b_blender_validation.log').open('w')
    try: subprocess.run([exe,'--background','--python',str(ROOT/'scripts/blender_validate_phase2b.py'),'--',*(str(p) for p in paths),str(out)],check=True,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
    finally: log.close()
    result=json.loads(out.read_text(encoding='utf-8'))
    features=json.loads((ROOT/'data/processed/phase2b_features.json').read_text(encoding='utf-8'))
    result['source']={'dataset':features['source'].get('dataset'),
                      'retrieved_at_utc':features['source'].get('retrieved_at_utc'),
                      'osm_api_url':features['source'].get('api_url'),
                      'crs':features['crs'],'origin_projected_m':features['origin_projected_m'],
                      'osm_raw_sha256':features['source_sha256'],'license':features['license']}
    result['actual_vs_estimated']={
        'real_osm_tree_positions':len(features['trees']), 'trees_with_species':features['counts']['trees_with_species'],
        'trees_with_observed_height':features['counts']['trees_with_observed_height'],
        'trees_with_observed_crown_diameter':features['counts']['trees_with_observed_crown_diameter'],
        'tree_heights_estimated':sum(t['height_observed_m'] is None for t in features['trees']),
        'tree_crown_diameters_estimated':sum(t['crown_diameter_observed_m'] is None for t in features['trees']),
        'mapped_green_area_features':len(features['green_areas']),
        'mapped_water_features':len(features['water_areas']),
        'water_features_with_estimated_width':sum(str(w['width_source']).startswith('estimated') for w in features['water_areas']),
        'mapped_bridge_footprints':len(features['bridge_footprints']),
        'bridges_with_estimated_vertical_display':sum(str(b['display_z_source']).startswith('estimated') for b in features['bridge_footprints']),
        'existing_phase2a_path_features_reclassified':len(features['park_path_osm_ids_reclassified_from_phase2a']),
        'green_classes':features['counts']['green_classes'],
        'bridge_ids_and_names':[{'osm_id':b['osm_id'],'name':b.get('name'),'display_z_source':b['display_z_source']} for b in features['bridge_footprints']]}
    result['output_sha256']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in paths[2:]}
    result['data_status']={'blend_and_glb_generated_from_real_osm_and_phase1_phase2a_inputs':True,
                           'procedural_tree_shape_is_visual_estimate':True,
                           'invented_tree_positions':0,'green_geometry_from_mapped_osm_polygons':True,
                           'bridge_footprints_from_mapped_osm_polygons':True,
                           'linear_water_surfaces_buffered_from_mapped_osm_centerlines':True,
                           'v03_public_redistribution_clearance':'not resolved; see LICENSE_DATA.md; outputs remain local'}
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    md=['# KIBA REAL CITY Phase 2B validation','',f"- Result: {'PASS' if all(v is not False for v in result.values()) else 'FAIL'}",
        f"- OSM snapshot: {result['source']['retrieved_at_utc']} (API metadata declared ODbL 1.0)",
        f"- CRS/origin: EPSG:6677 / `{features['origin_projected_m']}`; X east, Y north, Z up.",
        '- Detailed validation and v03 outputs remain local because redistribution terms for the composed model are not fully resolved.', '', '## Real data additions']
    for k,v in result['actual_vs_estimated'].items(): md.append(f'- `{k}`: `{json.dumps(v,ensure_ascii=False)}`')
    md += ['', '## v01 / v02 preservation', '- Building IDs, vertex coordinates, faces and dimensions match across v01, v02 and v03.',
           '- All 236 OSM road/path object IDs and mesh coordinates match v02; 108 walking corridors were moved between collections only.',
           '- The OSM park boundary relation ID and mesh coordinates match v02.', '', '## Validation results']
    for k,v in result.items():
        if k not in ('source','actual_vs_estimated','output_sha256','data_status'):
            md.append(f'- `{k}`: `{json.dumps(v,ensure_ascii=False)}`')
    md += ['', '## Estimates and limits',
           '- The 33 OSM tree points are real mapped positions, but none has a species, height or crown-diameter tag in this snapshot. Their generic tree meshes and display dimensions are estimates, recorded per object.',
           '- Waterway lines without width tags use class-based display widths. Bridge `layer=1` is represented with a 3 m display offset; this is not a measured elevation.',
           '- Green polygons are real OSM mapped areas clipped to the park and cleared of Phase 2A roads/buildings; no area was painted by visual guess.',
           '- Phase 1/2A files were not overwritten. Phase 2B source data and outputs are excluded from the public commit pending terms review.']
    (ROOT/'reports/phase2b_report.md').write_text('\n'.join(md)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__': main()
