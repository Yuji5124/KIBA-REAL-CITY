from __future__ import annotations
import json, math, re, sys
from pathlib import Path
from xml.etree import ElementTree as ET
from pyproj import CRS, Transformer
from shapely.geometry import Polygon, box
from shapely.validation import make_valid
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/'scripts'))
from common import load_config,area,mesh_1km_codes,write_json

def lname(tag): return tag.rsplit('}',1)[-1]

def coordinates(node):
    result=[]
    for e in node.iter():
        if lname(e.tag)!='posList' or not e.text: continue
        vals=[float(x) for x in e.text.split()]
        dim=int(e.attrib.get('srsDimension','3'))
        if dim < 2 or len(vals)%dim: continue
        result.extend([tuple(vals[i:i+dim]) for i in range(0,len(vals),dim)])
    return result

def find_source_crs(root, cfg):
    srs=next((e.attrib['srsName'] for e in root.iter() if e.attrib.get('srsName')),None)
    if not srs: return cfg['source_crs']
    m=re.search(r'(?:EPSG(?::|/|::|/0/)|urn:ogc:def:crs:EPSG::)(\d+)$',srs,re.I)
    return f'EPSG:{m.group(1)}' if m else srs

def main():
    cfg=load_config(); bounds,center=area(cfg); clip=box(*bounds); mesh=mesh_1km_codes(bounds)
    files=sorted(p for p in (ROOT/cfg['input_dir']).rglob('*') if p.suffix.lower() in {'.gml','.xml'})
    if not files: raise SystemExit(f"No CityGML found in {cfg['input_dir']}. Download and extract official source data first.")
    out=[]; warnings=[]; source_crs=set(); source_buildings=0
    to_geo=Transformer.from_crs('EPSG:4326',cfg['local_crs'],always_xy=True); cx,cy=to_geo.transform(cfg['center']['longitude'],cfg['center']['latitude'])
    for path in files:
        root=ET.parse(path).getroot(); crs=find_source_crs(root,cfg); source_crs.add(crs)
        trans=Transformer.from_crs(CRS.from_user_input(crs),cfg['local_crs'],always_xy=True)
        for building in (e for e in root.iter() if lname(e.tag)=='Building'):
            source_buildings+=1; bid=next((v for k,v in building.attrib.items() if lname(k)=='id'),f'{path.stem}_building_{source_buildings}')
            polygons=[]; zs=[]
            for ext in (e for e in building.iter() if lname(e.tag)=='exterior'):
                pts=coordinates(ext)
                if len(pts)<4: continue
                transformed=[]
                for p in pts:
                    x,y=trans.transform(p[0],p[1]); z=p[2] if len(p)>2 else 0.0
                    if all(math.isfinite(v) for v in (x,y,z)):
                        transformed.append((x-cx,y-cy)); zs.append(z)
                if len(transformed)>=4:
                    poly=Polygon(transformed)
                    if not poly.is_empty and poly.area>0: polygons.append((min((p[2] for p in pts if len(p)>2),default=0),poly))
            if not polygons: warnings.append(f'{bid}: no usable polygon rings'); continue
            # The lowest ring is the ground outline in ordinary LOD1/LOD2 buildings.
            low=min(z for z,_ in polygons); footprint=make_valid(max((p for z,p in polygons if abs(z-low)<0.01),key=lambda p:p.area))
            footprint=footprint.intersection(box(-cfg['extent_m']/2,-cfg['extent_m']/2,cfg['extent_m']/2,cfg['extent_m']/2))
            if footprint.is_empty: continue
            height=None; height_source=None
            for e in building.iter():
                if lname(e.tag) in {'measuredHeight','height'} and e.text:
                    try: height=float(e.text.strip()); height_source='CityGML measuredHeight'
                    except ValueError: pass
                    if height and height>0: break
            if not height and zs:
                height=max(zs)-min(zs); height_source='CityGML coordinate vertical range'
            if not height or not math.isfinite(height) or height<=0:
                warnings.append(f'{bid}: no valid height; skipped'); continue
            geoms=[footprint] if footprint.geom_type=='Polygon' else list(getattr(footprint,'geoms',[]))
            ring=[]
            for geom in geoms:
                if geom.geom_type!='Polygon' or geom.area<=0: continue
                ring.append([[round(x,4),round(y,4)] for x,y in geom.exterior.coords])
            if ring: out.append({'id':bid,'height_m':round(height,3),'height_source':height_source,'footprints':ring,'source_file':str(path.relative_to(ROOT))})
    if not out: raise SystemExit(f'No usable in-area buildings found among {source_buildings} CityGML Building features. Inspect CRS and CityGML content; no synthetic geometry was generated.')
    half=cfg['extent_m']/2
    write_json(cfg['processed_file'],{'crs':cfg['local_crs'],'center_projected_m':[cx,cy],'bounds_local_m':[-half,-half,half,half],'source_crs':sorted(source_crs),'buildings':out,'warnings':warnings})
    ref={'location':cfg['location_name'],'center_wgs84':cfg['center'],'center_projected_m':[cx,cy],'local_crs':cfg['local_crs'],'vertical_datum':cfg['vertical_datum'],'extent_m':cfg['extent_m'],'mesh_codes_1km':mesh,'clipping':'Building footprint polygons intersecting the 500 m square are clipped to its boundary; elevations/heights are preserved as source values.','dataset':cfg['dataset']}
    write_json(cfg['reference_file'],ref)
    report={'status':'converted','dataset':cfg['dataset'],'source_files':[str(p.relative_to(ROOT)) for p in files],'source_crs':sorted(source_crs),'area':ref,'building_features_in_source':source_buildings,'buildings_in_extent':len(out),'other_features':{'roads':0,'vegetation':0,'bridges':0,'terrain':0},'data_gaps':['Roads, vegetation, bridges and terrain are not converted in Phase 1.','Vertical datum and dataset release/license require confirmation from source package metadata.'],'warnings':warnings,'validation':{'mesh_codes_computed':bool(mesh),'all_buildings_have_positive_finite_height':all(math.isfinite(b['height_m']) and b['height_m']>0 for b in out),'building_count_nonzero':bool(out)}}
    write_json(cfg['report_json'],report)
    print(f"Converted {len(out)} buildings from {source_buildings} source features; meshes: {', '.join(mesh)}")

if __name__=='__main__': main()
