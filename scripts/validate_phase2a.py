from __future__ import annotations
import json, os, shutil, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def main():
    exe=os.environ.get('BLENDER_EXE') or shutil.which('blender')
    if not exe: raise SystemExit('Blender not found. Add it to PATH or set BLENDER_EXE.')
    v01=ROOT/'output/KIBA_REAL_CITY_v01.blend'; v02=ROOT/'output/KIBA_REAL_CITY_v02.blend'; glb=ROOT/'output/KIBA_REAL_CITY_v02.glb'
    out=ROOT/'reports/phase2a_validation.json'; out.parent.mkdir(parents=True,exist_ok=True)
    subprocess.run([exe,'--background','--python',str(ROOT/'scripts/blender_validate_phase2a.py'),'--',str(v01),str(v02),str(glb),str(out)],check=True,cwd=ROOT,stdout=(ROOT/'reports/phase2a_blender_validation.log').open('w'),stderr=subprocess.STDOUT)
    result=json.loads(out.read_text(encoding='utf-8'))
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__': main()
