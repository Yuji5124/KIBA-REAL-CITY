"""Record official PLATEAU catalog coverage for the Phase 3D extent."""
from __future__ import annotations
import json
from pathlib import Path
from urllib.request import Request,urlopen
from phase3d_common import ROOT

OUT=ROOT/'data/processed/phase3d_plateau_catalog.json'
def get_json(url):
    req=Request(url,headers={'User-Agent':'KIBA-REAL-CITY/Phase3D catalog research'})
    with urlopen(req,timeout=45) as response:
        return json.load(response)

def main():
    source=json.loads((ROOT/'data/processed/phase3d_source.json').read_text(encoding='utf-8'))
    if OUT.exists(): raise SystemExit('Phase 3D PLATEAU catalog record exists; refusing to overwrite.')
    lon0,lat0,lon1,lat1=source['extent']['bounds_wgs84_lonlat']
    bbox=','.join(f'{v:.10f}' for v in (lon0,lat0,lon1,lat1))
    region_url='https://api.plateauview.mlit.go.jp/datacatalog/citygml/r:'+bbox
    catalog_url='https://api.plateauview.mlit.go.jp/datacatalog/plateau-datasets'
    region=get_json(region_url);catalog=get_json(catalog_url)
    koto=next((c for c in region.get('cities',[]) if c.get('cityCode')=='13108'),None)
    if not koto: raise SystemExit('Official PLATEAU CityGML API did not return Koto City.')
    bldg={f['code']:f for f in koto.get('files',{}).get('bldg',[])}
    expected=set(source['extent']['mesh_codes_1km'])
    if not expected.issubset(bldg): raise SystemExit(f'PLATEAU bldg files missing expected meshes: {sorted(expected-set(bldg))}')
    metadata=[{k:d.get(k) for k in ('id','year','registration_year','spec','format','lod','texture','url','composite_url','file_size')}
              for d in catalog.get('datasets',[]) if d.get('city_code')=='13108' and d.get('type_en')=='bldg']
    local=[]
    for code in sorted(expected):
        p=ROOT/'data/raw'/f'{code}_bldg_6697_op.gml'
        if not p.is_file(): raise SystemExit(f'Missing local CityGML mesh: {p.relative_to(ROOT)}')
        local.append({'mesh':code,'file':str(p.relative_to(ROOT)),'bytes':p.stat().st_size})
    record={'catalog_source':'Project PLATEAU official datacatalog API',
      'region_query_url':region_url,'catalog_url':catalog_url,
      'region_query_city':{k:koto.get(k) for k in ('cityCode','cityName','year','registrationYear','spec','url')},
      'mesh_files':[{'mesh':c,'lod0':bldg[c].get('lod0'),'lod1':bldg[c].get('lod1'),
          'lod2':bldg[c].get('lod2'),'lod3':bldg[c].get('lod3'),
          'file_size':bldg[c].get('fileSize'),'citygml_url':bldg[c].get('url')} for c in sorted(expected)],
      'official_2025_building_3dtiles_datasets':metadata,
      'local_2023_citygml_meshes':local,
      'interpretation':{
        'required_meshes_already_present_locally':True,
        'additional_citygml_mesh_download_needed':False,
        'museum_mesh_lod2_count':bldg.get('53394614',{}).get('lod2'),
        'lod2_note':'2025 official extent query reports zero LOD2 CityGML features in mesh 53394614, which contains the museum. City-wide LOD2 3D Tiles are listed, but individual tile assets are hosted on an inaccessible assets.cms.plateau.reearth.io origin in this environment; museum LOD2 is not assumed.'}}
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(record,ensure_ascii=False,indent=2))
if __name__=='__main__': main()
