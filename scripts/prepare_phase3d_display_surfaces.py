"""Build non-overlapping display meshes while retaining original source meshes."""
from __future__ import annotations
import json
from pathlib import Path
from shapely import make_valid
from shapely.geometry import Polygon
from shapely.ops import unary_union
from prepare_phase3d_features import encode,mesh_data,from_records
from phase3d_common import ROOT

OUT=ROOT/'data/processed/phase3d_display_surfaces.json'
def main():
    if OUT.exists():raise SystemExit('phase3d_display_surfaces.json exists; refusing to overwrite.')
    extra=json.loads((ROOT/'data/processed/phase3d_features.json').read_text(encoding='utf-8'))
    roads02=json.loads((ROOT/'data/processed/phase2a_features.json').read_text(encoding='utf-8'))
    phase2b=json.loads((ROOT/'data/processed/phase2b_features.json').read_text(encoding='utf-8'))
    surfaces=[]
    rank={'motorway':0,'trunk':1,'primary':2,'secondary':3,'tertiary':4,'unclassified':5,
      'residential':6,'living_street':7,'service':8,'pedestrian':9,'footway':10,'path':11,'steps':12}
    road_items=[]
    for item in roads02['roads']:
        road_items.append({'source_id':item['osm_id'],'piece_id':'v04:'+item['osm_id'],
          'feature_type':'road_display','highway':item['highway'],'tags':item['tags'],
          'polygons':item['display_polygons'],'continues_v04':True,'z_m':0.02,
          'name':item.get('name'),'width_m':item.get('width_m'),'width_source':item.get('width_source')})
    for item in extra['osm']['roads']:
        road_items.append({'source_id':item['osm_id'],'piece_id':'outside-v04:'+item['osm_id'],
          'feature_type':'road_display','highway':item['highway'],'tags':item['tags'],
          'polygons':item['display_polygons'],'continues_v04':item['continues_v04_feature'],
          'z_m':0.02,'name':item.get('name'),'width_m':item.get('width_m'),
          'width_source':item.get('width_source')})
    road_items.sort(key=lambda r:(rank.get(r['highway'],15),r['piece_id']))
    road_union=Polygon();claimed=Polygon()
    for item in road_items:
        source_geom=from_records(item['polygons'])
        road_union=unary_union([road_union,source_geom])
        display=make_valid(source_geom.difference(claimed))
        claimed=unary_union([claimed,display])
        polys=encode(display)
        item['display_polygons']=polys
        if polys:item.update(mesh_data(polys,item['piece_id']))
        else:item.update({'mesh_vertices_xy_m':[],'mesh_faces':[],'triangulated_area_m2':0.0})
        item['display_area_m2']=round(display.area,6);item['overlap_removed_m2']=round(source_geom.area-display.area,6)
        surfaces.append(item)
    road_visible=unary_union([from_records(r['display_polygons']) for r in surfaces if r['feature_type']=='road_display'])

    # Waterway duplicates are resolved by partitioning the exact union into
    # disjoint, individually tagged source parts.
    water_items=[]
    for item in phase2b['water_areas']:
        water_items.append({'source_id':item['osm_id'],'piece_id':'v04:'+item['osm_id'],
           'feature_type':'water_display','tags':item['tags'],'polygons':item['polygons'],
           'continues_v04':True,'width_m':item.get('width_m'),'width_source':item.get('width_source')})
    for item in extra['osm']['water_areas']:
        water_items.append({'source_id':item['osm_id'],'piece_id':'outside-v04:'+item['osm_id'],
           'feature_type':'water_display','tags':item['tags'],'polygons':item['display_polygons'],
           'continues_v04':item['continues_v04_feature'],'width_m':item.get('width_m'),'width_source':item.get('width_source')})
    water_items.sort(key=lambda r:r['piece_id'])
    water_union=Polygon();claimed=Polygon()
    for item in water_items:
        src=from_records(item['polygons']);water_union=unary_union([water_union,src])
        display=make_valid(src.difference(road_visible).difference(claimed))
        claimed=unary_union([claimed,display]);polys=encode(display);item['display_polygons']=polys
        if polys:item.update(mesh_data(polys,item['piece_id']))
        else:item.update({'mesh_vertices_xy_m':[],'mesh_faces':[],'triangulated_area_m2':0.0})
        item['display_area_m2']=round(display.area,6);item['overlap_removed_m2']=round(src.area-display.area,6)
        surfaces.append(item)
    water_visible=unary_union([from_records(r['display_polygons']) for r in surfaces if r['feature_type']=='water_display'])

    green_items=[]
    for item in phase2b['green_areas']:
        green_items.append({'source_id':item['osm_id'],'piece_id':'v04:'+item['osm_id'],
          'feature_type':'grass_display','tags':item['tags'],'area_class':item['area_class'],
          'polygons':item['polygons'],'continues_v04':True})
    for item in extra['osm']['green_areas']:
        green_items.append({'source_id':item['osm_id'],'piece_id':'outside-v04:'+item['osm_id'],
          'feature_type':'grass_display','tags':item['tags'],'area_class':item['area_class'],
          'polygons':item['display_polygons'],'continues_v04':item['continues_v04_feature']})
    green_items.sort(key=lambda r:r['piece_id'])
    green_union=Polygon();claimed=Polygon()
    for item in green_items:
        src=from_records(item['polygons'])
        green_union=unary_union([green_union,src])
        display=make_valid(src.difference(road_visible).difference(water_visible).difference(claimed))
        claimed=unary_union([claimed,display]);polys=encode(display);item['display_polygons']=polys
        if polys:item.update(mesh_data(polys,item['piece_id']))
        else:item.update({'mesh_vertices_xy_m':[],'mesh_faces':[],'triangulated_area_m2':0.0})
        item['display_area_m2']=round(display.area,6);item['overlap_removed_m2']=round(src.area-display.area,6)
        surfaces.append(item)
    green_visible=unary_union([from_records(r['display_polygons']) for r in surfaces if r['feature_type']=='grass_display'])

    # Kiba Park is the low base surface. Its source geometry is retained,
    # while raised road/water/grass displays have no coplanar overlap.
    old_park=from_records(roads02['park']['display_polygons'])
    extension=from_records(extra['osm']['park_extension']['display_polygons'])
    park_union=unary_union([old_park,extension])
    park_items=[]
    for piece_id,geom,source_id in (('v04:relation/14273608',old_park,'relation/14273608'),
                                     ('outside-v04:relation/14273608',extension,'relation/14273608')):
        polygons=encode(geom)
        record={'source_id':source_id,'piece_id':piece_id,'feature_type':'park_display',
                'polygons':polygons,'display_polygons':polygons,'continues_v04':piece_id.startswith('v04:')}
        if polygons:record.update(mesh_data(polygons,piece_id))
        park_items.append(record);surfaces.append(record)
    def pairwise_overlap(records,field='display_polygons'):
        shapes=[from_records(r[field]) for r in records if r.get(field)]
        return sum(a.intersection(b).area for i,a in enumerate(shapes) for b in shapes[i+1:]
                   if a.bounds[2]>=b.bounds[0] and b.bounds[2]>=a.bounds[0]
                   and a.bounds[3]>=b.bounds[1] and b.bounds[3]>=a.bounds[1])
    source_road_overlap=pairwise_overlap(road_items,'polygons')
    source_water_overlap=pairwise_overlap(water_items,'polygons')
    overlaps={'road_overlap_removed_m2':round(sum(r['overlap_removed_m2'] for r in surfaces if r['feature_type']=='road_display'),6),
       'road_road_after_m2':round(pairwise_overlap([r for r in surfaces if r['feature_type']=='road_display']),6),
       'water_overlap_removed_m2':round(sum(r['overlap_removed_m2'] for r in surfaces if r['feature_type']=='water_display'),6),
       'water_water_after_m2':round(pairwise_overlap([r for r in surfaces if r['feature_type']=='water_display']),6),
       'water_road_m2':round(water_visible.intersection(road_visible).area,6),
       'grass_road_m2':round(green_visible.intersection(road_visible).area,6),
       'grass_water_m2':round(green_visible.intersection(water_visible).area,6)}
    result={'crs':'EPSG:6677','z_layers_m':{'park':-0.12,'water':-0.04,'grass':0.02,'roads':0.08,'terrain':-0.20},
       'geometry_role':'appearance-only partitions/height offsets; original v04 feature meshes remain immutable in 99_REFERENCE',
       'road_surfaces':len(road_items),'water_surfaces':len(water_items),'green_surfaces':len(green_items),
       'park_surfaces':len(park_items),'surfaces':surfaces,'overlap_areas_after_partition_m2':overlaps,
       'source_surface_areas_m2':{'roads':round(road_union.area,4),'water':round(water_union.area,4),'green':round(green_union.area,4),'park':round(park_union.area,4)},
       'source_pairwise_overlap_m2':{'roads':round(source_road_overlap,4),'water':round(source_water_overlap,4)},
       'display_surface_areas_m2':{'roads':round(road_visible.area,4),'water':round(water_visible.area,4),'green':round(green_visible.area,4)}}
    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:result[k] for k in ('road_surfaces','water_surfaces','green_surfaces','park_surfaces','z_layers_m','overlap_areas_after_partition_m2','source_pairwise_overlap_m2','source_surface_areas_m2','display_surface_areas_m2')},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
