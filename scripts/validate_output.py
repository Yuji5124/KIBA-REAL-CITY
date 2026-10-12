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
    report.update({'blend_bytes':blend.stat().st_size,'glb_bytes':glb.stat().st_size,'validation':checks})
    write_json(cfg['report_json'],report)
    md=['# KIBA REAL CITY generation report','',f"- Status: {report.get('status','unknown')}",f"- Dataset: {cfg['dataset']['name']} ({cfg['dataset']['release_year'] or 'release year unconfirmed'})",f"- Area: {cfg['location_name']}; center {cfg['center']['latitude']}, {cfg['center']['longitude']}; {cfg['extent_m']} m square",f"- Mesh codes (1 km): {', '.join(report.get('area',{}).get('mesh_codes_1km',[]))}",f"- Buildings in extent: {report.get('buildings_in_extent',0)}",f"- BLEND: {blend.stat().st_size} bytes",f"- GLB: {glb.stat().st_size} bytes",f"- CRS: {cfg['local_crs']}; vertical datum: {cfg['vertical_datum']}",'','## Validation']
    md += [f"- {k}: {'PASS' if v else 'FAIL'}" for k,v in checks.items() if isinstance(v,bool)]
    md += ['', '## Data gaps and warnings']+[f'- {x}' for x in report.get('data_gaps',[]) + report.get('warnings',[])]
    (ROOT/cfg['report_markdown']).write_text('\n'.join(md)+'\n',encoding='utf-8')
    failed=[k for k,v in checks.items() if isinstance(v,bool) and not v]
    print(f"BLEND {blend.stat().st_size} bytes; GLB {glb.stat().st_size} bytes; checks: {checks}")
    if failed: raise SystemExit('Failed checks: '+', '.join(failed))

if __name__=='__main__':main()
