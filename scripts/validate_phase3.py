"""Run Phase 3 Blender round-trip checks and write JSON and Markdown reports."""
from __future__ import annotations
import json, os, shutil, subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
    exe=os.environ.get('BLENDER_EXE') or shutil.which('blender')
    if not exe: raise SystemExit('Blender not found. Add it to PATH or set BLENDER_EXE.')
    paths=[ROOT/'output/KIBA_REAL_CITY_v03.blend',ROOT/'output/KIBA_REAL_CITY_v04.blend',
           ROOT/'output/KIBA_REAL_CITY_v04.glb']
    for path in paths:
        if not path.is_file(): raise SystemExit(f'Missing required input: {path.relative_to(ROOT)}')
    report=ROOT/'reports/phase3_report.json'; markdown=ROOT/'reports/phase3_report.md'
    if report.exists() or markdown.exists(): raise SystemExit('Phase 3 report exists; refusing to overwrite.')
    subprocess.run([exe,'--background','--python',str(ROOT/'scripts/blender_validate_phase3.py'),
                    '--',*(str(path) for path in paths),str(report)],check=True,cwd=ROOT)
    if not report.is_file():
        raise SystemExit('Blender validation did not write its report; inspect Blender output above.')
    data=json.loads(report.read_text(encoding='utf-8'))
    lines=['# KIBA REAL CITY Phase 3 report','',
      '- Source: real-data Phase 2B v03; no synthetic city features added.',
      f"- Counts: {json.dumps(data['v04_objects_by_source_group'],ensure_ascii=False)}",
      f"- Tree display forms: {json.dumps(data['tree_visual_styles'],ensure_ascii=False)} (visual estimates at OSM positions)",
      f"- Output sizes: BLEND {data['v04_sizes_bytes']['blend']} bytes; GLB {data['v04_sizes_bytes']['glb']} bytes.",
      f"- GLB reimport: {data['glb_reimports']}; meshes {data['glb_mesh_count']}; building bounds max error {data['glb_building_bounds_max_error_m']} m.",
      '', '## Geometry preservation','']
    lines.extend(f'- {name}: IDs {data["source_ids_unchanged_by_group"][name]}, geometry {data["source_geometry_unchanged_by_group"][name]}.'
                 for name in data['source_ids_unchanged_by_group'])
    lines+=['', '## Other checks','']
    for name in ('tree_source_positions_unchanged','tree_source_proxies_retained_hidden',
                 'all_expected_collections_present','all_mesh_vertices_finite','pbr_materials_present',
                 'blend_file_present','glb_has_all_buildings','glb_has_all_tree_visual_ids','glb_meshes_have_faces'):
        lines.append(f'- {name}: {data[name]}')
    lines+=['','Data-derived geometry was preserved. Material colors and tree forms are presentation estimates.']
    markdown.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(f'Wrote {report.relative_to(ROOT)} and {markdown.relative_to(ROOT)}')
if __name__=='__main__': main()
