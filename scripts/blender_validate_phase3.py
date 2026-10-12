"""Validate v04 geometry against the immutable v03 source and its GLB."""
import bpy, hashlib, json, math, sys
from pathlib import Path

args=sys.argv[sys.argv.index('--')+1:]
if len(args)!=4: raise SystemExit('Expected v03_blend v04_blend v04_glb report_json')
v03,v04,glb,report_path=map(Path,args)

def geometry_hash(obj):
    coords=[[round(float(c),7) for c in (obj.matrix_world @ vertex.co)] for vertex in obj.data.vertices]
    faces=[list(face.vertices) for face in obj.data.polygons]
    return hashlib.sha256(json.dumps([coords,faces],separators=(',',':')).encode()).hexdigest()

def collect(collection_names,attribute):
    found={}
    for name in collection_names:
        col=bpy.data.collections.get(name)
        for obj in (col.objects if col else ()):
            value=obj.get(attribute)
            if value is not None: found[str(value)]=obj
    return found

def mapped_groups():
    return {
      'buildings':collect(['01_BUILDINGS'],'citygml_id'),
      'roads_paths':collect(['02_ROADS','08_PARK_PATHS'],'osm_id'),
      'park_boundary':collect(['03_PARK'],'osm_id'),
      'green':collect(['07_GRASS'],'source_id'),
      'water':collect(['09_WATER'],'source_id'),
      'bridges':collect(['06_BRIDGES'],'source_id'),
      'trees':collect(['04_TREES','99_REFERENCE'],'source_id'),
    }

bpy.ops.wm.open_mainfile(filepath=str(v03))
base=mapped_groups()
base_hash={kind:{key:geometry_hash(obj) for key,obj in group.items()} for kind,group in base.items()}
base_locations={key:[round(float(c),8) for c in obj.location] for key,obj in base['trees'].items()}
bpy.ops.wm.open_mainfile(filepath=str(v04))
current=mapped_groups()
current_hash={kind:{key:geometry_hash(obj) for key,obj in group.items()} for kind,group in current.items()}
ids_equal={kind:set(base[kind])==set(current[kind]) for kind in base}
geometry_equal={kind:ids_equal[kind] and all(base_hash[kind][key]==current_hash[kind][key]
                    for key in base[kind]) for kind in base}
tree_locations={key:[round(float(c),8) for c in obj.location] for key,obj in current['trees'].items()}
tree_locations_equal=base_locations==tree_locations
expected_counts={'buildings':233,'roads_paths':236,'park_boundary':1,'green':17,'water':14,'bridges':2,'trees':33}
counts={kind:len(group) for kind,group in current.items()}
tree_visuals=[o for o in bpy.data.collections['04_TREES'].objects if o.get('feature_type')=='tree_visual']
tree_visual_ids={str(o.get('source_id')) for o in tree_visuals}
tree_styles={style:sum(1 for o in tree_visuals if o.get('visual_form')==style)
             for style in ('round_broadleaf','columnar','spreading')}
def bounds(obj):
    pts=[obj.matrix_world @ vertex.co for vertex in obj.data.vertices]
    return [min(p[i] for p in pts) for i in range(3)]+[max(p[i] for p in pts) for i in range(3)]
source_building_bounds={key:bounds(obj) for key,obj in current['buildings'].items()}
source_building_ids=set(current['buildings'])
source_tree_ids=set(current['trees'])
collections_expected=all(bpy.data.collections.get(name) is not None for name in
 ('01_BUILDINGS','02_ROADS','03_PARK','04_TREES','05_TERRAIN','06_BRIDGES','07_GRASS',
  '08_PARK_PATHS','09_WATER','99_REFERENCE'))
finite=all(math.isfinite(float(c)) for obj in bpy.data.objects if obj.type=='MESH'
           for vertex in obj.data.vertices for c in vertex.co)
source_tree_hidden=all(obj.hide_render and obj.hide_get() for obj in current['trees'].values())
pbr_materials=all(bpy.data.materials.get(name) and bpy.data.materials[name].use_nodes
                 for name in ('Phase 3 | soft warm mineral walls','Phase 3 | asphalt',
                              'Phase 3 | mapped green areas','Phase 3 | calm blue green water'))
blend_reopens=v04.is_file()

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(glb))
glb_meshes=[o for o in bpy.data.objects if o.type=='MESH']
glb_buildings=collect(['Scene'],'citygml_id')
# glTF imports generally group objects outside the named source collections.
glb_buildings={str(o.get('citygml_id')):o for o in glb_meshes if o.get('citygml_id')}
glb_tree_visuals=[o for o in glb_meshes if o.get('feature_type')=='tree_visual']
glb_tree_ids={str(o.get('source_id')) for o in glb_tree_visuals}
building_bounds_error=0.0
for key in source_building_ids:
    glb_obj=next((o for o in glb_buildings.values() if str(o.get('citygml_id'))==key),None)
    if glb_obj is None: continue
    a,b=source_building_bounds[key],bounds(glb_obj)
    building_bounds_error=max(building_bounds_error,max(abs(x-y) for x,y in zip(a,b)))
all_glb_meshes_valid=bool(glb_meshes) and all(len(o.data.polygons)>0 for o in glb_meshes)
report={
 'source':'Phase 2B v03 immutable source',
 'source_v03_hashes':{
   'blend':hashlib.sha256(v03.read_bytes()).hexdigest(),
   'glb':hashlib.sha256((v03.parent/'KIBA_REAL_CITY_v03.glb').read_bytes()).hexdigest()},
 'v04_sizes_bytes':{'blend':v04.stat().st_size if v04.exists() else 0,
                    'glb':glb.stat().st_size if glb.exists() else 0},
 'v04_objects_by_source_group':counts,'expected_counts':expected_counts,
 'source_ids_unchanged_by_group':ids_equal,'source_geometry_unchanged_by_group':geometry_equal,
 'tree_source_positions_unchanged':tree_locations_equal,
 'tree_display_count':len(tree_visuals),'tree_visual_styles':tree_styles,
 'tree_display_ids_match_source':tree_visual_ids==source_tree_ids,
 'tree_source_proxies_retained_hidden':source_tree_hidden,
 'all_expected_collections_present':collections_expected,'all_mesh_vertices_finite':finite,
 'pbr_materials_present':pbr_materials,'blend_file_present':blend_reopens,
 'glb_reimports':bool(glb_meshes),'glb_mesh_count':len(glb_meshes),
 'glb_building_count':len(glb_buildings),'glb_has_all_buildings':len(glb_buildings)==233,
 'glb_tree_visual_count':len(glb_tree_visuals),'glb_has_all_tree_visual_ids':glb_tree_ids==source_tree_ids,
 'glb_meshes_have_faces':all_glb_meshes_valid,
 'glb_building_bounds_max_error_m':round(building_bounds_error,8)}
report_path.parent.mkdir(parents=True,exist_ok=True)
report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report,ensure_ascii=False))
checks=list(ids_equal.values())+list(geometry_equal.values())+[
 tree_locations_equal,counts==expected_counts,len(tree_visuals)==33,
 all(v>0 for v in tree_styles.values()),report['tree_display_ids_match_source'],
 source_tree_hidden,collections_expected,finite,pbr_materials,blend_reopens,
 report['glb_reimports'],report['glb_has_all_buildings'],report['glb_tree_visual_count']==33,
 report['glb_has_all_tree_visual_ids'],all_glb_meshes_valid,building_bounds_error<0.02]
if not all(checks): raise SystemExit('Phase 3 validation failed; see report.')
