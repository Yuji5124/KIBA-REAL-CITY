from __future__ import annotations
import json, math, os, shutil, subprocess, sys, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/'scripts'))
from common import load_config,write_json

def main():
    cfg=load_config(); exe=os.environ.get('BLENDER_EXE') or shutil.which('blender')
    if not exe: raise SystemExit('Blender not found. Set BLENDER_EXE.')
    blend=ROOT/cfg['blend_file']; glb=ROOT/cfg['glb_file']; processed=ROOT/cfg['processed_file']
    if not blend.exists() or not glb.exists(): raise SystemExit('BLEND/GLB output missing; run build_blender.py first.')
    result=ROOT/'reports'/'validation_result.json'; result.parent.mkdir(parents=True,exist_ok=True)
    subprocess.run([exe,'--background','--python',str(ROOT/'scripts'/'blender_validate.py'),'--',str(blend),str(glb),str(processed),str(result)],check=True,cwd=ROOT)
    checks=json.loads(result.read_text(encoding='utf-8'))
    report_path=ROOT/cfg['report_json']; report=json.loads(report_path.read_text(encoding='utf-8')) if report_path.exists() else {}
    report.update({'blend_bytes':blend.stat().st_size,'glb_bytes':glb.stat().st_size})
    report['validation']={**report.get('validation',{}),**checks}
    write_json(cfg['report_json'],report)
    metrics=report.get('building_metrics',{})
    source_sizes=', '.join(f"{Path(x['path']).name} ({x['bytes']} bytes)" for x in report.get('source_file_details',[]))
    md=['# KIBA REAL CITY generation report','',f"- Status: {report.get('status','unknown')}",f"- Dataset: {cfg['dataset']['name']} ({cfg['dataset']['release_year'] or 'release year unconfirmed'})",f"- Source files: {source_sizes or ', '.join(Path(x).name for x in report.get('source_files',[]))}",f"- CityGML spec/schema: {', '.join(report.get('citygml_spec_versions',[])) or 'not identified'} / PLATEAU IUR {', '.join(report.get('plateau_iur_schema_versions',[])) or 'not identified'}",f"- Area: {cfg['location_name']}; center {cfg['center']['latitude']}, {cfg['center']['longitude']}; {cfg['extent_m']} m square",f"- Mesh codes (1 km): {', '.join(report.get('area',{}).get('mesh_codes_1km',[]))}",f"- Source building features: {report.get('building_features_in_source','unknown')}",f"- Buildings in extent: {report.get('buildings_in_extent',0)}",f"- LOD1 height range/mean: {metrics.get('lod1_height_min_m','?')} / {metrics.get('lod1_height_max_m','?')} / {metrics.get('lod1_height_mean_m','?')} m",f"- Footprint bounds (local m): {metrics.get('local_footprint_bounds_m','unknown')}",f"- Per-building position/base/height records: {len(report.get('building_records',[]))} entries in generation_report.json",f"- Coordinate XY storage: {report.get('coordinate_precision',{}).get('stored_xy_decimals_m','?')} decimal places in metres; maximum rounding error {report.get('coordinate_precision',{}).get('max_xy_rounding_error_m','?')} m",f"- measuredHeight differs from LOD1 geometry on {report.get('measured_height_differs_from_lod1_solid_count','?')} features; LOD1 Solid Z extent is used for generated height",f"- BLEND: {blend.stat().st_size} bytes",f"- GLB: {glb.stat().st_size} bytes",f"- CRS: {cfg['local_crs']}; vertical datum: {cfg['vertical_datum']}",'- Preview: reports/KIBA_REAL_CITY_preview.png','','## Validation']
    md += [f"- {k}: {'PASS' if v else 'FAIL'}" for k,v in checks.items() if isinstance(v,bool)]
    md += ['', '## Data gaps and warnings']+[f'- {x}' for x in report.get('data_gaps',[]) + report.get('warnings',[])]
    (ROOT/cfg['report_markdown']).write_text('\n'.join(md)+'\n',encoding='utf-8')
    failed=[k for k,v in checks.items() if isinstance(v,bool) and not v]
    print(f"BLEND {blend.stat().st_size} bytes; GLB {glb.stat().st_size} bytes; checks: {checks}")
    if failed: raise SystemExit('Failed checks: '+', '.join(failed))

if __name__=='__main__':main()
