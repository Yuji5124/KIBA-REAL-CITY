"""Create a visual v04 copy of v03 without modifying mapped city geometry."""
import bpy, hashlib, json, math, random, sys
from pathlib import Path
from mathutils import Vector

args=sys.argv[sys.argv.index('--')+1:]
if len(args)!=3:
    raise SystemExit('Expected v03_blend output_dir geo_reference_v04.json')
source_blend, output_dir, geo_path=map(Path,args)
output_dir.mkdir(parents=True,exist_ok=True)
blend_path=output_dir/'KIBA_REAL_CITY_v04.blend'
glb_path=output_dir/'KIBA_REAL_CITY_v04.glb'
if any(p.exists() for p in (blend_path,glb_path,geo_path)):
    raise SystemExit('A v04 output already exists; refusing to overwrite.')

bpy.ops.wm.open_mainfile(filepath=str(source_blend))
scene=bpy.context.scene

def pbr(name,color,roughness,metallic=0.0):
    material=bpy.data.materials.get(name) or bpy.data.materials.new(name)
    material.diffuse_color=(*color,1.0)
    material.use_nodes=True
    principled=material.node_tree.nodes.get('Principled BSDF')
    principled.inputs['Base Color'].default_value=(*color,1.0)
    principled.inputs['Roughness'].default_value=roughness
    principled.inputs['Metallic'].default_value=metallic
    return material

mats={
    'wall':pbr('Phase 3 | soft warm mineral walls',(0.76,0.79,0.81),0.78),
    'roof':pbr('Phase 3 | pale roof finish',(0.88,0.89,0.88),0.82),
    'road':pbr('Phase 3 | asphalt',(0.105,0.125,0.14),0.9),
    'park':pbr('Phase 3 | park surface',(0.28,0.48,0.23),0.92),
    'green':pbr('Phase 3 | mapped green areas',(0.25,0.43,0.19),0.94),
    'forest':pbr('Phase 3 | mapped woodland',(0.16,0.34,0.16),0.95),
    'water':pbr('Phase 3 | calm blue green water',(0.08,0.34,0.43),0.24,0.08),
    'bridge':pbr('Phase 3 | bridge concrete',(0.57,0.55,0.49),0.72),
    'trunk':pbr('Phase 3 | tree bark estimate',(0.23,0.13,0.075),0.96),
    'branch':pbr('Phase 3 | branch wood estimate',(0.28,0.17,0.095),0.94),
    'leaf_a':pbr('Phase 3 | foliage green A estimate',(0.18,0.39,0.16),0.91),
    'leaf_b':pbr('Phase 3 | foliage green B estimate',(0.25,0.46,0.18),0.91),
    'leaf_c':pbr('Phase 3 | foliage green C estimate',(0.12,0.31,0.14),0.93),
}

def assign_simple(obj,material):
    if obj.type!='MESH': return
    obj.data.materials.clear(); obj.data.materials.append(material)
    for face in obj.data.polygons: face.material_index=0

buildings=bpy.data.collections.get('01_BUILDINGS')
if not buildings: raise SystemExit('01_BUILDINGS collection missing.')
for obj in buildings.objects:
    if obj.type!='MESH': continue
    obj.data.materials.clear()
    obj.data.materials.append(mats['wall']); obj.data.materials.append(mats['roof'])
    for face in obj.data.polygons:
        face.material_index=1 if face.normal.z>0.92 else 0

for name in ('02_ROADS','08_PARK_PATHS'):
    col=bpy.data.collections.get(name)
    if col:
        for obj in col.objects: assign_simple(obj,mats['road'])
for obj in (bpy.data.collections.get('03_PARK').objects if bpy.data.collections.get('03_PARK') else []):
    assign_simple(obj,mats['park'])
for obj in (bpy.data.collections.get('07_GRASS').objects if bpy.data.collections.get('07_GRASS') else []):
    cls=str(obj.get('area_class',''))
    assign_simple(obj,mats['green'] if cls in ('grass','meadow','grassland','recreation_ground') else mats['forest'])
for obj in (bpy.data.collections.get('09_WATER').objects if bpy.data.collections.get('09_WATER') else []):
    assign_simple(obj,mats['water'])
for obj in (bpy.data.collections.get('06_BRIDGES').objects if bpy.data.collections.get('06_BRIDGES') else []):
    assign_simple(obj,mats['bridge'])

# Keep the exact Phase 2B tree proxy meshes and their OSM coordinates as hidden
# reference objects. The newly built visuals are separate display-only meshes.
reference=bpy.data.collections.get('99_REFERENCE')
if reference is None:
    reference=bpy.data.collections.new('99_REFERENCE'); bpy.data.collections['KIBA_REAL_CITY'].children.link(reference)
trees=bpy.data.collections.get('04_TREES')
if trees is None: raise SystemExit('04_TREES collection missing.')
source_trees=sorted([o for o in trees.objects if o.get('feature_type')=='tree'],key=lambda o:str(o.get('source_id','')))
if len(source_trees)!=33: raise SystemExit(f'Expected 33 mapped tree positions; got {len(source_trees)}.')
for old in source_trees:
    for col in list(old.users_collection): col.objects.unlink(old)
    reference.objects.link(old)
    old.hide_render=True
    old.hide_set(True)
    old['phase3_role']='unchanged Phase 2B source position and proxy geometry'

def add_cylinder(vertices,faces,indices,start,end,r0,r1,mat_index,segments=7):
    start,end=Vector(start),Vector(end); direction=end-start
    if direction.length<1e-8: return
    direction.normalize()
    helper=Vector((0,0,1)) if abs(direction.z)<0.9 else Vector((1,0,0))
    u=direction.cross(helper).normalized(); v=direction.cross(u).normalized()
    base=len(vertices)
    for center,radius in ((start,r0),(end,r1)):
        for i in range(segments):
            angle=math.tau*i/segments
            point=center+radius*(u*math.cos(angle)+v*math.sin(angle))
            vertices.append(tuple(point))
    for i in range(segments):
        j=(i+1)%segments
        faces.append((base+i,base+j,base+segments+j,base+segments+i)); indices.append(mat_index)
    faces.extend((tuple(base+i for i in reversed(range(segments))),tuple(base+segments+i for i in range(segments))))
    indices.extend((mat_index,mat_index))

def add_ellipsoid(vertices,faces,indices,center,radii,mat_index,segments=9,rings=6):
    cx,cy,cz=center; rx,ry,rz=radii; base=len(vertices)
    for j in range(rings+1):
        phi=math.pi*j/rings
        for i in range(segments):
            theta=math.tau*i/segments
            vertices.append((cx+rx*math.sin(phi)*math.cos(theta),
                             cy+ry*math.sin(phi)*math.sin(theta),
                             cz+rz*math.cos(phi)))
    for j in range(rings):
        for i in range(segments):
            a=base+j*segments+i; b=base+j*segments+(i+1)%segments
            c=b+segments; d=a+segments
            faces.append((a,b,c,d)); indices.append(mat_index)

def make_tree(source,index):
    identity=str(source['source_id'])
    seed=int.from_bytes(hashlib.sha256(('KIBA_PHASE3_TREE_V1:'+identity).encode()).digest()[:8],'big')
    rng=random.Random(seed)
    style=('round_broadleaf','columnar','spreading')[seed%3]
    h=float(source.get('height_display_m') or 6.0)
    diameter=float(source.get('crown_diameter_display_m') or 4.0)
    radius=diameter*0.5
    verts=[]; faces=[]; mi=[]
    trunk_h=h*(0.43 if style!='columnar' else 0.52)
    trunk_r=radius*0.075
    add_cylinder(verts,faces,mi,(0,0,0),(0,0,trunk_h),trunk_r,trunk_r*0.68,0,8)
    # Branch and crown dimensions are explicitly estimated presentation geometry.
    branches=5 if style=='spreading' else 4
    for i in range(branches):
        angle=math.tau*i/branches+rng.uniform(-0.12,0.12)
        reach=radius*rng.uniform(0.36,0.57)
        z0=trunk_h*rng.uniform(0.55,0.78)
        z1=h*rng.uniform(0.61,0.78)
        end=(math.cos(angle)*reach,math.sin(angle)*reach,z1)
        add_cylinder(verts,faces,mi,(0,0,z0),end,trunk_r*0.55,trunk_r*0.22,1,6)
    if style=='columnar':
        for k,(z,scale) in enumerate(((0.61,0.46),(0.76,0.40),(0.89,0.31))):
            add_ellipsoid(verts,faces,mi,(rng.uniform(-.05,.05),rng.uniform(-.05,.05),h*z),
                          (radius*scale,radius*scale*0.88,h*0.17),2+k%3)
    elif style=='spreading':
        for i in range(5):
            angle=math.tau*i/5+rng.uniform(-.12,.12); reach=radius*rng.uniform(.38,.55)
            add_ellipsoid(verts,faces,mi,(math.cos(angle)*reach,math.sin(angle)*reach,h*rng.uniform(.63,.73)),
                          (radius*.43,radius*.37,h*.12),2+i%3)
        add_ellipsoid(verts,faces,mi,(0,0,h*.77),(radius*.46,radius*.45,h*.16),3)
    else:
        add_ellipsoid(verts,faces,mi,(0,0,h*.72),(radius*.53,radius*.51,h*.24),2)
        for i in range(3):
            angle=math.tau*i/3+rng.uniform(-.1,.1); reach=radius*.3
            add_ellipsoid(verts,faces,mi,(math.cos(angle)*reach,math.sin(angle)*reach,h*rng.uniform(.65,.78)),
                          (radius*.31,radius*.30,h*.17),3+i%2)
    mesh=bpy.data.meshes.new('phase3_display_'+identity.replace('/','_'))
    mesh.from_pydata(verts,[],faces)
    for key in ('trunk','branch','leaf_a','leaf_b','leaf_c'): mesh.materials.append(mats[key])
    for polygon,material_index in zip(mesh.polygons,mi): polygon.material_index=material_index
    mesh.update()
    obj=bpy.data.objects.new(f'tree_visual_{style}_{identity.replace("/","_")}',mesh)
    trees.objects.link(obj); obj.location=source.location.copy()
    obj['source_id']=identity; obj['osm_id']=identity; obj['feature_type']='tree_visual'
    obj['source']='OpenStreetMap mapped tree position; visual form is estimated'
    obj['license']='ODbL 1.0'; obj['attribution']='OpenStreetMap and contributors'
    obj['attribution_url']='https://www.openstreetmap.org/copyright'; obj['crs']='EPSG:6677'
    obj['species_observed']=source.get('species_observed','')
    obj['visual_form']=style; obj['visual_form_source']='presentation estimate; fixed seed from OSM ID'
    obj['height_display_m']=h; obj['crown_diameter_display_m']=diameter
    obj['height_display_source']=source.get('height_display_source','estimated Phase 2B default')
    obj['position_source']=source.get('position_source','OpenStreetMap node tagged natural=tree')
    # Blender custom integer properties are signed 32-bit; retain the full
    # deterministic seed as text instead of truncating it.
    obj['phase3_random_seed']=str(seed)
    return obj

visual_trees=[make_tree(obj,i) for i,obj in enumerate(source_trees)]
if len(visual_trees)!=33: raise SystemExit('Display tree count mismatch.')

scene['phase3_style']='clean daylight city model; PBR estimates are presentation-only'
scene['phase3_geometry_policy']='No source building, road, park, green, water, bridge, or tree-position geometry modified.'
scene['phase3_tree_models']='Three deterministic presentation forms; tree species remain unconfirmed.'
scene['phase3_material_policy']='Appearance-only PBR materials; no measured facade colors are claimed.'

geo_source=source_blend.parent/'geo_reference_v03.json'
geo=json.loads(geo_source.read_text(encoding='utf-8'))
geo['phase3']={'visual_revision':'v04','source':'v03 immutable geodata',
               'crs':'EPSG:6677','origin_preserved':True,
               'appearance_only_materials':True,'tree_visuals':len(visual_trees),
               'tree_species_observed':sum(bool(o.get('species_observed')) for o in source_trees),
               'tree_shape_source':'estimated display geometry at existing OSM positions; fixed seed per OSM ID',
               'data_geometry_policy':'Source meshes retained in 99_REFERENCE; building, transport, park, green, water, bridge and tree-position geometry unchanged.',
               'material_attributes':'PBR display estimates; no facade or tree species inference.'}
geo_path.parent.mkdir(parents=True,exist_ok=True)
geo_path.write_text(json.dumps(geo,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
bpy.ops.export_scene.gltf(filepath=str(glb_path),export_format='GLB',use_selection=False,
                          export_yup=True,export_extras=True,use_visible=True)
print(json.dumps({'blend':str(blend_path),'glb':str(glb_path),'geo_reference':str(geo_path),
                  'trees':len(visual_trees),'tree_styles':{s:sum(o['visual_form']==s for o in visual_trees)
                  for s in ('round_broadleaf','columnar','spreading')}},ensure_ascii=False))
