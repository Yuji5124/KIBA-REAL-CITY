from __future__ import annotations
import os, shutil, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from common import load_config

def main():
    cfg=load_config(); exe=os.environ.get('BLENDER_EXE') or shutil.which('blender')
    if not exe: raise SystemExit('Blender not found. Add it to PATH or set BLENDER_EXE.')
    data=ROOT/cfg['processed_file']
    if not data.exists(): raise SystemExit(f'{data.relative_to(ROOT)} is missing; run python scripts/convert_data.py first.')
    for key in ['blend_file','glb_file']:(ROOT/cfg[key]).parent.mkdir(parents=True,exist_ok=True)
    cmd=[exe,'--background','--python',str(ROOT/'scripts/blender_scene.py'),'--',str(data),str(ROOT/cfg['blend_file']),str(ROOT/cfg['glb_file'])]
    subprocess.run(cmd,check=True,cwd=ROOT)
    print(f"Created {cfg['blend_file']} and {cfg['glb_file']}")

if __name__=='__main__':main()
