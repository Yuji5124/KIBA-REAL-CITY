"""Merge real CityGML/OSM additions with immutable v04 feature identities."""
from __future__ import annotations
import hashlib,json,math
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree as ET
from pyproj import Transformer
from shapely import constrained_delaunay_triangles,make_valid
from shapely.geometry import LineString,Point,Polygon,box
from shapely.ops import triangulate,unary_union
from shapely.errors import GEOSException
from phase3d_common import ROOT,ORIGIN,target_extent

OUT=ROOT/'data/processed/phase3d_features.json'
ROAD_WIDTH={'motorway':12.0,'trunk':10.0,'primary':8.0,'secondary':7.0,'tertiary':6.0,
 'unclassified':4.5,'residential':4.0,'living_street':4.0,'service':3.0,'pedestrian':3.0,
 'cycleway':2.5,'footway':2.0,'path':2.0,'steps':1.5,'track':3.0,'bridleway':2.0}
PATH_CLASSES={'footway','path','pedestrian','steps','cycleway'}
GREEN={'landuse':{'grass','meadow','forest','recreation_ground'},
       'leisure':{'garden'},'natural':{'grassland','wood','scrub','heath'}}
WATER={'natural':{'water','wetland'},'waterway':{'river','stream','canal','ditch'}}
WATER_WIDTH={'river':8.0,'canal':6.0,'stream':2.0,'ditch':1.5}
T=Transformer.from_crs('EPSG:4326','EPSG:6677',always_xy=True)
TRIANGULATION_FALLBACKS=0

def tags(e):return {t.attrib['k']:t.attrib['v'] for t in e.findall('tag')}
def encode(geom):
    geom=make_valid(geom)
    if geom.is_empty:return []
    if geom.geom_type=='Polygon': geoms=[geom]
    elif geom.geom_type=='MultiPolygon':geoms=list(geom.geoms)
    else:geoms=[g for g in getattr(geom,'geoms',[]) if g.geom_type=='Polygon' and not g.is_empty]
    records=[]
    for poly in geoms:
        # Quantize input, then repair again: narrow road buffers can become
        # self-touching if only their serialized boundary is rounded.
        ext=[(round(float(x),6),round(float(y),6)) for x,y in poly.exterior.coords]
        holes=[[(round(float(x),6),round(float(y),6)) for x,y in ring.coords] for ring in poly.interiors]
        fixed=make_valid(Polygon(ext,holes))
        parts=[fixed] if fixed.geom_type=='Polygon' else [p for p in getattr(fixed,'geoms',[]) if p.geom_type=='Polygon']
        for part in parts:
            if part.area<=1e-5:continue
            records.append({'exterior':[[float(x),float(y)] for x,y in part.exterior.coords],
              'interiors':[[[float(x),float(y)] for x,y in ring.coords] for ring in part.interiors]})
    return records
def mesh_data(polygons,label='unknown'):
    global TRIANGULATION_FALLBACKS
    verts=[];faces=[];index={}
    fallback=False
    for record in polygons:
        poly=Polygon(record['exterior'],record.get('interiors',[]))
        try: triangles=constrained_delaunay_triangles(poly).geoms
        except GEOSException:
            triangles=triangulate(poly);fallback=True
        for tri in triangles:
            if not poly.covers(tri) or tri.area<1e-7:continue
            points=list(tri.exterior.coords)[:3];face=[]
            for x,y in points:
                key=(float(x),float(y))
                if key not in index:index[key]=len(verts);verts.append(key)
                face.append(index[key])
            if len(set(face))==3:
                a,b,c=[verts[i] for i in face]
                if (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])<0:face.reverse()
                faces.append(face)
    mesh_area=sum(abs((verts[b][0]-verts[a][0])*(verts[c][1]-verts[a][1])-
                      (verts[c][0]-verts[a][0])*(verts[b][1]-verts[a][1]))/2 for a,b,c in faces)
    expected=sum(Polygon(p['exterior'],p.get('interiors',[])).area for p in polygons)
    if abs(mesh_area-expected)>max(.02,expected*1e-5):
        if not fallback:
            fallback=True;verts=[];faces=[];index={}
            for record in polygons:
                poly=Polygon(record['exterior'],record.get('interiors',[]))
                for tri in triangulate(poly):
                    if not poly.covers(tri) or tri.area<1e-7:continue
                    face=[]
                    for x,y in list(tri.exterior.coords)[:3]:
                        key=(float(x),float(y))
                        if key not in index:index[key]=len(verts);verts.append(key)
                        face.append(index[key])
                    if len(set(face))==3:
                        a,b,c=[verts[i] for i in face]
                        if (b[0]-a[0])*(c[1]-a[1])-(c[0]-a[0])*(b[1]-a[1])<0:face.reverse()
                        faces.append(face)
            mesh_area=sum(abs((verts[b][0]-verts[a][0])*(verts[c][1]-verts[a][1])-
                              (verts[c][0]-verts[a][0])*(verts[b][1]-verts[a][1]))/2 for a,b,c in faces)
            if abs(mesh_area-expected)>max(.02,expected*1e-5):
                raise ValueError(f'Triangulation error after fallback for {label}: {mesh_area:.4f} vs {expected:.4f}')
        else: raise ValueError(f'Triangulation error for {label}: {mesh_area:.4f} vs {expected:.4f}')
    if fallback:TRIANGULATION_FALLBACKS+=1
    return {'mesh_vertices_xy_m':[list(v) for v in verts],'mesh_faces':faces,
            'triangulated_area_m2':round(mesh_area,4),'triangulation_area_error_m2':round(abs(mesh_area-expected),5),
            'triangulation_fallback_used':fallback}
def from_records(records):
    return unary_union([Polygon(r['exterior'],r.get('interiors',[])) for r in records]) if records else Polygon()
def is_tagged(properties,rules):return any(properties.get(k) in vals for k,vals in rules.items())
def positive(value):
    try:
        v=float(str(value).replace('m','').strip())
        return v if math.isfinite(v) and v>0 else None
    except (TypeError,ValueError):return None
def meters(v):return T.transform(float(v[0]),float(v[1]))

def main():
    if OUT.exists():raise SystemExit('phase3d_features.json exists; refusing to overwrite.')
    source=json.loads((ROOT/'data/processed/phase3d_source.json').read_text(encoding='utf-8'))
    city=json.loads((ROOT/'data/processed/phase3d_buildings.json').read_text(encoding='utf-8'))
    oldp=json.loads((ROOT/'data/processed/phase2a_features.json').read_text(encoding='utf-8'))
    oldt=json.loads((ROOT/'data/processed/phase2b_features.json').read_text(encoding='utf-8'))
    oldbuild=json.loads((ROOT/'data/processed/buildings.json').read_text(encoding='utf-8'))
    raw_path=ROOT/'data/raw/kiba_phase3d_osm_map.osm';raw=raw_path.read_bytes()
    root=ET.fromstring(raw)
    if root.attrib.get('version')!='0.6' or 'odbl/1-0' not in root.attrib.get('license','').lower():
        raise SystemExit('OSM input does not declare ODbL 1.0.')
    nodes={n.attrib['id']:n for n in root.findall('node')}
    ways={w.attrib['id']:w for w in root.findall('way')}
    to_local=lambda lon,lat: tuple(a-b for a,b in zip(T.transform(float(lon),float(lat)),ORIGIN))
    def nxy(ref):
        n=nodes.get(str(ref))
        if n is None:raise ValueError(f'Missing OSM node/{ref}')
        return to_local(n.attrib['lon'],n.attrib['lat'])
    def way_geom(way):
        coords=[nxy(nd.attrib['ref']) for nd in way.findall('nd')]
        if len(coords)<2:return None
        if coords[0]==coords[-1] and len(coords)>=4:return make_valid(Polygon(coords))
        return LineString(coords)

    extent_info=source['extent'];target=box(*extent_info['bounds_local_m']);oldclip=box(-250,-250,250,250)
    outside=target.difference(oldclip)
    extent_geo=target_extent(ROOT/'data/raw/kiba_phase3d_museum_relation.osm',
                             ROOT/'data/raw/kiba_phase3d_park_relation.osm')
    park_full=extent_geo['park_geometry']
    museum_geom=extent_geo['museum_geometry']

    old_building_ids={b['id'] for b in oldbuild['buildings']}
    old_building_geom={b['id']:unary_union([Polygon(ring) for ring in b['footprints']]) for b in oldbuild['buildings']}
    all_building_geom=[unary_union([Polygon(p['exterior'],p['interiors']) for p in b['geometry']]) for b in city['buildings']]
    building_union=unary_union(all_building_geom)
    new_buildings=[];extensions=[]
    for record in city['buildings']:
        geom=unary_union([Polygon(p['exterior'],p['interiors']) for p in record['geometry']])
        bid=record['citygml_id']
        if bid in old_building_ids:
            extension=geom.difference(old_building_geom[bid]).intersection(target)
            if extension.area>0.02:
                piece={'source_citygml_id':bid,'phase3d_piece_id':bid+'::outside-v04',
                   'base_z_m':record['base_z_m'],'height_m':record['height_m'],
                   'height_source':record['height_source'],'geometry':encode(extension),
                   'source_file':record['source_file'],'part_status':'continuation outside immutable v04 geometry'}
                piece.update({'mesh_area_m2':round(extension.area,3)})
                if piece['geometry']:
                    piece.update(mesh_data(piece['geometry'],piece['phase3d_piece_id']))
                    extensions.append(piece)
        else:
            item={**record,'geometry':encode(geom),'feature_status':'new PLATEAU CityGML feature'}
            item.update(mesh_data(item['geometry'],bid))
            new_buildings.append(item)
    if set(r['citygml_id'] for r in new_buildings)&old_building_ids:
        raise SystemExit('New CityGML feature IDs collide with original v04 buildings.')
    # Ensure each OSM way is processed once and IDs stay source-trackable.
    old_road_ids={r['osm_id'] for r in oldp['roads']}
    old_tree_ids={r['osm_id'] for r in oldt['trees']}
    old_green_ids={r['osm_id'] for r in oldt['green_areas']}
    old_water_ids={r['osm_id'] for r in oldt['water_areas']}
    old_bridge_ids={r['osm_id'] for r in oldt['bridge_footprints']}
    roads=[];road_source_geoms=[];omitted=Counter()
    road_candidates=[]
    for way in ways.values():
        prop=tags(way);hw=prop.get('highway')
        if not hw or hw in {'proposed','construction','raceway','platform'} or prop.get('access')=='no':continue
        geom=way_geom(way)
        if geom is None or geom.is_empty:continue
        if geom.geom_type=='Polygon' and prop.get('area')=='yes':
            surface=geom;width=positive(prop.get('width'));width_source='OSM area geometry'
            gtype='mapped_area'
        elif geom.geom_type in ('LineString','MultiLineString','Polygon'):
            explicit=positive(prop.get('width'));width=explicit or ROAD_WIDTH.get(hw,2.5)
            width_source='OSM width tag' if explicit else 'estimated by OSM highway class'
            centerline=LineString(list(geom.exterior.coords)) if geom.geom_type=='Polygon' else geom
            surface=centerline.buffer(width/2,cap_style='flat',join_style='mitre');gtype='buffered_centerline'
        else:continue
        part=make_valid(surface.intersection(outside))
        if part.is_empty or part.area<0.01:continue
        road_candidates.append((hw,way,prop,part,width,width_source,gtype))
    rank={'motorway':0,'trunk':1,'primary':2,'secondary':3,'tertiary':4,'unclassified':5,
          'residential':6,'living_street':7,'service':8,'pedestrian':9,'footway':10,'path':11,'steps':12}
    road_candidates.sort(key=lambda x:(rank.get(x[0],15),x[1].attrib['id']))
    used_road=unary_union([from_records(r['display_polygons']) for r in oldp['roads']])
    for hw,way,prop,source_part,width,width_source,gtype in road_candidates:
        oid=f"way/{way.attrib['id']}"
        display=make_valid(source_part.difference(building_union).difference(used_road))
        polys=encode(display)
        if not polys:
            omitted['roads_fully_hidden_by_higher_priority_or_building']+=1;continue
        rec={'osm_id':oid,'source_id':oid,'tags':prop,'highway':hw,'name':prop.get('name'),
             'surface':prop.get('surface'),'width_m':width,'width_source':width_source,
             'geometry_type':gtype,'source_area_m2':round(source_part.area,3),
             'display_area_m2':round(display.area,3),'display_polygons':polys,
             'piece_status':'outside_v04_extent','continues_v04_feature':oid in old_road_ids,
             'crs':'EPSG:6677','source':'OpenStreetMap map API current extract'}
        rec.update(mesh_data(polys,oid));roads.append(rec);road_source_geoms.append(source_part)
        used_road=unary_union([used_road,display])
    road_union=unary_union([used_road,*road_source_geoms]) if road_source_geoms else used_road

    water=[];water_claimed=Polygon()
    for way in ways.values():
        prop=tags(way);geom=way_geom(way)
        if geom is None or geom.is_empty:continue
        oid=f"way/{way.attrib['id']}"
        is_water_area=geom.geom_type=='Polygon' and is_tagged(prop,WATER)
        is_waterway=prop.get('waterway') in WATER['waterway']
        if not is_water_area and not is_waterway:continue
        if is_water_area:surface=geom;width=positive(prop.get('width'));width_source='OSM mapped water polygon'
        else:
            kind=prop.get('waterway');width=positive(prop.get('width')) or WATER_WIDTH.get(kind,3.0)
            width_source='OSM width tag' if positive(prop.get('width')) else 'estimated by waterway class'
            centerline=LineString(list(geom.exterior.coords)) if geom.geom_type=='Polygon' else geom
            surface=centerline.buffer(width/2,cap_style='flat',join_style='mitre')
        part=make_valid(surface.intersection(outside))
        if part.is_empty or part.area<0.02:continue
        display=make_valid(part.difference(building_union).difference(road_union).difference(water_claimed))
        polys=encode(display)
        if not polys:omitted['water_no_visible_area']+=1;continue
        rec={'osm_id':oid,'source_id':oid,'tags':prop,'width_m':width,'width_source':width_source,
             'source_area_m2':round(part.area,3),'display_area_m2':round(display.area,3),
             'display_polygons':polys,'geometry_source':'OSM mapped geometry; width estimated only where absent',
             'piece_status':'outside_v04_extent','continues_v04_feature':oid in old_water_ids,
             'crs':'EPSG:6677','source':'OpenStreetMap map API current extract'}
        rec.update(mesh_data(polys,oid));water.append(rec);water_claimed=unary_union([water_claimed,display])

    green=[];green_claimed=Polygon()
    for way in ways.values():
        prop=tags(way);geom=way_geom(way)
        if geom is None or geom.geom_type!='Polygon' or not is_tagged(prop,GREEN):continue
        oid=f"way/{way.attrib['id']}"
        part=make_valid(geom.intersection(park_full).intersection(outside))
        if part.is_empty or part.area<0.05:continue
        display=make_valid(part.difference(building_union).difference(road_union)
                           .difference(water_claimed).difference(green_claimed))
        polys=encode(display)
        if not polys:omitted['green_no_visible_area']+=1;continue
        area_class=next((prop[k] for k in ('landuse','leisure','natural') if prop.get(k)), 'green')
        rec={'osm_id':oid,'source_id':oid,'tags':prop,'area_class':area_class,
             'source_area_m2':round(part.area,3),'display_area_m2':round(display.area,3),
             'display_polygons':polys,'geometry_source':'OSM mapped polygon clipped to mapped Kiba Park grounds',
             'piece_status':'outside_v04_extent','continues_v04_feature':oid in old_green_ids,
             'crs':'EPSG:6677','source':'OpenStreetMap map API current extract'}
        rec.update(mesh_data(polys,oid));green.append(rec);green_claimed=unary_union([green_claimed,display])

    bridges=[]
    for way in ways.values():
        prop=tags(way);geom=way_geom(way)
        if geom is None or geom.geom_type!='Polygon' or prop.get('man_made')!='bridge':continue
        oid=f"way/{way.attrib['id']}"
        part=make_valid(geom.intersection(outside))
        if part.is_empty or part.area<0.5:continue
        polys=encode(part)
        if not polys:continue
        layer=positive(prop.get('layer'));z=3.0*layer if layer and layer>0 else 0.0
        rec={'osm_id':oid,'source_id':oid,'tags':prop,'name':prop.get('name'),
             'source_area_m2':round(part.area,3),'display_z_m':z,
             'display_z_source':'estimated 3 m per OSM layer' if layer else 'not vertically resolved in OSM',
             'display_polygons':polys,'piece_status':'outside_v04_extent',
             'continues_v04_feature':oid in old_bridge_ids,'crs':'EPSG:6677',
             'source':'OpenStreetMap map API current extract'}
        rec.update(mesh_data(polys,oid));bridges.append(rec)

    trees=[]
    for node in nodes.values():
        prop=tags(node)
        if prop.get('natural')!='tree':continue
        x,y=to_local(node.attrib['lon'],node.attrib['lat'])
        pt=Point(x,y)
        if not target.covers(pt) or oldclip.covers(pt):continue
        oid=f"node/{node.attrib['id']}"
        if oid in old_tree_ids:continue
        oh=positive(prop.get('height'));oc=positive(prop.get('diameter_crown'))
        trees.append({'osm_id':oid,'source_id':oid,'x_m':round(x,4),'y_m':round(y,4),
            'tags':prop,'species':prop.get('species') or prop.get('taxon'),
            'height_observed_m':oh,'crown_diameter_observed_m':oc,
            'height_display_m':oh or 6.0,'height_display_source':'OSM height tag' if oh else 'estimated generic display height 6 m',
            'crown_diameter_display_m':oc or 4.0,'crown_diameter_display_source':'OSM diameter_crown tag' if oc else 'estimated generic display diameter 4 m',
            'position_source':'OpenStreetMap node tagged natural=tree','crs':'EPSG:6677'})

    park_part=make_valid(park_full.intersection(target).difference(oldclip))
    park_display=make_valid(park_part.difference(building_union).difference(road_union))
    park_polys=encode(park_display);park_rec={'osm_id':'relation/14273608','source_id':'relation/14273608',
      'name':'木場公園','tags':source['park']['tags'],'source_area_m2':round(park_part.area,3),
      'display_area_m2':round(park_display.area,3),'display_polygons':park_polys,
      'piece_status':'outside_v04_extent','crs':'EPSG:6677',
      'source':'OpenStreetMap relation full geometry','boundary_geometry':'full OSM park relation retained in source data'}
    park_rec.update(mesh_data(park_polys,'relation/14273608'))
    if not park_polys:raise SystemExit('No displayable Kiba Park boundary extension.')

    all_new_ids=[b['citygml_id'] for b in new_buildings]
    if len(all_new_ids)!=len(set(all_new_ids)):raise SystemExit('Duplicate CityGML IDs in added buildings.')
    # Check the intended overlap-removal policy directly on display surfaces.
    display_road=unary_union([from_records(r['display_polygons']) for r in roads])
    display_water=unary_union([from_records(r['display_polygons']) for r in water])
    display_green=unary_union([from_records(r['display_polygons']) for r in green])
    overlap={'road_building_m2':round(display_road.intersection(building_union).area,5),
      'green_road_m2':round(display_green.intersection(display_road).area,5),
      'water_road_m2':round(display_water.intersection(display_road).area,5),
      'green_water_m2':round(display_green.intersection(display_water).area,5)}
    result={'phase':'3D','crs':'EPSG:6677','origin_projected_m':list(ORIGIN),
      'bounds_local_m':extent_info['bounds_local_m'],'bounds_projected_epsg6677_m':extent_info['bounds_projected_epsg6677_m'],
      'bounds_wgs84_lonlat':city['bounds_wgs84_lonlat'],
      'extent_width_m':extent_info['width_m'],'extent_height_m':extent_info['height_m'],
      'mesh_codes_1km':extent_info['mesh_codes_1km'],
      'sources':{'osm':{'url':source['osm_extract']['url'],'sha256':source['osm_extract']['sha256'],
         'license':'ODbL 1.0','attribution':'OpenStreetMap and contributors',
         'relation_urls':[source['museum']['relation_full_url'],source['park']['relation_full_url']]},
         'plateau':city['dataset'],'citygml_source_files':city['source_files']},
      'museum':{'osm_id':'relation/12077221','citygml_id':city['museum_building_id'],
        'source_file':city['museum_building']['source_file'],
        'bounds_local_m':city['museum_building']['geometry_bounds_local_m'],
        'osm_citygml_footprint_validation':city['museum_building']['osm_validation'],
        'citygml_lod1_height_m':city['museum_building']['height_m'],
        'citygml_measuredHeight_m':city['museum_building']['measured_height_m'],
        'lod1_minus_measured_height_m':round(city['museum_building']['height_m']-city['museum_building']['measured_height_m'],3)
          if city['museum_building']['measured_height_m'] is not None else None},
      'buildings':{'new':new_buildings,'continuations':extensions},
      'osm':{'roads':roads,'trees':trees,'green_areas':green,'water_areas':water,'bridges':bridges,
        'park_extension':park_rec},
      'counts':{'existing_buildings_preserved':len(old_building_ids),'buildings_total':len(old_building_ids)+len(new_buildings),
         'new_building_ids':len(new_buildings),'building_continuations':len(extensions),
         'road_extension_pieces':len(roads),'road_extension_source_ids':len({r['osm_id'] for r in roads}),
         'road_continuations':sum(r['continues_v04_feature'] for r in roads),
         'new_tree_positions':len(trees),'green_extension_pieces':len(green),
         'green_continuations':sum(r['continues_v04_feature'] for r in green),
         'water_extension_pieces':len(water),'water_continuations':sum(r['continues_v04_feature'] for r in water),
         'new_bridges':len(bridges),'bridge_continuations':sum(r['continues_v04_feature'] for r in bridges),
         'park_extension_polygons':len(park_polys)},
      'display_overlap_areas_m2':overlap,'omitted':dict(omitted),
      'constrained_triangulation_fallback_count':TRIANGULATION_FALLBACKS,
      'tree_estimate_policy':{'default_height_m':6.0,'default_crown_diameter_m':4.0,
         'all_unobserved_dimensions_are_estimates':True},
      'geometry_policy':'Existing v04 meshes are immutable. All new map polygons are clipped outside the old square; connecting continuations use unique piece IDs and keep original source IDs in provenance.'}
    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'counts':result['counts'],'overlap':overlap,'omitted':result['omitted']},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
