"""Build a new v05 scene from v04 plus real 2023 PLATEAU and 2026 OSM data."""
from __future__ import annotations
import bpy,hashlib,json,math,random,sys
from pathlib import Path
from mathutils import Vector

args=sys.argv[sys.argv.index('--')+1:]
if len(args)!=5:
    raise SystemExit('Expected v04_blend phase3d_features display_surfaces output_dir geo_reference_v05.json')
source_blend,features_path,surfaces_path,output_dir,geo_path=map(Path,args)
output_dir.mkdir(parents=True,exist_ok=True)
blend_path=output_dir/'KIBA_REAL_CITY_v05.blend';glb_path=output_dir/'KIBA_REAL_CITY_v05.glb'
if any(p.exists() for p in (blend_path,glb_path,geo_path)):
    raise SystemExit('A v05 output exists; refusing to overwrite.')
features=json.loads(features_path.read_text(encoding='utf-8'))
surface_data=json.loads(surfaces_path.read_text(encoding='utf-8'))

bpy.ops.wm.open_mainfile(filepath=str(source_blend))
scene=bpy.context.scene
root=bpy.data.collections.get('KIBA_REAL_CITY')
if root is None:raise SystemExit('KIBA_REAL_CITY collection missing.')
reference=bpy.data.collections.get('99_REFERENCE')
if reference is None:
    reference=bpy.data.collections.new('99_REFERENCE');root.children.link(reference)

def pbr(name,color,roughness):
    material=bpy.data.materials.get(name) or bpy.data.materials.new(name)
    material.diffuse_color=(*color,1.0);material.use_nodes=True
    bs=material.node_tree.nodes.get('Principled BSDF')
    bs.inputs['Base Color'].default_value=(*color,1.0);bs.inputs['Roughness'].default_value=roughness
    return material

mats={
 'wall':bpy.data.materials.get('Phase 3 | soft warm mineral walls') or pbr('Phase 3 | soft warm mineral walls',(0.76,0.79,0.81),0.78),
 'roof':bpy.data.materials.get('Phase 3 | pale roof finish') or pbr('Phase 3 | pale roof finish',(0.88,0.89,0.88),0.82),
 'road':bpy.data.materials.get('Phase 3 | asphalt') or pbr('Phase 3 | asphalt',(0.105,0.125,0.14),0.9),
 'park':bpy.data.materials.get('Phase 3 | park surface') or pbr('Phase 3 | park surface',(0.28,0.48,0.23),0.92),
 'green':bpy.data.materials.get('Phase 3 | mapped green areas') or pbr('Phase 3 | mapped green areas',(0.25,0.43,0.19),0.94),
 'forest':bpy.data.materials.get('Phase 3 | mapped woodland') or pbr('Phase 3 | mapped woodland',(0.16,0.34,0.16),0.95),
 'water':bpy.data.materials.get('Phase 3 | calm blue green water') or pbr('Phase 3 | calm blue green water',(0.08,0.34,0.43),0.24),
 'bridge':bpy.data.materials.get('Phase 3 | bridge concrete') or pbr('Phase 3 | bridge concrete',(0.57,0.55,0.49),0.72),
 'trunk':bpy.data.materials.get('Phase 3 | tree bark estimate') or pbr('Phase 3 | tree bark estimate',(0.23,0.13,0.075),0.96),
 'branch':bpy.data.materials.get('Phase 3 | branch wood estimate') or pbr('Phase 3 | branch wood estimate',(0.28,0.17,0.095),0.94),
 'leaf_a':bpy.data.materials.get('Phase 3 | foliage green A estimate') or pbr('Phase 3 | foliage green A estimate',(0.18,0.39,0.16),0.91),
 'leaf_b':bpy.data.materials.get('Phase 3 | foliage green B estimate') or pbr('Phase 3 | foliage green B estimate',(0.25,0.46,0.18),0.91),
 'leaf_c':bpy.data.materials.get('Phase 3 | foliage green C estimate') or pbr('Phase 3 | foliage green C estimate',(0.12,0.31,0.14),0.93),
 'ground':pbr('Phase 3D | neutral context ground',(0.30,0.33,0.35),0.92)}
path_classes={'footway','path','pedestrian','steps','cycleway'}

def move_source_to_reference(obj):
    for col in list(obj.users_collection):col.objects.unlink(obj)
    reference.objects.link(obj);obj['phase3d_role']='immutable_v04_geodata_source'
    obj.hide_render=True;obj.hide_set(True)

# Preserve the exact original ground mesh objects and their transform in the
# reference collection. New layer-separated, non-overlapping display surfaces
# are generated as separate editable objects.
ground_collections=('02_ROADS','03_PARK','07_GRASS','08_PARK_PATHS','09_WATER','05_TERRAIN')
for name in ground_collections:
    col=bpy.data.collections.get(name)
    if col:
        for obj in list(col.objects):
            if obj.type=='MESH':move_source_to_reference(obj)

def surface_object(record,collection,material,z,kind):
    mesh=bpy.data.meshes.new('display_'+record['piece_id'].replace('/','_').replace(':','_'))
    verts=[(float(x),float(y),float(z)) for x,y in record.get('mesh_vertices_xy_m',[])]
    faces=[tuple(int(i) for i in f) for f in record.get('mesh_faces',[])]
    mesh.from_pydata(verts,[],faces);mesh.materials.append(material);mesh.update()
    obj=bpy.data.objects.new('display_'+record['piece_id'].replace('/','_').replace(':','_'),mesh)
    bpy.data.collections[collection].objects.link(obj)
    obj['source_id']=record['source_id'];obj['osm_id']=record['source_id']
    obj['feature_type']=kind;obj['phase3d_role']='display_surface'
    obj['feature_piece_id']=record['piece_id'];obj['display_z_m']=float(z)
    obj['source']='OpenStreetMap mapped geometry; display-only overlap and height treatment'
    obj['crs']='EPSG:6677';obj['attribution']='OpenStreetMap and contributors';obj['license']='ODbL 1.0'
    obj['tags_json']=json.dumps(record.get('tags',{}),ensure_ascii=False,sort_keys=True)
    obj['display_area_m2']=float(record.get('display_area_m2',record.get('triangulated_area_m2',0.0)))
    if record.get('width_m') is not None:obj['width_m']=float(record['width_m'])
    if record.get('width_source'):obj['width_source']=record['width_source']
    if record.get('area_class'):obj['area_class']=record['area_class']
    return obj

surface_count={'roads':0,'park':0,'grass':0,'water':0}
for rec in surface_data['surfaces']:
    kind=rec['feature_type']
    if kind=='road_display':
        col='08_PARK_PATHS' if rec.get('highway') in path_classes else '02_ROADS'
        surface_object(rec,col,mats['road'],surface_data['z_layers_m']['roads'],'road_display')
        surface_count['roads']+=1
    elif kind=='park_display':
        surface_object(rec,'03_PARK',mats['park'],surface_data['z_layers_m']['park'],'park_display')
        surface_count['park']+=1
    elif kind=='grass_display':
        mat=mats['green'] if rec.get('area_class') in ('grass','meadow','grassland','recreation_ground') else mats['forest']
        surface_object(rec,'07_GRASS',mat,surface_data['z_layers_m']['grass'],'green_display')
        surface_count['grass']+=1
    elif kind=='water_display':
        surface_object(rec,'09_WATER',mats['water'],surface_data['z_layers_m']['water'],'water_display')
        surface_count['water']+=1

# Replace the visual placeholder ground with one larger plane at a separate
# depth. The original 500 m reference plane remains hidden and unmodified.
bounds=features['bounds_local_m'];w,s,e,n=map(float,bounds);gz=surface_data['z_layers_m']['terrain']
ground_mesh=bpy.data.meshes.new('phase3d_expanded_reference_ground')
ground_mesh.from_pydata([(w,s,gz),(e,s,gz),(e,n,gz),(w,n,gz)],[],[(0,1,2,3)])
ground_mesh.materials.append(mats['ground']);ground_mesh.update()
ground=bpy.data.objects.new('expanded flat visual reference ground (not measured terrain)',ground_mesh)
bpy.data.collections['05_TERRAIN'].objects.link(ground)
ground['data_status']='flat presentation plane only; no measured elevation claimed'
ground['phase3d_role']='display_ground';ground['crs']='EPSG:6677'

def building_mesh(record,object_name):
    xy=record['mesh_vertices_xy_m'];faces2=record['mesh_faces']
    base=float(record['base_z_m']);height=float(record['height_m'])
    if not xy or not faces2 or height<=0:raise ValueError(f'No usable LOD1 geometry for {object_name}')
    nverts=len(xy);verts=[(float(x),float(y),base) for x,y in xy]+[(float(x),float(y),base+height) for x,y in xy]
    faces=[];material_indices=[]
    for face in faces2:
        faces.append(tuple(int(i)+nverts for i in face));material_indices.append(1)
        faces.append(tuple(int(i) for i in reversed(face)));material_indices.append(0)
    lookup={(float(x),float(y)):i for i,(x,y) in enumerate(xy)}
    for poly in record['geometry']:
        for ring in [poly['exterior'],*poly.get('interiors',[])]:
            indices=[lookup[(float(x),float(y))] for x,y in ring]
            for a,b in zip(indices,indices[1:]):
                if a==b:continue
                faces.append((a,b,b+nverts,a+nverts));material_indices.append(0)
    mesh=bpy.data.meshes.new(object_name+'_LOD1_mesh')
    mesh.from_pydata(verts,[],faces);mesh.materials.append(mats['wall']);mesh.materials.append(mats['roof'])
    for polygon,index in zip(mesh.polygons,material_indices):polygon.material_index=index
    mesh.update();return mesh

def add_building(record,continuation=False):
    if continuation:
        identity=record['source_citygml_id'];name='building_extension_'+identity
        obj=bpy.data.objects.new(name,building_mesh(record,name))
        obj['parent_citygml_id']=identity;obj['source_id']=identity
        obj['phase3d_piece_id']=record['phase3d_piece_id']
        obj['feature_type']='building_continuation'
        obj['geometry_status']='source CityGML footprint minus immutable v04 building footprint'
    else:
        identity=record['citygml_id'];name=identity
        obj=bpy.data.objects.new(name,building_mesh(record,name))
        obj['citygml_id']=identity;obj['source_id']=identity
        obj['feature_type']='building';obj['dataset']='Project PLATEAU Tokyo Koto City 3D City Model'
        obj['dataset_year']=2023;obj['source_file']=record['source_file']
        obj['height_m']=float(record['height_m']);obj['base_z_m']=float(record['base_z_m'])
        obj['height_source']=record['height_source']
        obj['measured_height_m']=float(record['measured_height_m'] or 0.0)
        obj['geometry_status']='real PLATEAU LOD1; complete source footprint retained'
        if identity==features['museum']['citygml_id']:
            obj['name']='東京都現代美術館';obj['validated_osm_id']='relation/12077221'
            obj['footprint_iou_osm']=features['museum']['osm_citygml_footprint_validation']['intersection_over_union']
    bpy.data.collections['01_BUILDINGS'].objects.link(obj)
    obj['crs']='EPSG:6677';obj['source_license']='PLATEAU source license confirmation recorded in LICENSE_DATA.md'
    return obj

for rec in features['buildings']['new']:add_building(rec,False)
for rec in features['buildings']['continuations']:add_building(rec,True)

# Create individual editable tree visuals at the newly mapped OSM locations.
tree_col=bpy.data.collections['04_TREES']
def add_cylinder(vertices,faces,indices,start,end,r0,r1,material_index,segments=7):
    start,end=Vector(start),Vector(end);direction=end-start
    if direction.length<1e-8:return
    direction.normalize();helper=Vector((0,0,1)) if abs(direction.z)<0.9 else Vector((1,0,0))
    u=direction.cross(helper).normalized();v=direction.cross(u).normalized();base=len(vertices)
    for center,radius in ((start,r0),(end,r1)):
        for i in range(segments):
            a=math.tau*i/segments;point=center+radius*(u*math.cos(a)+v*math.sin(a));vertices.append(tuple(point))
    for i in range(segments):
        j=(i+1)%segments;faces.append((base+i,base+j,base+segments+j,base+segments+i));indices.append(material_index)
    faces.extend((tuple(base+i for i in reversed(range(segments))),tuple(base+segments+i for i in range(segments))))
    indices.extend((material_index,material_index))
def add_ellipsoid(vertices,faces,indices,center,radii,material_index,segments=9,rings=6):
    cx,cy,cz=center;rx,ry,rz=radii;base=len(vertices)
    for j in range(rings+1):
        phi=math.pi*j/rings
        for i in range(segments):
            theta=math.tau*i/segments
            vertices.append((cx+rx*math.sin(phi)*math.cos(theta),cy+ry*math.sin(phi)*math.sin(theta),cz+rz*math.cos(phi)))
    for j in range(rings):
        for i in range(segments):
            a=base+j*segments+i;b=base+j*segments+(i+1)%segments;c=b+segments;d=a+segments
            faces.append((a,b,c,d));indices.append(material_index)
def add_tree(tree):
    oid=tree['osm_id'];seed=int.from_bytes(hashlib.sha256(('KIBA_PHASE3_TREE_V1:'+oid).encode()).digest()[:8],'big')
    rng=random.Random(seed);style=('round_broadleaf','columnar','spreading')[seed%3]
    h=float(tree['height_display_m']);radius=float(tree['crown_diameter_display_m'])/2
    verts=[];faces=[];mi=[];trunk_h=h*(.52 if style=='columnar' else .43);trunk_r=radius*.075
    add_cylinder(verts,faces,mi,(0,0,0),(0,0,trunk_h),trunk_r,trunk_r*.68,0,8)
    for i in range(5 if style=='spreading' else 4):
        angle=math.tau*i/(5 if style=='spreading' else 4)+rng.uniform(-.12,.12)
        reach=radius*rng.uniform(.36,.57);z0=trunk_h*rng.uniform(.55,.78);z1=h*rng.uniform(.61,.78)
        add_cylinder(verts,faces,mi,(0,0,z0),(math.cos(angle)*reach,math.sin(angle)*reach,z1),trunk_r*.55,trunk_r*.22,1,6)
    if style=='columnar':
        for k,(z,scale) in enumerate(((.61,.46),(.76,.40),(.89,.31))):
            add_ellipsoid(verts,faces,mi,(rng.uniform(-.05,.05),rng.uniform(-.05,.05),h*z),(radius*scale,radius*scale*.88,h*.17),2+k%3)
    elif style=='spreading':
        for i in range(5):
            a=math.tau*i/5+rng.uniform(-.12,.12);reach=radius*rng.uniform(.38,.55)
            add_ellipsoid(verts,faces,mi,(math.cos(a)*reach,math.sin(a)*reach,h*rng.uniform(.63,.73)),(radius*.43,radius*.37,h*.12),2+i%3)
        add_ellipsoid(verts,faces,mi,(0,0,h*.77),(radius*.46,radius*.45,h*.16),3)
    else:
        add_ellipsoid(verts,faces,mi,(0,0,h*.72),(radius*.53,radius*.51,h*.24),2)
        for i in range(3):
            a=math.tau*i/3+rng.uniform(-.1,.1);reach=radius*.3
            add_ellipsoid(verts,faces,mi,(math.cos(a)*reach,math.sin(a)*reach,h*rng.uniform(.65,.78)),(radius*.31,radius*.30,h*.17),3+i%2)
    mesh=bpy.data.meshes.new('phase3d_'+oid.replace('/','_'));mesh.from_pydata(verts,[],faces)
    for name in ('trunk','branch','leaf_a','leaf_b','leaf_c'):mesh.materials.append(mats[name])
    for poly,index in zip(mesh.polygons,mi):poly.material_index=index
    mesh.update();obj=bpy.data.objects.new('tree_visual_'+style+'_'+oid.replace('/','_'),mesh);tree_col.objects.link(obj)
    obj.location=(float(tree['x_m']),float(tree['y_m']),0.0);obj['osm_id']=oid;obj['source_id']=oid
    obj['feature_type']='tree_visual';obj['visual_form']=style
    obj['source']='OpenStreetMap real mapped tree position; shape is estimated presentation geometry'
    obj['license']='ODbL 1.0';obj['attribution']='OpenStreetMap and contributors'
    obj['crs']='EPSG:6677';obj['height_display_m']=h;obj['crown_diameter_display_m']=float(tree['crown_diameter_display_m'])
    obj['height_display_source']=tree['height_display_source'];obj['crown_diameter_display_source']=tree['crown_diameter_display_source']
    obj['phase3d_seed']=str(seed);obj['species_observed']=tree.get('species') or ''
    empty=bpy.data.objects.new('tree_position_source_'+oid.replace('/','_'),None);reference.objects.link(empty)
    empty.location=(float(tree['x_m']),float(tree['y_m']),0.0);empty['source_id']=oid
    empty['osm_id']=oid;empty['feature_type']='tree_position';empty['crs']='EPSG:6677'
    empty['source']='OpenStreetMap node tagged natural=tree';empty.hide_render=True;empty.hide_set(True)
for rec in features['osm']['trees']:add_tree(rec)

# New bridge footprint pieces are separate additions; originals stay unchanged.
for rec in features['osm']['bridges']:
    surface_object({**rec,'piece_id':'outside-v04:'+rec['osm_id'],
       'mesh_vertices_xy_m':rec['mesh_vertices_xy_m'],'mesh_faces':rec['mesh_faces']},
       '06_BRIDGES',mats['bridge'],float(rec['display_z_m']),'bridge_extension')

scene['phase3d_source']='KIBA REAL CITY v04; local origin and existing source meshes preserved'
scene['phase3d_crs']='EPSG:6677';scene['phase3d_bounds_local_m']=json.dumps(features['bounds_local_m'])
scene['phase3d_building_count_new']=len(features['buildings']['new'])
scene['phase3d_building_continuations']=len(features['buildings']['continuations'])
scene['phase3d_display_surface_z_layers']=json.dumps(surface_data['z_layers_m'])
scene['phase3d_display_note']='Ground surfaces use separate display meshes with vertical separation and overlap partitioning; original v04 meshes are hidden in 99_REFERENCE unchanged.'

geo=json.loads((source_blend.parent/'geo_reference_v04.json').read_text(encoding='utf-8'))
geo['phase3d']={**geo.get('phase3',{}),'visual_revision':'v05','source':'immutable v04 plus real 2023 PLATEAU and 2026 OSM extension',
 'crs':'EPSG:6677','origin_preserved':True,'bounds_local_m':features['bounds_local_m'],
 'bounds_projected_epsg6677_m':features['bounds_projected_epsg6677_m'],
 'bounds_wgs84_lonlat':features['bounds_wgs84_lonlat'],'extent_width_m':features['bounds_local_m'][2]-features['bounds_local_m'][0],
 'extent_height_m':features['bounds_local_m'][3]-features['bounds_local_m'][1],
 'mesh_codes_1km':features['mesh_codes_1km'],'museum':features['museum'],
 'source_files':features['sources']['citygml_source_files'],
 'osm_snapshot':features['sources']['osm'],
 'counts':features['counts'],'display_surface_z_layers_m':surface_data['z_layers_m'],
 'display_overlap_area_m2':surface_data['overlap_areas_after_partition_m2'],
 'feature_preservation_policy':'Original v04 ground-feature objects and trees are kept in 99_REFERENCE with unchanged mesh vertices/faces and positions. Appearance-only display surfaces/offsets are separate.'}
geo_path.parent.mkdir(parents=True,exist_ok=True)
geo_path.write_text(json.dumps(geo,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

# Default saved Blender view frames the expanded park-to-museum area.
target=Vector(((w+e)/2,(s+n)/2,0))
cam=scene.camera
if cam:
    cam.location=target+Vector((650,-950,1400));direction=target-cam.location
    cam.rotation_euler=direction.to_track_quat('-Z','Y').to_euler();cam.data.lens=48
scene.render.engine='BLENDER_EEVEE_NEXT';scene.render.resolution_x=1600;scene.render.resolution_y=1200
scene.render.resolution_percentage=100
bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
bpy.ops.export_scene.gltf(filepath=str(glb_path),export_format='GLB',use_selection=False,
                          export_yup=True,export_extras=True,use_visible=True)
print(json.dumps({'blend':str(blend_path),'glb':str(glb_path),'geo_reference':str(geo_path),
 'new_buildings':len(features['buildings']['new']),'building_continuations':len(features['buildings']['continuations']),
 'display_surfaces':surface_count,'new_trees':len(features['osm']['trees']),
 'new_bridges':len(features['osm']['bridges'])},ensure_ascii=False))
