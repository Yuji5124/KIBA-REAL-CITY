"""Create local Phase 3D outputs from the preserved v04 plus prepared real data."""
from __future__ import annotations
import hashlib, json, os, shutil, subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
EXPECTED_V04={
 'KIBA_REAL_CITY_v04.blend':'377f26df9954f5c19b9de46c830c01b36773653b8dce88f0d9c524377e23a3ed',
 'KIBA_REAL_CITY_v04.glb':'73fe7e7af28b4259cfc2a62552b803963b8345eb19131e1355a8a92dd6a9d102'}
def sha256(path:Path)->str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()
def main():
    blender=os.environ.get('BLENDER_EXE') or shutil.which('blender')
    if not blender:raise SystemExit('Blender not found; set BLENDER_EXE or add Blender to PATH.')
    for name,digest in EXPECTED_V04.items():
        path=ROOT/'output'/name
        if not path.is_file() or sha256(path)!=digest:raise SystemExit(f'Immutable v04 SHA-256 check failed: {name}')
    inputs=(ROOT/'data/processed/phase3d_features.json',ROOT/'data/processed/phase3d_display_surfaces.json')
    for path in inputs:
        if not path.is_file():raise SystemExit(f'Missing prepared source: {path.relative_to(ROOT)}')
    output=ROOT/'output/KIBA_REAL_CITY_v05.blend';glb=ROOT/'output/KIBA_REAL_CITY_v05.glb'
    geo=ROOT/'output/geo_reference_v05.json'
    if any(p.exists() for p in (output,glb,geo)):
        raise SystemExit('A v05 output already exists; refusing to overwrite.')
    subprocess.run([blender,'--background','--python',str(ROOT/'scripts/blender_phase3d.py'),'--',
      str(ROOT/'output/KIBA_REAL_CITY_v04.blend'),*(str(p) for p in inputs),
      str(ROOT/'output'),str(geo)],check=True,cwd=ROOT)
    missing=[p.relative_to(ROOT) for p in (output,glb,geo) if not p.is_file() or p.stat().st_size==0]
    if missing:raise SystemExit('Blender failed to create complete outputs: '+', '.join(map(str,missing)))
    print(json.dumps({'v04_sha256':EXPECTED_V04,'outputs_bytes':{p.name:p.stat().st_size for p in (output,glb,geo)}},indent=2))
if __name__=='__main__':main()
