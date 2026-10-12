"""Extract real 2023 PLATEAU LOD1 footprints for the Phase 3D extent."""
from __future__ import annotations
import json,math,re
from pathlib import Path
from xml.etree import ElementTree as ET
from pyproj import CRS,Transformer
from shapely import make_valid
from shapely.geometry import Polygon,box
from shapely.ops import unary_union
from phase3d_common import ROOT,ORIGIN,extent_metadata

OUT=ROOT/'data/processed/phase3d_buildings.json'
def lname(tag): return tag.rsplit('}',1)[-1]
def coords(node):
    result=[]
    for element in node.iter():
        if lname(element.tag)!='posList' or not element.text: continue
        values=[float(x) for x in element.text.split()]
        dim=int(element.attrib.get('srsDimension','3'))
        if dim>=2 and len(values)%dim==0:
            result.extend([values[i:i+dim] for i in range(0,len(values),dim)])
    return result
def encode(geometry):
    if geometry.geom_type=='Polygon': polys=[geometry]
    elif geometry.geom_type=='MultiPolygon': polys=list(geometry.geoms)
    else: polys=[g for g in getattr(geometry,'geoms',[]) if g.geom_type=='Polygon']
    return [{'exterior':[[round(float(x),4),round(float(y),4)] for x,y in p.exterior.coords],
             'interiors':[[[round(float(x),4),round(float(y),4)] for x,y in r.coords] for r in p.interiors]}
            for p in polys if not p.is_empty and p.area>1e-5]

def main():
    if OUT.exists(): raise SystemExit('phase3d_buildings.json exists; refusing to overwrite.')
    source=json.loads((ROOT/'data/processed/phase3d_source.json').read_text(encoding='utf-8'))
    extent_meta=source['extent']; local_bounds=extent_meta['bounds_local_m']
    clip=box(*local_bounds)
    required=['53394604','53394614']
    files=[ROOT/'data/raw'/f'{code}_bldg_6697_op.gml' for code in required]
    if any(not p.is_file() for p in files): raise SystemExit('A required CityGML mesh is missing.')
    cfg=json.loads((ROOT/'config/kiba_park.json').read_text(encoding='utf-8'))
    to_project=Transformer.from_crs('EPSG:4326','EPSG:6677',always_xy=True)
    cx,cy=to_project.transform(cfg['center']['longitude'],cfg['center']['latitude'])
    if abs(cx-ORIGIN[0])>1e-5 or abs(cy-ORIGIN[1])>1e-5:
        raise SystemExit('Shared v04 EPSG:6677 origin mismatch.')
    buildings=[];warnings=[];source_crs=set();citygml_versions=set();model_versions=set()
    source_count=0;rounding_error=0.0;museum_feature=None
    museum_point=(-10000,10000)
    # OSM museum footprint is used only as a position/identity cross-check.
    museum_bounds=source['museum']['bounds_local_m']
    museum_point=((museum_bounds[0]+museum_bounds[2])/2,(museum_bounds[1]+museum_bounds[3])/2)
    for path in files:
        root=ET.parse(path).getroot()
        schema=next((v for k,v in root.attrib.items() if lname(k)=='schemaLocation'),'')
        citygml_versions.update(re.findall(r'http://www\.opengis\.net/citygml/(\d+\.\d+)',schema))
        model_versions.update(re.findall(r'/iur/(?:uro|urf)/(\d+\.\d+)',schema))
        source_crs_name=next((e.attrib['srsName'] for e in root.iter() if e.attrib.get('srsName')),'EPSG:6697')
        crs=CRS.from_user_input(source_crs_name);source_crs.add(crs.to_string())
        transformer=Transformer.from_crs(crs,'EPSG:6677',always_xy=True)
        axes=crs.axis_info
        swap=(len(axes)>=2 and axes[0].direction.lower() in {'north','south'}
              and axes[1].direction.lower() in {'east','west'})
        for building in (e for e in root.iter() if lname(e.tag)=='Building'):
            source_count+=1
            bid=next((v for k,v in building.attrib.items() if lname(k)=='id'),f'{path.stem}_building_{source_count}')
            roof_edge=next((e for e in building if lname(e.tag)=='lod0RoofEdge'),None)
            region=roof_edge if roof_edge is not None else building
            candidates=[]
            for exterior in (e for e in region.iter() if lname(e.tag)=='exterior'):
                pts=coords(exterior);xy=[];zvals=[]
                for point in pts:
                    a,b=(point[1],point[0]) if swap else (point[0],point[1])
                    z=point[2] if len(point)>2 else 0.0
                    x,y=transformer.transform(a,b)
                    lx,ly=x-cx,y-cy
                    if all(math.isfinite(q) for q in (lx,ly,z)):
                        rounding_error=max(rounding_error,math.hypot(round(lx,4)-lx,round(ly,4)-ly))
                        xy.append((lx,ly));zvals.append(z)
                if len(xy)>=4:
                    geom=make_valid(Polygon(xy))
                    if not geom.is_empty and geom.area>0:candidates.append((min(zvals,default=0.0),geom))
            if not candidates:
                warnings.append(f'{bid}: no valid LOD0 roof-edge footprint');continue
            lowest=min(z for z,_ in candidates)
            footprint=max((g for z,g in candidates if abs(z-lowest)<0.01),key=lambda g:g.area)
            if not footprint.intersects(clip):continue
            lod1=next((e for e in building if lname(e.tag)=='lod1Solid'),None)
            solid_z=[p[2] for p in coords(lod1) if len(p)>2 and math.isfinite(p[2])] if lod1 is not None else []
            measured=None
            for element in building.iter():
                if lname(element.tag) in {'measuredHeight','height'} and element.text:
                    try:
                        value=float(element.text.strip())
                        if math.isfinite(value) and value>0:measured=value;break
                    except ValueError:pass
            if solid_z:base_z=min(solid_z);height=max(solid_z)-base_z;height_source='CityGML LOD1 Solid Z extent'
            elif measured:base_z=0.0;height=measured;height_source='CityGML measuredHeight fallback (LOD1 Solid unavailable)'
            else:
                warnings.append(f'{bid}: no valid LOD1 Solid or measuredHeight');continue
            if not math.isfinite(height) or height<=0:
                warnings.append(f'{bid}: invalid non-positive height');continue
            item={'citygml_id':bid,'base_z_m':round(base_z,3),'height_m':round(height,3),
                  'height_source':height_source,'measured_height_m':measured,
                  'geometry':encode(footprint),'geometry_bounds_local_m':[round(x,4) for x in footprint.bounds],
                  'source_file':str(path.relative_to(ROOT)),'source_crs':crs.to_string()}
            if not item['geometry']:warnings.append(f'{bid}: encoding yielded empty geometry');continue
            buildings.append(item)
            if (footprint.centroid.x-museum_point[0])**2+(footprint.centroid.y-museum_point[1])**2 < 300**2:
                pass
    ids=[b['citygml_id'] for b in buildings]
    if len(set(ids))!=len(ids):raise SystemExit('Duplicate CityGML IDs in required source meshes.')
    # Match the OSM museum multipolygon to the closest PLATEAU building by
    # intersection/union and centroid, retaining actual PLATEAU geometry.
    from shapely.geometry import Polygon as ShapePolygon
    osm_raw=ROOT/'data/raw/kiba_phase3d_museum_relation.osm'
    root=ET.parse(osm_raw).getroot();elements={e.tag.rsplit('}',1)[-1]+'|'+e.attrib.get('id',''):e for e in root}
    rel=elements['relation|12077221'];rings={'outer':[],'inner':[]}
    for member in rel.findall('member'):
        way=elements['way|'+member.attrib['ref']];pts=[]
        for nd in way.findall('nd'):
            node=elements['node|'+nd.attrib['ref']]
            x,y=Transformer.from_crs('EPSG:4326','EPSG:6677',always_xy=True).transform(float(node.attrib['lon']),float(node.attrib['lat']))
            pts.append((x-cx,y-cy))
        rings[member.attrib['role']].append(Polygon(pts))
    osm_geom=unary_union(rings['outer']).difference(unary_union(rings['inner']))
    best=None
    for item in buildings:
        polys=[ShapePolygon(p['exterior'],p['interiors']) for p in item['geometry']]
        geom=unary_union(polys)
        intersection=geom.intersection(osm_geom).area;union=geom.union(osm_geom).area
        iou=intersection/union if union else 0
        candidate=(iou,item,geom)
        if best is None or iou>best[0]:best=candidate
    if best is None or best[0]<0.7:raise SystemExit('No PLATEAU building strongly matched OSM museum footprint.')
    _,museum_feature,museum_geom=best
    museum_feature['osm_validation']={'osm_id':'relation/12077221','intersection_over_union':round(best[0],6),
       'plateau_coverage':round(museum_geom.intersection(osm_geom).area/museum_geom.area,6),
       'osm_coverage':round(museum_geom.intersection(osm_geom).area/osm_geom.area,6)}
    data={'phase':'3D','crs':'EPSG:6677','origin_projected_m':[cx,cy],
      'bounds_local_m':list(local_bounds),'bounds_wgs84_lonlat':extent_meta['bounds_wgs84_lonlat'],
      'mesh_codes_1km':required,'dataset':{'name':'Project PLATEAU Tokyo Koto City 3D City Model',
         'release_year':2023,'feature_type':'bldg','source_crs':sorted(source_crs),
         'citygml_versions':sorted(citygml_versions),'iur_versions':sorted(model_versions)},
      'source_count':source_count,'in_target_buildings':len(buildings),
      'buildings':buildings,'museum_building_id':museum_feature['citygml_id'],
      'museum_building':museum_feature,'coordinate_max_rounding_error_m':round(rounding_error,8),
      'warnings':warnings,'source_files':[{'path':str(p.relative_to(ROOT)),'bytes':p.stat().st_size} for p in files]}
    OUT.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:data[k] for k in ('source_count','in_target_buildings','museum_building_id','coordinate_max_rounding_error_m','source_files')},ensure_ascii=False,indent=2))
    print('museum_height_m',museum_feature['height_m'],'measured_height_m',museum_feature['measured_height_m'],'footprint_bounds',museum_feature['geometry_bounds_local_m'],'OSM_match',museum_feature['osm_validation'])
if __name__=='__main__': main()
