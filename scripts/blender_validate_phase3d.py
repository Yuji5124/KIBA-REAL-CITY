"""Compare v05 against immutable v04 sources and validate the exported GLB."""
import bpy, hashlib, json, math, sys
from pathlib import Path
args=sys.argv[sys.argv.index('--')+1:]
if len(args)!=5:raise SystemExit('Expected v04.blend v05.blend v05.glb features.json report.json')
v04,v05,glb,features_path,report_path=map(Path,args)
features=json.loads(features_path.read_text(encoding='utf-8'))
def geometry_hash(obj):
    coords=[[round(float(c),7) for c in (obj.matrix_world @ vertex.co)] for vertex in obj.data.vertices]
    faces=[list(poly.vertices) for poly in obj.data.polygons]
    return hashlib.sha256(json.dumps([coords,faces],separators=(',',':')).encode()).hexdigest()
def source_groups():
    layouts={
      'buildings':(['01_BUILDINGS'],'citygml_id',None),
      'roads_paths':(['02_ROADS','08_PARK_PATHS','99_REFERENCE'],'osm_id',None),
      'park_boundary':(['03_PARK','99_REFERENCE'],'osm_id',None),
      'green':(['07_GRASS','99_REFERENCE'],'source_id','green'),
      'water':(['09_WATER','99_REFERENCE'],'source_id','water'),
      'bridges':(['06_BRIDGES','99_REFERENCE'],'source_id','bridge'),
      'trees':(['04_TREES','99_REFERENCE'],'source_id','tree'),
    }
    out={}
    for group,(collections,key,feature_type) in layouts.items():
        found={}
        for name in collections:
            col=bpy.data.collections.get(name)
            if not col:continue
            for obj in col.objects:
                value=obj.get(key)
                if value is None:continue
                if feature_type and obj.get('feature_type')!=feature_type:continue
                if name=='99_REFERENCE':
                    if obj.get('phase3d_role')!='immutable_v04_geodata_source' and group!='trees':continue
                    if feature_type is None and obj.get('feature_type') is not None:continue
                if obj.get('phase3d_role')=='display_surface':continue
                identity=str(value)
                if identity in found:raise ValueError(f'Duplicate source {group} identity: {identity}')
                found[identity]=obj
        out[group]=found
    return out
def bounds(obj):
    pts=[obj.matrix_world@v.co for v in obj.data.vertices]
    return [min(p[i] for p in pts) for i in range(3)]+[max(p[i] for p in pts) for i in range(3)]
def mesh_hashes(groups):return {g:{k:geometry_hash(o) for k,o in items.items()} for g,items in groups.items()}
bpy.ops.wm.open_mainfile(filepath=str(v04));baseline=source_groups();baseline_hash=mesh_hashes(baseline)
baseline_tree_locations={k:[round(float(c),8) for c in o.location] for k,o in baseline['trees'].items()}
baseline_building_bounds={k:bounds(o) for k,o in baseline['buildings'].items()}
bpy.ops.wm.open_mainfile(filepath=str(v05));current=source_groups();current_hash=mesh_hashes(current)
ids_equal={g:set(baseline[g])==set(current[g]) for g in baseline}
geom_equal={g:ids_equal[g] and all(baseline_hash[g][k]==current_hash[g][k] for k in baseline[g]) for g in baseline}
tree_positions_equal=ids_equal['trees'] and all(
    baseline_tree_locations[k]==
    [round(float(c),8) for c in current['trees'][k].location] for k in baseline['trees'])
counts={g:len(v) for g,v in current.items()}
buildings=bpy.data.collections['01_BUILDINGS'].objects
city_ids=[str(o.get('citygml_id')) for o in buildings if o.get('citygml_id')]
extension_ids=[str(o.get('parent_citygml_id')) for o in buildings if o.get('parent_citygml_id')]
unique_city_ids=set(city_ids)
museum_id=features['museum']['citygml_id']
museum_obj=next((o for o in buildings if o.get('citygml_id')==museum_id),None)
museum_bounds=bounds(museum_obj) if museum_obj else None
all_finite=all(math.isfinite(float(c)) for obj in bpy.data.objects if obj.type=='MESH'
               for vertex in obj.data.vertices for c in vertex.co)
collections_expected=all(bpy.data.collections.get(n) for n in (
 '01_BUILDINGS','02_ROADS','03_PARK','04_TREES','05_TERRAIN','06_BRIDGES',
 '07_GRASS','08_PARK_PATHS','09_WATER','99_REFERENCE'))
tree_visuals=[o for o in bpy.data.collections['04_TREES'].objects if o.get('feature_type')=='tree_visual']
display_surfaces=[o for o in bpy.data.objects if o.get('phase3d_role')=='display_surface']
bridge_extensions=[o for o in bpy.data.collections['06_BRIDGES'].objects if o.get('feature_type')=='bridge_extension']
v05_bounds=[float(x) for x in features['bounds_local_m']]
in_target=bool(museum_bounds) and museum_bounds[0]>=v05_bounds[0]-1e-5 and museum_bounds[1]>=v05_bounds[1]-1e-5 and museum_bounds[3]<=v05_bounds[2]+1e-5 and museum_bounds[4]<=v05_bounds[3]+1e-5
old_ids=set(baseline['buildings'])
new_city_sequence=[identity for identity in city_ids if identity not in old_ids]
new_ids=set(new_city_sequence)
source_counts={'old_buildings':len(baseline['buildings']),'old_roads_paths':len(baseline['roads_paths']),
 'old_park_features':len(baseline['park_boundary']),'old_green':len(baseline['green']),
 'old_water':len(baseline['water']),'old_bridges':len(baseline['bridges']),'old_trees':len(baseline['trees'])}
source_hashes_v04={g:{k:v for k,v in hs.items()} for g,hs in baseline_hash.items()}
# Keep detailed original geometry signatures in the report for an auditable per-ID comparison.
for obj in bpy.data.objects:
    if obj.type=='MESH' and not all(math.isfinite(float(c)) for v in obj.data.vertices for c in v.co):
        raise SystemExit(f'Non-finite coordinates in {obj.name}')
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(glb))
glb_meshes=[o for o in bpy.data.objects if o.type=='MESH']
glb_city_ids={str(o.get('citygml_id')) for o in glb_meshes if o.get('citygml_id')}
glb_tree_ids={str(o.get('source_id')) for o in glb_meshes if o.get('feature_type')=='tree_visual'}
glb_bounds={str(o.get('citygml_id')):bounds(o) for o in glb_meshes if o.get('citygml_id')}
glb_existing_max_error=0.0
for identity in old_ids:
    if identity not in glb_bounds:continue
    before=baseline_building_bounds[identity];after=glb_bounds[identity]
    glb_existing_max_error=max(glb_existing_max_error,max(abs(a-b) for a,b in zip(before,after)))
glb_faces_valid=bool(glb_meshes) and all(len(o.data.polygons)>0 for o in glb_meshes)
report={
 'source_v04_sha256':{'blend':hashlib.sha256(v04.read_bytes()).hexdigest(),'glb':hashlib.sha256((v04.parent/'KIBA_REAL_CITY_v04.glb').read_bytes()).hexdigest()},
 'v05_sizes_bytes':{'blend':v05.stat().st_size,'glb':glb.stat().st_size},
 'extent':{'bounds_local_m':v05_bounds,'width_m':features['bounds_local_m'][2]-features['bounds_local_m'][0],
           'height_m':features['bounds_local_m'][3]-features['bounds_local_m'][1],
           'bounds_projected_epsg6677_m':features['bounds_projected_epsg6677_m'],
           'bounds_wgs84_lonlat':features['bounds_wgs84_lonlat'],'mesh_codes_1km':features['mesh_codes_1km']},
 'source_counts_v04':source_counts,'source_geometry_ids_equal_v04':ids_equal,
 'source_geometry_hashes_equal_v04':geom_equal,'tree_positions_equal_v04':tree_positions_equal,
 'building_citygml_feature_count':len(unique_city_ids),'new_building_citygml_ids':len(new_ids),
 'building_continuation_piece_count':len(extension_ids),'duplicate_building_ids':len(city_ids)!=len(unique_city_ids),
 'duplicate_new_citygml_ids':len(new_city_sequence)!=len(new_ids),
 'extensions':features['counts'],
 'museum':{'citygml_id':museum_id,'source_file':features['museum']['source_file'],
   'lod1_height_m':features['museum']['citygml_lod1_height_m'],'measured_height_m':features['museum']['citygml_measuredHeight_m'],
   'lod1_minus_measured_height_m':features['museum']['lod1_minus_measured_height_m'],
   'footprint_iou_osm':features['museum']['osm_citygml_footprint_validation']['intersection_over_union'],
   'model_bounds_local_m':museum_bounds,'entire_model_inside_extent':in_target,
   'model_geometry_status':'real PLATEAU LOD1; no LOD2 feature in target mesh'},
 'extensions':features['counts'],'tree_visual_count':len(tree_visuals),
 'display_surface_object_count':len(display_surfaces),'bridge_extension_object_count':len(bridge_extensions),
 'display_overlap_areas_m2':json.loads((features_path.parent/'phase3d_display_surfaces.json').read_text(encoding='utf-8'))['overlap_areas_after_partition_m2'],
 'all_coordinates_finite':all_finite,'expected_collections_present':bool(collections_expected),
 'glb_reimported':bool(glb_meshes),'glb_mesh_count':len(glb_meshes),'glb_citygml_building_id_count':len(glb_city_ids),
 'glb_has_all_citygml_buildings':glb_city_ids==unique_city_ids,'glb_tree_count':len(glb_tree_ids),
 'glb_tree_source_ids_match':glb_tree_ids=={str(o.get('source_id')) for o in tree_visuals},
 'glb_all_meshes_have_faces':glb_faces_valid,'glb_existing_building_bounds_max_error_m':round(glb_existing_max_error,8),
 'v04_per_feature_geometry_hashes':source_hashes_v04,
 'v05_per_feature_geometry_hashes':current_hash}
report_path.parent.mkdir(parents=True,exist_ok=True)
report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k not in ('v04_per_feature_geometry_hashes','v05_per_feature_geometry_hashes')},ensure_ascii=False,indent=2))
checks=[all(ids_equal.values()),all(geom_equal.values()),tree_positions_equal,source_counts=={
 'old_buildings':233,'old_roads_paths':236,'old_park_features':1,'old_green':17,'old_water':14,'old_bridges':2,'old_trees':33},
 len(unique_city_ids)==583,len(new_ids)==350,len(extension_ids)==26,
 len(city_ids)==len(unique_city_ids),len(new_city_sequence)==len(new_ids),in_target,all_finite,collections_expected,
 bool(glb_meshes),len(glb_city_ids)==583,glb_city_ids==unique_city_ids,
 glb_tree_ids=={str(o.get('source_id')) for o in tree_visuals},glb_faces_valid,glb_existing_max_error<0.02]
if not all(checks):raise SystemExit('Phase 3D validation failed. See phase3d_report.json and Blender output.')
