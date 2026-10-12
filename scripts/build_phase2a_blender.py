from __future__ import annotations
import os, shutil, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def main():
    exe=os.environ.get('BLENDER_EXE') or shutil.which('blender')
    if not exe: raise SystemExit('Blender not found. Add it to PATH or set BLENDER_EXE.')
    features=ROOT/'data/processed/phase2a_features.json'
    source=ROOT/'output/KIBA_REAL_CITY_v01.blend'
    if not features.is_file() or not source.is_file(): raise SystemExit('Missing converted real OSM data or Phase 1 BLEND.')
    subprocess.run([exe,'--background','--python',str(ROOT/'scripts/blender_phase2a.py'),'--',str(features),str(source),str(ROOT/'output')],check=True,cwd=ROOT)

if __name__=='__main__': main()
