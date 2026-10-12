"""Add Phase 2B OSM features to a Phase 2A scene, leaving all source meshes intact."""
import bpy, json, math, sys
from pathlib import Path

args=sys.argv[sys.argv.index('--')+1:]
if len(args)!=4: raise SystemExit('Expected features_json v02_blend output_dir geo_reference_json')
features_path,source_blend,output_dir,geo_path=map(Path,args)
features=json.loads(features_path.read_text(encoding='utf-8'))
output_dir.mkdir(parents=True,exist_ok=True)
blend_path=output_dir/'KIBA_REAL_CITY_v03.blend'; glb_path=output_dir/'KIBA_REAL_CITY_v03.glb'
if blend_path.exists() or glb_path.exists() or geo_path.exists():
    raise SystemExit('A v03 output already exists; refusing to overwrite any prior output.')
bpy.ops.wm.open_mainfile(filepath=str(source_blend))
scene=bpy.context.scene; root=bpy.data.collections.get('KIBA_REAL_CITY')
if root is None: raise SystemExit('KIBA_REAL_CITY root collection missing.')

names=('01_BUILDINGS','02_ROADS','03_PARK','04_TREES','05_TERRAIN','06_BRIDGES','07_GRASS','08_PARK_PATHS','09_WATER','99_REFERENCE')
for name in names:
    if bpy.data.collections.get(name) is None:
        col=bpy.data.collections.new(name); root.children.link(col)
    elif bpy.data.collections[name].users==0:
        root.children.link(bpy.data.collections[name])

def mat(name,color):
    m=bpy.data.materials.get(name)
    if m is None:
        m=bpy.data.materials.new(name); m.diffuse_color=(*color,1); m.use_nodes=True
        bs=m.node_tree.nodes.get('Principled BSDF')
        if bs: bs.inputs['Base Color'].default_value=(*color,1)
    return m

materials={
 'tree_trunk':mat('Phase 2B | OSM tree trunk',(0.20,0.105,0.045)),
 'tree_crown':mat('Phase 2B | generic tree crown',(0.10,0.34,0.13)),
 'grass':mat('Phase 2B | mapped grass',(0.25,0.48,0.20)),
 'forest':mat('Phase 2B | mapped forest and wood',(0.13,0.32,0.16)),
 'water':mat('Phase 2B | mapped water',(0.08,0.32,0.50)),
 'bridge':mat('Phase 2B | OSM bridge footprint',(0.47,0.43,0.35)),
}

def create_polygon_obj(rec,col_name,kind,material,z=0.0):
    verts=[(float(x),float(y),float(z)) for x,y in rec['mesh_vertices_xy_m']]
    faces=[tuple(int(i) for i in face) for face in rec['mesh_faces']]
    if not faces: raise ValueError(f"No triangulated faces for {rec['osm_id']}")
    mesh=bpy.data.meshes.new(rec['osm_id'].replace('/','_')+'_mesh'); mesh.from_pydata(verts,[],faces); mesh.materials.append(material); mesh.update()
    obj=bpy.data.objects.new(f"{kind}_{rec['osm_id'].replace('/','_')}",mesh); bpy.data.collections[col_name].objects.link(obj)
    obj['source']='OpenStreetMap API current extract'; obj['source_id']=rec['osm_id']; obj['osm_id']=rec['osm_id']
    obj['feature_type']=kind
    obj['license']='ODbL 1.0'; obj['attribution']='OpenStreetMap and contributors'; obj['attribution_url']='https://www.openstreetmap.org/copyright'
    obj['tags_json']=json.dumps(rec['tags'],ensure_ascii=False,sort_keys=True)
    obj['geometry_source']=rec['geometry_source']; obj['crs']='EPSG:6677'; obj['local_origin_projected_m']=json.dumps(features['origin_projected_m'])
    return obj

# Reclassify existing Phase 2A walking corridors that lie within the real park
# boundary into a dedicated collection. No mesh, transform, object ID or tag changes.
path_ids=set(features['park_path_osm_ids_reclassified_from_phase2a'])
roads=bpy.data.collections['02_ROADS']; paths=bpy.data.collections['08_PARK_PATHS']
moved=set()
for obj in list(roads.objects):
    oid=str(obj.get('osm_id',''))
    if oid in path_ids:
        roads.objects.unlink(obj); paths.objects.link(obj); moved.add(oid)
if moved != path_ids:
    raise SystemExit(f'Phase 2A road/path IDs do not match for collection transfer: expected {len(path_ids)}, found {len(moved)}')

for tree in features['trees']:
    h=float(tree['height_display_m']); crown=float(tree['crown_diameter_display_m']); radius=crown/2
    verts=[]; faces=[]; material_indices=[]
    def add_cone(z0,z1,r0,r1,material_index,segments=8):
        base=len(verts)
        for z,r in ((z0,r0),(z1,r1)):
            for i in range(segments):
                a=2*math.pi*i/segments; verts.append((r*math.cos(a),r*math.sin(a),z))
        for i in range(segments):
            j=(i+1)%segments; faces.append((base+i,base+j,base+segments+j,base+segments+i)); material_indices.append(material_index)
        faces.append(tuple(base+i for i in reversed(range(segments)))); material_indices.append(material_index)
        faces.append(tuple(base+segments+i for i in range(segments))); material_indices.append(material_index)
    add_cone(0.0,h*0.55,max(0.10,radius*0.10),max(0.06,radius*0.06),0)
    add_cone(h*0.25,h*0.82,radius*0.78,radius*0.08,1)
    mesh=bpy.data.meshes.new(tree['osm_id'].replace('/','_')+'_individual_mesh'); mesh.from_pydata(verts,[],faces)
    mesh.materials.append(materials['tree_trunk']); mesh.materials.append(materials['tree_crown'])
    for poly,index in zip(mesh.polygons,material_indices): poly.material_index=index
    mesh.update()
    obj=bpy.data.objects.new(f"tree_{tree['osm_id'].replace('/','_')}",mesh); bpy.data.collections['04_TREES'].objects.link(obj)
    obj.location=(float(tree['x_m']),float(tree['y_m']),0.0)
    obj['source']='OpenStreetMap API current extract'; obj['source_id']=tree['osm_id']; obj['osm_id']=tree['osm_id']
    obj['license']='ODbL 1.0'; obj['attribution']='OpenStreetMap and contributors'; obj['tags_json']=json.dumps(tree['tags'],ensure_ascii=False,sort_keys=True)
    obj['species_observed']=tree['species'] or ''; obj['height_observed_m']=tree['height_observed_m'] or 0.0
    obj['height_display_m']=h; obj['height_display_source']=tree['height_display_source']
    obj['crown_diameter_observed_m']=tree['crown_diameter_observed_m'] or 0.0
    obj['crown_diameter_display_m']=crown; obj['crown_diameter_display_source']=tree['crown_diameter_display_source']
    obj['position_source']=tree['position_source']; obj['crs']='EPSG:6677'; obj['shape']='generic visualization proxy; not botanical geometry'
    obj['feature_type']='tree'

for rec in features['green_areas']:
    material=materials['grass'] if rec['area_class'] in ('grass','meadow','grassland','recreation_ground') else materials['forest']
    obj=create_polygon_obj(rec,'07_GRASS','green',material,0.015)
    obj['area_class']=rec['area_class']; obj['source_area_m2']=rec['source_area_m2']; obj['display_area_m2']=rec['display_area_m2']
    obj['geometry_status']='mapped OSM area; display clipped around existing roads/buildings'

for rec in features['water_areas']:
    obj=create_polygon_obj(rec,'09_WATER','water',materials['water'],-0.03)
    obj['width_m']=rec['width_m'] or 0.0; obj['width_source']=rec['width_source']
    obj['source_area_m2']=rec['source_area_m2']; obj['display_area_m2']=rec['display_area_m2']

for rec in features['bridge_footprints']:
    obj=create_polygon_obj(rec,'06_BRIDGES','bridge',materials['bridge'],float(rec['display_z_m']))
    obj['name']=rec['name'] or rec['osm_id']; obj['source_area_m2']=rec['source_area_m2']
    obj['display_z_m']=rec['display_z_m']; obj['display_z_source']=rec['display_z_source']

scene['phase2b_osm_source_sha256']=features['source_sha256']; scene['phase2b_osm_snapshot_year']=features['source'].get('snapshot_year',0)
scene['phase2b_license']='Open Data Commons Open Database License (ODbL) 1.0'
scene['phase2b_attribution']='OpenStreetMap and contributors'; scene['phase2b_attribution_url']='https://www.openstreetmap.org/copyright'
scene['phase2b_crs']='EPSG:6677'; scene['phase2b_origin_projected_m']=json.dumps(features['origin_projected_m'])
scene['phase2b_tree_count']=len(features['trees']); scene['phase2b_green_area_count']=len(features['green_areas'])
scene['phase2b_water_count']=len(features['water_areas']); scene['phase2b_bridge_count']=len(features['bridge_footprints'])
scene['phase2b_estimation_note']='Tree shape/unknown dimensions, selected water widths, and bridge display Z are estimates marked on each object.'

geo=json.loads((Path('output/geo_reference_v02.json')).read_text(encoding='utf-8'))
geo['phase2b']={'source':'OpenStreetMap API current extract','source_sha256':features['source_sha256'],'crs':'EPSG:6677',
                'local_origin_projected_m':features['origin_projected_m'],'axes':'X east, Y north, Z up',
                'counts':features['counts'],'estimation_policy':features['estimation_policy'],
                'vertical_datum':'OSM vegetation/green/water/bridge data provide no common measured vertical datum; generic display offsets are estimates.'}
geo_path.parent.mkdir(parents=True,exist_ok=True); geo_path.write_text(json.dumps(geo,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(filepath=str(glb_path),export_format='GLB',use_selection=False,export_yup=True,export_extras=True)
print(json.dumps({'blend':str(blend_path),'glb':str(glb_path),'geo_reference':str(geo_path),
                  'trees':len(features['trees']),'green_areas':len(features['green_areas']),
                  'water_areas':len(features['water_areas']),'bridges':len(features['bridge_footprints']),
                  'paths_reclassified':len(moved)},ensure_ascii=False))
