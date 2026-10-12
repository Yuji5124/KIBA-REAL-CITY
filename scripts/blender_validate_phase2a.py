import bpy, json, math, sys, hashlib
from pathlib import Path
from mathutils import Vector

args=sys.argv[sys.argv.index('--')+1:]
if len(args)!=4: raise SystemExit('Expected v01_blend v02_blend v02_glb result_json')
v01,v02,glb,out=map(Path,args)

def buildings():
    col=bpy.data.collections.get('01_BUILDINGS')
    if col is None: return {}
    result={}
    for obj in col.objects:
        if obj.type!='MESH' or not obj.get('citygml_id'): continue
        bid=str(obj['citygml_id'])
        points=[obj.matrix_world @ v.co for v in obj.data.vertices]
        if not points: continue
        coords=[tuple(round(float(c),6) for c in p) for p in points]
        faces=[tuple(int(i) for i in poly.vertices) for poly in obj.data.polygons]
        signature=hashlib.sha256(json.dumps([coords,faces],separators=(',',':')).encode()).hexdigest()
        bounds=[min(p[i] for p in points) for i in range(3)]+[max(p[i] for p in points) for i in range(3)]
        result[bid]={'object_name':obj.name,'hash':signature,'bounds':bounds,'height':float(obj.get('height_m',0)),'base_z':float(obj.get('base_z_m',0))}
    return result

bpy.ops.wm.open_mainfile(filepath=str(v01)); source=buildings()
bpy.ops.wm.open_mainfile(filepath=str(v02)); candidate=buildings()
same_ids=source.keys()==candidate.keys()
changed=[bid for bid in source.keys() & candidate.keys() if source[bid]['hash']!=candidate[bid]['hash']]
count_ok=len(source)==233 and len(candidate)==233 and same_ids
hashes_ok=count_ok and not changed
road_col=bpy.data.collections.get('02_ROADS'); park_col=bpy.data.collections.get('03_PARK')
road_objs=list(road_col.objects) if road_col else []
park_objs=list(park_col.objects) if park_col else []
all_finite=all(math.isfinite(float(c)) for obj in road_objs+park_objs if obj.type=='MESH' for vert in obj.data.vertices for c in vert.co)
road_ids={str(o.get('osm_id')) for o in road_objs}; park_ids={str(o.get('osm_id')) for o in park_objs}
v02_metadata={'phase2a_source':str(bpy.context.scene.get('phase2a_source','')),'phase2a_license':str(bpy.context.scene.get('phase2a_license','')),'phase2a_attribution':str(bpy.context.scene.get('phase2a_attribution',''))}
surfaces=road_objs+park_objs
all_surface_normals_up=all(poly.normal.z>0.999 for obj in surfaces if obj.type=='MESH' for poly in obj.data.polygons)

# Import the delivered GLB into a clean scene and compare all building IDs, bounds,
# OSM feature IDs and park relation against the v02 BLEND.
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(glb))
glb_mesh=[o for o in bpy.data.objects if o.type=='MESH']
glb_buildings={str(o.get('citygml_id')):o for o in glb_mesh if o.get('citygml_id')}
expected=set(source)
glb_ids_ok=set(glb_buildings)==expected
max_bounds_error=0.0
for bid in expected & glb_buildings.keys():
    glb_obj=glb_buildings[bid]
    pts=[glb_obj.matrix_world @ v.co for v in glb_obj.data.vertices]
    actual=[min(p[i] for p in pts) for i in range(3)]+[max(p[i] for p in pts) for i in range(3)]
    max_bounds_error=max(max_bounds_error,max(abs(a-b) for a,b in zip(actual,candidate[bid]['bounds'])))
glb_osm_road_ids={str(o.get('osm_id')) for o in glb_mesh if o.get('osm_id','').startswith('way/')}
glb_park_ids={str(o.get('osm_id')) for o in glb_mesh if o.get('osm_id','').startswith('relation/')}
expected_road_ids=road_ids
result={
 'phase1_v01_exists':v01.is_file(),'phase2a_v02_exists':v02.is_file(),'v02_glb_exists':glb.is_file(),
 'phase1_building_count':len(source),'phase2a_building_count':len(candidate),'same_233_building_ids':bool(same_ids),
 'building_geometry_hashes_unchanged':bool(hashes_ok),'changed_building_ids':changed,
 'v02_road_object_count':len(road_objs),'v02_park_object_count':len(park_objs),
 'real_osm_road_ids_preserved_in_blend':len(road_ids)==len(expected_road_ids) and len(road_ids)>0,
 'park_relation_preserved_in_blend':'relation/14273608' in park_ids,
 'roads_and_park_have_finite_coordinates':all_finite,
 'roads_and_park_surface_normals_up':all_surface_normals_up,
 'glb_reimports':bool(glb_mesh),'all_building_ids_present_in_glb':bool(glb_ids_ok),
 'max_building_bounds_error_blend_vs_glb_m':round(max_bounds_error,8),
 'building_bounds_preserved_to_2cm_in_glb':max_bounds_error<=0.02,
 'all_osm_road_ids_present_in_glb':road_ids.issubset(glb_osm_road_ids),
 'park_relation_present_in_glb':'relation/14273608' in glb_park_ids,
 'glb_mesh_object_count':len(glb_mesh),
 'scene_provenance':v02_metadata,
}
out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('Phase 2A validation:',json.dumps(result,ensure_ascii=False))
checks=[v for k,v in result.items() if isinstance(v,bool)]
if not all(checks): raise SystemExit('One or more Phase 2A checks failed.')
