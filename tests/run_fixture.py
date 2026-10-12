from __future__ import annotations
import json, os, subprocess, sys, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from common import load_config,area,mesh_1km_codes

def main():
    cfg=load_config(); bounds,_=area(cfg); meshes=mesh_1km_codes(bounds)
    assert meshes==['53394604','53394614'],f'Unexpected mesh cells: {meshes}'
    blender=os.environ.get('BLENDER_EXE','blender')
    with tempfile.TemporaryDirectory(prefix='kiba-fixture-') as td:
        t=Path(td); src=t/'fixture.json'; blend=t/'fixture.blend'; glb=t/'fixture.glb'; result=t/'validation.json'
        subprocess.run([sys.executable,str(ROOT/'tests'/'make_fixture.py'),str(src)],check=True)
        subprocess.run([blender,'--background','--python',str(ROOT/'scripts'/'blender_scene.py'),'--',str(src),str(blend),str(glb)],check=True,cwd=ROOT)
        subprocess.run([blender,'--background','--python',str(ROOT/'scripts'/'blender_validate.py'),'--',str(blend),str(glb),str(src),str(result)],check=True,cwd=ROOT)
        checks=json.loads(result.read_text(encoding='utf-8'))
        assert all(checks.get(k) for k in ['building_count_nonzero','finite_source_coordinates','blend_reopens_with_buildings','glb_reimports_with_buildings','all_expected_glb_buildings_present']),checks
        print(f'Fixture round trip passed; meshes={meshes}; checks={checks}')

if __name__=='__main__':main()
