"""Build v03 locally from real Phase 2A/2B inputs; never overwrites v01/v02/v03."""
from __future__ import annotations
import json, os, shutil, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def main():
    exe=os.environ.get('BLENDER_EXE') or shutil.which('blender')
    if not exe: raise SystemExit('Blender not found. Add it to PATH or set BLENDER_EXE.')
    features=ROOT/'data/processed/phase2b_features.json'
    v02=ROOT/'output/KIBA_REAL_CITY_v02.blend'
    v03=ROOT/'output/KIBA_REAL_CITY_v03.blend'; glb=ROOT/'output/KIBA_REAL_CITY_v03.glb'
    geo=ROOT/'output/geo_reference_v03.json'
    for p in (features,v02):
        if not p.is_file(): raise SystemExit(f'Missing input: {p.relative_to(ROOT)}')
    for p in (v03,glb,geo):
        if p.exists(): raise SystemExit(f'Refusing to overwrite existing output: {p.relative_to(ROOT)}')
    subprocess.run([exe,'--background','--python',str(ROOT/'scripts/blender_phase2b.py'),'--',str(features),str(v02),str(ROOT/'output'),str(geo)],check=True,cwd=ROOT)

if __name__=='__main__': main()
