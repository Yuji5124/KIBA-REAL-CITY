"""Add real OSM roads/park to a copy of v01 and export v02; never writes v01."""
import bpy, json, sys
from pathlib import Path

args=sys.argv[sys.argv.index('--')+1:]
if len(args)!=3: raise SystemExit('Expected features_json v01_blend output_dir')
features_path, source_blend, output_dir=map(Path,args)
features=json.loads(features_path.read_text(encoding='utf-8'))
output_dir.mkdir(parents=True,exist_ok=True)
blend_path=output_dir/'KIBA_REAL_CITY_v02.blend'
glb_path=output_dir/'KIBA_REAL_CITY_v02.glb'
if blend_path.exists() or glb_path.exists():
    raise SystemExit('v02 output already exists; move it aside before rebuilding. v01 is never overwritten.')
bpy.ops.wm.open_mainfile(filepath=str(source_blend))
scene=bpy.context.scene
root=bpy.data.collections.get('KIBA_REAL_CITY')
if root is None: raise SystemExit('KIBA_REAL_CITY collection missing in Phase 1 BLEND.')
for name in ('02_ROADS','03_PARK'):
    col=bpy.data.collections.get(name)
    if col is None:
        col=bpy.data.collections.new(name); root.children.link(col)
    if len(col.objects): raise SystemExit(f'{name} is not empty; refusing duplicate Phase 2A geometry.')

def material(name,color):
    m=bpy.data.materials.get(name)
    if m is None:
        m=bpy.data.materials.new(name); m.diffuse_color=(*color,1); m.use_nodes=True
        m.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value=(*color,1)
    return m
road_mat=material('Road | OSM mapped corridor, width tagged or estimated',(0.20,0.22,0.23))
park_mat=material('Park | OSM Kiba Park boundary',(0.12,0.32,0.14))

def polygon_mesh(name, data, z, mat):
    verts=[(float(x),float(y),float(z)) for x,y in data['mesh_vertices_xy_m']]
    faces=[tuple(int(i) for i in f) for f in data['mesh_faces']]
    if not faces: raise ValueError(f'No triangulated faces in {name}')
    mesh=bpy.data.meshes.new(name+'_mesh'); mesh.from_pydata(verts,[],faces); mesh.materials.append(mat); mesh.update()
    return mesh

roads_col=bpy.data.collections['02_ROADS']
for road in features['roads']:
    mesh=polygon_mesh(road['osm_id'].replace('/','_'),road,road['z_m'],road_mat)
    obj=bpy.data.objects.new(f"road_{road['osm_id'].replace('/','_')}",mesh); roads_col.objects.link(obj)
    obj['osm_id']=road['osm_id']; obj['highway']=road['highway']; obj['width_m']=road['width_m'] or 0.0
    obj['width_source']=road['width_source']; obj['geometry_type']=road['geometry_type']; obj['source']='OpenStreetMap live API map extract'
    obj['license']='ODbL 1.0'; obj['attribution']='OpenStreetMap and contributors'
    obj['tags_json']=json.dumps(road['tags'],ensure_ascii=False,sort_keys=True)
    if road.get('name'): obj['name']=road['name']
park=features['park']; mesh=polygon_mesh('kiba_park_relation_14273608',park,park['z_m'],park_mat)
obj=bpy.data.objects.new('park_osm_relation_14273608_Kiba_Park',mesh); bpy.data.collections['03_PARK'].objects.link(obj)
obj['osm_id']=park['osm_id']; obj['name']='木場公園'; obj['source']='OpenStreetMap live API map extract'
obj['license']='ODbL 1.0'; obj['attribution']='OpenStreetMap and contributors'
obj['tags_json']=json.dumps(park['tags'],ensure_ascii=False,sort_keys=True); obj['z_status']=park['z_status']

scene['phase2a_source']='OpenStreetMap API current extract; ODbL 1.0; retrieved 2026-10-12 UTC'
scene['phase2a_license']='Open Data Commons Open Database License (ODbL) 1.0'
scene['phase2a_license_url']='https://opendatacommons.org/licenses/odbl/1-0/'
scene['phase2a_attribution']='OpenStreetMap and contributors'
scene['phase2a_attribution_url']='https://www.openstreetmap.org/copyright'
scene['phase2a_local_crs']=features['crs']; scene['phase2a_origin_projected_m']=json.dumps(features['origin_projected_m'])
scene['phase2a_road_count']=len(features['roads']); scene['phase2a_park_relation']='relation/14273608'
bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(filepath=str(glb_path),export_format='GLB',use_selection=False,export_yup=True,export_extras=True)
print(json.dumps({'blend':str(blend_path),'glb':str(glb_path),'roads':len(features['roads']),'park_polygons':len(park['polygons'])},ensure_ascii=False))
