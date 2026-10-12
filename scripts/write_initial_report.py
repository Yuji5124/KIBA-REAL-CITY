"""Write honest georeference and status reports before source data is available."""
from __future__ import annotations
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/'scripts'))
from common import load_config,area,mesh_1km_codes,write_json

def main():
    cfg=load_config(); bounds,center=area(cfg); half=cfg['extent_m']/2; meshes=mesh_1km_codes(bounds)
    reference={'location':cfg['location_name'],'center_wgs84':cfg['center'],'center_projected_m':[center[0],center[1]],'local_crs':cfg['local_crs'],'vertical_datum':cfg['vertical_datum'],'extent_m':cfg['extent_m'],'local_bounds_m':[-half,-half,half,half],'mesh_codes_1km':meshes,'clipping':'Building footprint polygons will be clipped to the square; boundary-crossing geometry has not yet been processed.','dataset':cfg['dataset']}
    report={'status':'awaiting_source_data','dataset':cfg['dataset'],'area':reference,'source_files':[],'source_crs':[],'buildings_in_extent':None,'other_features':{'roads':None,'vegetation':None,'bridges':None,'terrain':None},'data_gaps':['No official CityGML source data has been downloaded or supplied.','Dataset release year, license, source package URL, source CRS, vertical datum, and LOD remain unverified.','Road, park, vegetation, bridge, and terrain conversion is not implemented in Phase 1.'],'warnings':['This is an environment/setup report, not a generated real-city model.'],'validation':{'mesh_codes_computed':True,'source_data_present':False,'blend_generated':False,'glb_generated':False}}
    write_json(cfg['reference_file'],reference); write_json(cfg['report_json'],report)
    lines=['# KIBA REAL CITY generation report','','- Status: awaiting official source data',f"- Dataset: {cfg['dataset']['name']} (year, license, package, and LOD unverified)",f"- Area: {cfg['location_name']}; center WGS84 {cfg['center']['latitude']}, {cfg['center']['longitude']}; {cfg['extent_m']} m square",f"- Mesh codes (1 km): {', '.join(meshes)}",f"- Buildings converted: not yet measured",f"- CRS: {cfg['local_crs']}; vertical datum: {cfg['vertical_datum']}",'','## Blockers and data gaps']+[f'- {x}' for x in report['data_gaps']+report['warnings']]
    p=ROOT/cfg['report_markdown']; p.parent.mkdir(parents=True,exist_ok=True); p.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(f"Wrote georeference and pending-data report; intersecting meshes: {', '.join(meshes)}")

if __name__=='__main__':main()
