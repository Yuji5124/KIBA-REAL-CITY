"""Build a new local v04 visual scene from v03; never overwrite prior versions."""
from __future__ import annotations
import hashlib, os, shutil, subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def sha256(path:Path)->str:
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''): digest.update(block)
    return digest.hexdigest()

def main():
    exe=os.environ.get('BLENDER_EXE') or shutil.which('blender')
    source=ROOT/'output/KIBA_REAL_CITY_v03.blend'
    expected={
        'KIBA_REAL_CITY_v03.blend':'965e1f4b7b9336cff21eec56c0fc87c5f24c600c24b92d79abdc40d78a54af37',
        'KIBA_REAL_CITY_v03.glb':'a901bdd6db765b799e9cc7be55dcec494fe11593a6a79b80e7fbeaca5ded2574'}
    if not exe: raise SystemExit('Blender not found. Add it to PATH or set BLENDER_EXE.')
    if not source.is_file(): raise SystemExit('Missing output/KIBA_REAL_CITY_v03.blend.')
    for name,digest in expected.items():
        path=ROOT/'output'/name
        if not path.is_file() or sha256(path)!=digest:
            raise SystemExit(f'Immutable Phase 2B source failed SHA-256 check: {name}')
    destinations=(ROOT/'output/KIBA_REAL_CITY_v04.blend',ROOT/'output/KIBA_REAL_CITY_v04.glb',
                  ROOT/'output/geo_reference_v04.json')
    if any(p.exists() for p in destinations):
        # A previous authorized attempt may have stopped between BLEND and
        # GLB export. Only discard this task's incomplete pair; complete v04
        # outputs remain protected from overwrite.
        present=[p for p in destinations if p.exists()]
        if len(present)==len(destinations) or destinations[1].exists():
            raise SystemExit('v04 output exists; refusing to overwrite.')
        for path in present:
            path.unlink()
    subprocess.run([exe,'--background','--python',str(ROOT/'scripts/blender_phase3.py'),
                    '--',str(source),str(ROOT/'output'),str(destinations[2])],check=True,cwd=ROOT)
    expected_outputs=destinations[:2]+(destinations[2],)
    missing=[p.relative_to(ROOT) for p in expected_outputs if not p.is_file() or p.stat().st_size==0]
    if missing:
        raise SystemExit('Blender did not create all requested outputs: '+', '.join(map(str,missing)))

if __name__=='__main__': main()
