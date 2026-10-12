"""Compare v03 to immutable v01/v02 and test its exported GLB."""
import bpy, json, math, sys, hashlib
from pathlib import Path
from mathutils import Vector

args=sys.argv[sys.argv.index('--')+1:]
if len(args)!=5: raise SystemExit('Expected v01_blend v02_blend v03_blend v03_glb report_json')
v01,v02,v03,glb,out=map(Path,args)

def geom_hash(obj):
    pts=[obj.matrix_world @ v.co for v in obj.data.vertices]
    coords=[[round(float(c),6) for c in p] for p in pts]
    faces=[list(poly.vertices) for poly in obj.data.polygons]
    return hashlib.sha256(json.dumps([coords,faces],separators=(',',':')).encode()).hexdigest()

def by_id(collection_names,attribute):
    result={}
    for name in collection_names:
        col=bpy.data.collections.get(name)
        for obj in (col.objects if col else []):
            value=obj.get(attribute)
            if value is not None: result[str(value)]=obj
    return result

bpy.ops.wm.open_mainfile(filepath=str(v01)); b01=by_id(['01_BUILDINGS'],'citygml_id')
hash01={k:geom_hash(o) for k,o in b01.items()}; ids01=set(b01)
bpy.ops.wm.open_mainfile(filepath=str(v02)); b02=by_id(['01_BUILDINGS'],'citygml_id')
hash02={k:geom_hash(o) for k,o in b02.items()}; ids02=set(b02)
roads02=by_id(['02_ROADS'],'osm_id'); hash_roads02={k:geom_hash(o) for k,o in roads02.items()}
park02=by_id(['03_PARK'],'osm_id'); hash_park02={k:geom_hash(o) for k,o in park02.items()}
bpy.ops.wm.open_mainfile(filepath=str(v03)); b03=by_id(['01_BUILDINGS'],'citygml_id')
hash03={k:geom_hash(o) for k,o in b03.items()}; ids03=set(b03)
roads03=by_id(['02_ROADS','08_PARK_PATHS'],'osm_id'); hash_roads03={k:geom_hash(o) for k,o in roads03.items()}
park03=by_id(['03_PARK'],'osm_id'); hash_park03={k:geom_hash(o) for k,o in park03.items()}
extra={'tree':by_id(['04_TREES'],'source_id'),'green':by_id(['07_GRASS'],'source_id'),
       'water':by_id(['09_WATER'],'source_id'),'bridge':by_id(['06_BRIDGES'],'source_id')}
building_unchanged=(ids01==ids02==ids03 and len(ids03)==233 and
                     all(hash01[k]==hash02[k]==hash03[k] for k in ids01))
road_ids_unchanged=(set(hash_roads02)==set(hash_roads03) and len(hash_roads02)==236 and len(hash_roads03)==236 and
                    all(hash_roads02[k]==hash_roads03[k] for k in hash_roads02))
park_unchanged=(set(hash_park02)==set(hash_park03) and len(hash_park03)==1 and
                all(hash_park02[k]==hash_park03[k] for k in hash_park02))
all_meshes=[o for o in bpy.data.objects if o.type=='MESH']
finite=all(math.isfinite(float(c)) for o in all_meshes for v in o.data.vertices for c in v.co)
up_normals=all(p.normal.z>0.99 for o in all_meshes if o.name.startswith(('green_','water_','bridge_')) for p in o.data.polygons)
source_props=all(bool(o.get('source')) and bool(o.get('source_id')) and o.get('crs')=='EPSG:6677'
                 for group in extra.values() for o in group.values())
all_expected_collections=all(bpy.data.collections.get(n) is not None for n in
 ('01_BUILDINGS','02_ROADS','03_PARK','04_TREES','05_TERRAIN','06_BRIDGES','07_GRASS','08_PARK_PATHS','09_WATER','99_REFERENCE'))
v03_building_bounds={k:[min((o.matrix_world@v.co)[i] for v in o.data.vertices) for i in range(3)]+
                          [max((o.matrix_world@v.co)[i] for v in o.data.vertices) for i in range(3)]
                     for k,o in b03.items()}
report={'phase1_building_count':len(b01),'phase2a_building_count':len(b02),'phase2b_building_count':len(b03),
        'building_ids_vertices_faces_and_dimensions_unchanged_v01_v02_v03':building_unchanged,
        'phase2a_road_path_count_v02':len(roads02),'phase2b_road_and_path_count':len(roads03),
        'road_path_ids_and_geometry_unchanged':road_ids_unchanged,
        'park_boundary_id_and_geometry_unchanged':park_unchanged,
        'trees_added':len(extra['tree']),'green_areas_added':len(extra['green']),
        'water_features_added':len(extra['water']),'bridge_footprints_added':len(extra['bridge']),
        'all_expected_collections_present':all_expected_collections,'all_mesh_coordinates_finite':finite,
        'added_surface_normals_up':up_normals,'all_added_features_have_source_id_and_crs':source_props,
        'v03_blend_exists':v03.is_file(),'v03_glb_exists':glb.is_file(),
        'v03_sizes_bytes':{'blend':v03.stat().st_size if v03.exists() else 0,'glb':glb.stat().st_size if glb.exists() else 0}}

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(glb))
glb_mesh=[o for o in bpy.data.objects if o.type=='MESH']
glb_buildings={str(o.get('citygml_id')):o for o in glb_mesh if o.get('citygml_id')}
glb_ids={k:{str(o.get('source_id')) for o in glb_mesh if o.get('feature_type')==k}
         for k in ('tree','green','water','bridge')}
expected_ids={k:set(v) for k,v in extra.items()}
glb_group_ok={k:expected_ids[k].issubset(glb_ids[k]) for k in expected_ids}
bounds_error=0.0
for bid,obj in glb_buildings.items():
    if bid not in b03: continue
    pts=[obj.matrix_world @ v.co for v in obj.data.vertices]
    a=[min(p[i] for p in pts) for i in range(3)]+[max(p[i] for p in pts) for i in range(3)]
    b=v03_building_bounds[bid]
    bounds_error=max(bounds_error,max(abs(x-y) for x,y in zip(a,b)))
report.update({'glb_reimports':bool(glb_mesh),'glb_mesh_count':len(glb_mesh),
               'glb_has_all_233_buildings':set(glb_buildings)==set(b03),
               'glb_building_bounds_max_error_m':round(bounds_error,8),
               'glb_added_source_ids_present_by_group':glb_group_ok,
               'glb_meshes_have_faces':all(len(o.data.polygons)>0 for o in glb_mesh)})
out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('Phase 2B validation:',json.dumps(report,ensure_ascii=False))
checks=[v for v in report.values() if isinstance(v,bool)]+list(glb_group_ok.values())
if not all(checks) or bounds_error>0.02: raise SystemExit('One or more Phase 2B validation checks failed.')
