import bpy, json, math, sys
from pathlib import Path
args=sys.argv[sys.argv.index('--')+1:]
blend,glb,processed,out=map(Path,args)
data=json.loads(processed.read_text(encoding='utf-8'))
bpy.ops.wm.open_mainfile(filepath=str(blend))
mesh_objects=[o for o in bpy.data.objects if o.type=='MESH']
finite_blend=all(math.isfinite(float(v)) for o in mesh_objects for vert in o.data.vertices for v in vert.co)
blend_count=sum(1 for o in mesh_objects if o.get('citygml_id'))
blend_ok=len(mesh_objects)>0 and blend_count>0 and finite_blend
def dimensions_match(objects):
    for b in data['buildings']:
        vertices=[obj.matrix_world @ vertex.co for obj in objects if obj.get('citygml_id')==b['id'] for vertex in obj.data.vertices]
        points=[point for ring in b['footprints'] for point in ring]
        if not vertices or not points: return False
        base=float(b.get('base_z_m',0.0)); expected=(min(p[0] for p in points),min(p[1] for p in points),base,max(p[0] for p in points),max(p[1] for p in points),base+float(b['height_m']))
        actual=(min(v.x for v in vertices),min(v.y for v in vertices),min(v.z for v in vertices),max(v.x for v in vertices),max(v.y for v in vertices),max(v.z for v in vertices))
        if any(abs(a-e)>0.02 for a,e in zip(actual,expected)): return False
    return True
blend_dimensions=dimensions_match(mesh_objects)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(glb))
glb_mesh=[o for o in bpy.data.objects if o.type=='MESH']
finite_glb=all(math.isfinite(float(v)) for o in glb_mesh for vert in o.data.vertices for v in vert.co)
ids={o.get('citygml_id') for o in glb_mesh if o.get('citygml_id')}
expected={b['id'] for b in data['buildings']}
glb_ok=len(glb_mesh)>0 and finite_glb and bool(ids & expected)
glb_dimensions=dimensions_match(glb_mesh)
result={'building_count_nonzero':bool(expected),'finite_source_coordinates':all(math.isfinite(v) for b in data['buildings'] for ring in b['footprints'] for p in ring for v in p),'blend_reopens_with_buildings':blend_ok,'glb_reimports_with_buildings':glb_ok,'all_expected_glb_buildings_present':expected.issubset(ids),'dimensions_preserved_to_2cm_in_blend':blend_dimensions,'dimensions_preserved_to_2cm_in_glb':glb_dimensions,'expected_buildings':len(expected),'blend_building_objects':blend_count,'glb_mesh_objects':len(glb_mesh)}
out.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print('Validation:',result)
