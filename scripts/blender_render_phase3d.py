"""Render four deterministic presentation views of an already-built v05 scene."""
import bpy, json, math, sys
from pathlib import Path
from mathutils import Vector
args=sys.argv[sys.argv.index('--')+1:]
if len(args)!=3:raise SystemExit('Expected v05.blend previews_dir phase3d_features.json')
blend,preview_dir,features_path=map(Path,args)
features=json.loads(features_path.read_text(encoding='utf-8'))
preview_dir.mkdir(parents=True,exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(blend))
scene=bpy.context.scene
if scene.world is None:scene.world=bpy.data.worlds.new('Phase 3D | daylight world')
scene.world.use_nodes=True
bg=scene.world.node_tree.nodes.get('Background');bg.inputs['Color'].default_value=(0.78,0.84,0.94,1);bg.inputs['Strength'].default_value=0.65
scene.render.engine='BLENDER_EEVEE_NEXT';scene.render.resolution_x=1920;scene.render.resolution_y=1280;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_mode='RGBA'
scene.view_settings.view_transform='AgX'
scene.render.film_transparent=False
scene.camera.data.lens=48 if scene.camera else 48
if not any(o.type=='LIGHT' and o.data.type=='SUN' for o in scene.objects):
    data=bpy.data.lights.new('Phase 3D daylight sun','SUN');data.energy=3.0
    sun=bpy.data.objects.new('Phase 3D daylight sun',data);scene.collection.objects.link(sun)
    sun.rotation_euler=(math.radians(24),math.radians(-18),math.radians(-28))
else:
    for obj in scene.objects:
        if obj.type=='LIGHT' and obj.data.type=='SUN':obj.data.energy=3.0
def aim(camera,target):camera.rotation_euler=(Vector(target)-camera.location).to_track_quat('-Z','Y').to_euler()
def camera_for(name,location,target,ortho=None,lens=48):
    data=bpy.data.cameras.new(name);obj=bpy.data.objects.new(name,data);scene.collection.objects.link(obj)
    obj.location=location;aim(obj,target);data.lens=lens
    if ortho is not None:data.type='ORTHO';data.ortho_scale=ortho
    return obj
bounds=features['bounds_local_m'];west,south,east,north=map(float,bounds)
center=((west+east)/2,(south+north)/2,0)
museum=features['museum'];mb=museum['bounds_local_m']
museum_center=((mb[0]+mb[2])/2,(mb[1]+mb[3])/2,0)
views=[
 ('KIBA_REAL_CITY_v05_overview.png',camera_for('v05 full park to museum overview',(center[0]+620,center[1]-920,1900),center,lens=48),1600,1200),
 ('KIBA_REAL_CITY_v05_museum.png',camera_for('v05 museum detail',(museum_center[0]+230,museum_center[1]-310,330),museum_center,lens=58),1600,1200),
 ('KIBA_REAL_CITY_v05_kiba_bridge.png',camera_for('v05 Kiba Park Bridge detail',(90,-140,230),(88,135,0),lens=58),1600,1200),
 ('KIBA_REAL_CITY_v05_top.png',camera_for('v05 top view',(center[0],center[1],1600),center,ortho=(north-south)*1.15*4/3),1600,1200),
]
for name,camera,width,height in views:
    target=preview_dir/name
    if target.exists():raise SystemExit(f'Refusing to overwrite preview: {target}')
    scene.camera=camera;scene.render.resolution_x=width;scene.render.resolution_y=height
    scene.render.filepath=str(target);bpy.ops.render.render(write_still=True)
    if not target.is_file() or target.stat().st_size==0:raise SystemExit(f'Render failed: {target}')
    print(f'RENDERED {target} {target.stat().st_size} bytes')
