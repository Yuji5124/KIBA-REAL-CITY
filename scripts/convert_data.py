from __future__ import annotations
import json, math, re, sys
from pathlib import Path
from xml.etree import ElementTree as ET
from pyproj import CRS, Transformer
from shapely.geometry import Polygon, box
from shapely.ops import unary_union
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
    out=[]; warnings=[]; source_crs=set(); citygml_versions=set(); plateau_model_versions=set(); source_buildings=0; measured_mismatches=0; xy_rounding_errors=[]
    to_geo=Transformer.from_crs('EPSG:4326',cfg['local_crs'],always_xy=True); cx,cy=to_geo.transform(cfg['center']['longitude'],cfg['center']['latitude'])
    for path in files:
        root=ET.parse(path).getroot(); crs=find_source_crs(root,cfg); source_crs.add(crs)
        schema_location=next((v for k,v in root.attrib.items() if lname(k)=='schemaLocation'),'')
        citygml_versions.update(re.findall(r'http://www\.opengis\.net/citygml/(\d+\.\d+)',schema_location))
        plateau_model_versions.update(re.findall(r'/iur/(?:uro|urf)/(\d+\.\d+)',schema_location))
        source=CRS.from_user_input(crs)
        trans=Transformer.from_crs(source,cfg['local_crs'],always_xy=True)
        axes=source.axis_info
        # EPSG:6697 CityGML ordinates are latitude, longitude, height.  The
        # always_xy transformer expects longitude, latitude, so reorder north/east axes.
        swap_xy=(len(axes)>=2 and axes[0].direction.lower() in {'north','south'}
                 and axes[1].direction.lower() in {'east','west'})
        for building in (e for e in root.iter() if lname(e.tag)=='Building'):
            source_buildings+=1; bid=next((v for k,v in building.attrib.items() if lname(k)=='id'),f'{path.stem}_building_{source_buildings}')
            polygons=[]
            roof_edge=next((e for e in building if lname(e.tag)=='lod0RoofEdge'),None)
            footprint_region=roof_edge if roof_edge is not None else building
            for ext in (e for e in footprint_region.iter() if lname(e.tag)=='exterior'):
                pts=coordinates(ext)
                if len(pts)<4: continue
                transformed=[]; ring_z=[]
                for p in pts:
                    a,b=(p[1],p[0]) if swap_xy else (p[0],p[1])
                    z=p[2] if len(p)>2 else 0.0
                    x,y=trans.transform(a,b)
                    if all(math.isfinite(v) for v in (x,y,z)):
                        lx=x-cx; ly=y-cy
                        xy_rounding_errors.append(math.hypot(round(lx,4)-lx,round(ly,4)-ly))
                        transformed.append((lx,ly)); ring_z.append(z)
                if len(transformed)>=4:
                    poly=Polygon(transformed)
                    if not poly.is_empty and poly.area>0: polygons.append((min(ring_z,default=0),poly))
            if not polygons and roof_edge is not None:
                # Some CityGML exports omit the LOD0 roof edge; fall back to all
                # surface rings and use the lowest, largest valid ring below.
                for ext in (e for e in building.iter() if lname(e.tag)=='exterior'):
                    pts=coordinates(ext)
                    if len(pts)<4: continue
                    transformed=[]; ring_z=[]
                    for p in pts:
                        a,b=(p[1],p[0]) if swap_xy else (p[0],p[1])
                        z=p[2] if len(p)>2 else 0.0; x,y=trans.transform(a,b)
                        if all(math.isfinite(v) for v in (x,y,z)):
                            lx=x-cx; ly=y-cy
                            xy_rounding_errors.append(math.hypot(round(lx,4)-lx,round(ly,4)-ly))
                            transformed.append((lx,ly)); ring_z.append(z)
                    if len(transformed)>=4:
                        poly=Polygon(transformed)
                        if not poly.is_empty and poly.area>0: polygons.append((min(ring_z,default=0),poly))
            if not polygons: warnings.append(f'{bid}: no usable polygon rings'); continue
            # The lowest ring is the ground outline in ordinary LOD1/LOD2 buildings.
            low=min(z for z,_ in polygons); footprint=make_valid(max((p for z,p in polygons if abs(z-low)<0.01),key=lambda p:p.area))
            footprint=footprint.intersection(box(-cfg['extent_m']/2,-cfg['extent_m']/2,cfg['extent_m']/2,cfg['extent_m']/2))
            if footprint.is_empty: continue
            measured_height=None
            for e in building.iter():
                if lname(e.tag) in {'measuredHeight','height'} and e.text:
                    try: measured_height=float(e.text.strip())
                    except ValueError: pass
                    if measured_height and measured_height>0: break
            lod1=next((e for e in building if lname(e.tag)=='lod1Solid'),None)
            solid_z=[]
            if lod1 is not None:
                for p in coordinates(lod1):
                    if len(p)>2 and math.isfinite(p[2]): solid_z.append(p[2])
            if solid_z:
                base_z=min(solid_z); top_z=max(solid_z); height=top_z-base_z
                height_source='CityGML LOD1 Solid vertical extent'
            elif measured_height and math.isfinite(measured_height):
                base_z=0.0; height=measured_height; height_source='CityGML measuredHeight (LOD1 solid unavailable)'
            else:
                warnings.append(f'{bid}: no valid LOD1 solid or measured height; skipped'); continue
            if not math.isfinite(height) or height<=0:
                warnings.append(f'{bid}: no valid positive height; skipped'); continue
            if measured_height and abs(measured_height-height)>0.5: measured_mismatches+=1
            geoms=[footprint] if footprint.geom_type=='Polygon' else list(getattr(footprint,'geoms',[]))
            ring=[]
            for geom in geoms:
                if geom.geom_type!='Polygon' or geom.area<=0: continue
                ring.append([[round(x,4),round(y,4)] for x,y in geom.exterior.coords])
            if ring: out.append({'id':bid,'base_z_m':round(base_z,3),'height_m':round(height,3),'height_source':height_source,'measured_height_m':measured_height,'footprints':ring,'source_file':str(path.relative_to(ROOT))})
    if not out: raise SystemExit(f'No usable in-area buildings found among {source_buildings} CityGML Building features. Inspect CRS and CityGML content; no synthetic geometry was generated.')
    half=cfg['extent_m']/2
    write_json(cfg['processed_file'],{'crs':cfg['local_crs'],'center_projected_m':[cx,cy],'bounds_local_m':[-half,-half,half,half],'source_crs':sorted(source_crs),'buildings':out,'warnings':warnings})
    ref={'location':cfg['location_name'],'center_wgs84':cfg['center'],'center_projected_m':[cx,cy],'local_crs':cfg['local_crs'],'vertical_datum':cfg['vertical_datum'],'extent_m':cfg['extent_m'],'mesh_codes_1km':mesh,'clipping':'Building footprint polygons intersecting the 500 m square are clipped to its boundary; elevations/heights are preserved as source values.','dataset':cfg['dataset']}
    write_json(cfg['reference_file'],ref)
    xy=[pt for b in out for ring in b['footprints'] for pt in ring]
    heights=[b['height_m'] for b in out]
    building_records=[]
    for b in out:
        shape=unary_union([Polygon(ring) for ring in b['footprints']])
        center=shape.centroid
        building_records.append({'citygml_id':b['id'],'centroid_local_m':[round(center.x,4),round(center.y,4)],'footprint_bounds_local_m':[round(v,4) for v in shape.bounds],'base_z_m':b['base_z_m'],'lod1_height_m':b['height_m'],'measuredHeight_attribute_m':b['measured_height_m'],'source_file':b['source_file']})
    archive_paths=sorted((ROOT/cfg['input_dir']).rglob('*.zip'))
    report={'status':'converted','dataset':cfg['dataset'],'source_files':[str(p.relative_to(ROOT)) for p in files],'source_file_details':[{'path':str(p.relative_to(ROOT)),'bytes':p.stat().st_size} for p in files],'source_archives':[{'path':str(p.relative_to(ROOT)),'bytes':p.stat().st_size} for p in archive_paths],'source_crs':sorted(source_crs),'citygml_spec_versions':sorted(citygml_versions),'plateau_iur_schema_versions':sorted(plateau_model_versions),'source_axis_order':'EPSG:6697 north/east/up source ordinates are reordered to east/north before projection','coordinate_precision':{'stored_xy_decimals_m':4,'max_xy_rounding_error_m':max(xy_rounding_errors,default=0.0)},'area':ref,'building_features_in_source':source_buildings,'buildings_in_extent':len(out),'building_metrics':{'lod1_height_min_m':min(heights),'lod1_height_max_m':max(heights),'lod1_height_mean_m':round(sum(heights)/len(heights),3),'base_z_min_m':min(b['base_z_m'] for b in out),'base_z_max_m':max(b['base_z_m'] for b in out),'footprint_polygon_count':sum(len(b['footprints']) for b in out),'local_footprint_bounds_m':[min(p[0] for p in xy),min(p[1] for p in xy),max(p[0] for p in xy),max(p[1] for p in xy)]},'building_records':building_records,'height_method':'LOD1 Solid Z max-min; base elevation retained separately; measuredHeight preserved as source metadata','measured_height_differs_from_lod1_solid_count':measured_mismatches,'other_features':{'roads':0,'vegetation':0,'bridges':0,'terrain':0},'data_gaps':['Roads, vegetation, bridges and terrain are not converted in Phase 1.','Dataset release year is from the supplied official dataset identifier; license is not present in the provided per-mesh archives and remains unverified.'],'warnings':warnings,'validation':{'mesh_codes_computed':bool(mesh),'all_footprints_inside_500m_extent':all(-half-0.01<=x<=half+0.01 and -half-0.01<=y<=half+0.01 for x,y in xy),'all_buildings_have_positive_finite_height':all(math.isfinite(b['height_m']) and b['height_m']>0 for b in out),'building_count_nonzero':bool(out)}}
    write_json(cfg['report_json'],report)
    print(f"Converted {len(out)} buildings from {source_buildings} source features; meshes: {', '.join(mesh)}")

if __name__=='__main__': main()
