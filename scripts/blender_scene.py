import bpy, json, math, sys
from pathlib import Path
from mathutils import Vector
from mathutils.geometry import tessellate_polygon

args=sys.argv[sys.argv.index('--')+1:]
if len(args)!=3: raise SystemExit('Expected processed.json blend_path glb_path')
data_path,blend_path,glb_path=map(Path,args)
data=json.loads(data_path.read_text(encoding='utf-8'))
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
for c in list(bpy.data.collections):
    if c.name!='Collection': bpy.data.collections.remove(c)
root=bpy.data.collections.get('Collection')
if root: bpy.data.collections.remove(root)
scene=bpy.context.scene
master=bpy.data.collections.new('KIBA_REAL_CITY'); scene.collection.children.link(master)
def collection(name):
    c=bpy.data.collections.new(name); master.children.link(c); return c
buildings=collection('01_BUILDINGS')
for name in ['02_ROADS','03_PARK','04_TREES','05_TERRAIN','06_BRIDGES','99_REFERENCE']: collection(name)
def material(name,color):
    m=bpy.data.materials.new(name); m.diffuse_color=(*color,1); m.use_nodes=True
    bs=m.node_tree.nodes.get('Principled BSDF'); bs.inputs['Base Color'].default_value=(*color,1); return m
white=material('Building | warm white',(0.82,0.84,0.86)); ground=material('Ground | neutral',(0.18,0.20,0.19))
all_xy=[]; count=0
for b in data['buildings']:
    for n,ring in enumerate(b['footprints']):
        pts=[(float(p[0]),float(p[1])) for p in ring[:-1]]
        if len(pts)<3: continue
        signed=sum(pts[i][0]*pts[(i+1)%len(pts)][1]-pts[(i+1)%len(pts)][0]*pts[i][1] for i in range(len(pts)))
        if signed<0: pts.reverse()
        h=float(b['height_m']); verts=[(x,y,0.0) for x,y in pts]+[(x,y,h) for x,y in pts]; N=len(pts)
        faces=[]
        for i in range(N): faces.append((i,(i+1)%N,(i+1)%N+N,i+N))
        tess=tessellate_polygon([[Vector((x,y,0)) for x,y in pts]])
        for tri in tess: faces.append(tuple(int(v)+N for v in tri))
        mesh=bpy.data.meshes.new(f'{b["id"]}_mesh'); mesh.from_pydata(verts,[],faces); mesh.materials.append(white); mesh.update()
        obj=bpy.data.objects.new(b['id'] if n==0 else f'{b["id"]}_{n+1}',mesh); buildings.objects.link(obj)
        obj['citygml_id']=b['id']; obj['height_m']=h; obj['height_source']=b['height_source']; obj['source_file']=b['source_file']
        all_xy.extend(pts); count+=1
if not count: raise SystemExit('No building mesh was created.')
# Context ground is a neutral 500 m reference plane; it is not represented as measured terrain.
gmesh=bpy.data.meshes.new('reference_ground_mesh'); gmesh.from_pydata([(-250,-250,-0.05),(250,-250,-0.05),(250,250,-0.05),(-250,250,-0.05)],[],[(0,1,2,3)])
gobj=bpy.data.objects.new('500 m reference area | flat placeholder',gmesh); bpy.data.collections['05_TERRAIN'].objects.link(gobj); gobj.data.materials.append(ground); gobj['data_status']='flat visual placeholder; not measured terrain'
cam_data=bpy.data.cameras.new('City overview'); cam=bpy.data.objects.new('City overview',cam_data); scene.collection.objects.link(cam)
cam.location=(390,-470,480); target=Vector((0,0,0)); direction=target-Vector(cam.location); cam.rotation_euler=direction.to_track_quat('-Z','Y').to_euler(); cam_data.lens=48; scene.camera=cam
sun_data=bpy.data.lights.new('Sun','SUN'); sun=bpy.data.objects.new('Sun',sun_data); scene.collection.objects.link(sun); sun.rotation_euler=(math.radians(25),math.radians(-20),math.radians(-25)); sun_data.energy=2.0
world=scene.world or bpy.data.worlds.new('World'); scene.world=world; world.use_nodes=True; world.node_tree.nodes['Background'].inputs['Color'].default_value=(0.48,0.53,0.60,1); world.node_tree.nodes['Background'].inputs['Strength'].default_value=0.8
scene.render.engine='BLENDER_EEVEE_NEXT'; scene.render.resolution_x=1280; scene.render.resolution_y=960; scene.render.resolution_percentage=100
scene.unit_settings.system='METRIC'; scene.unit_settings.scale_length=1.0
scene['project']='KIBA REAL CITY'; scene['crs']=data['crs']; scene['local_axes']='X east, Y north, Z up'; scene['model_buildings']=count
bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(filepath=str(glb_path),export_format='GLB',use_selection=False,export_yup=True,export_extras=True)
print(f'KIBA scene: {count} editable building objects; wrote BLEND and GLB')
