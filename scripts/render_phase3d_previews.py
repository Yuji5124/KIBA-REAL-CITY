"""Render four v05 views and an OSM-vector old/new extent comparison."""
from __future__ import annotations
import os,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PREVIEWS=[ROOT/'reports'/name for name in (
 'KIBA_REAL_CITY_v05_overview.png','KIBA_REAL_CITY_v05_museum.png',
 'KIBA_REAL_CITY_v05_kiba_bridge.png','KIBA_REAL_CITY_v05_top.png',
 'KIBA_REAL_CITY_v05_extent_comparison.png')]
def main():
    blender=os.environ.get('BLENDER_EXE') or shutil.which('blender')
    if not blender:raise SystemExit('Blender not found; set BLENDER_EXE or add Blender to PATH.')
    scene=ROOT/'output/KIBA_REAL_CITY_v05.blend';features=ROOT/'data/processed/phase3d_features.json'
    for path in (scene,features):
        if not path.is_file():raise SystemExit(f'Missing prerequisite: {path.relative_to(ROOT)}')
    existing=[p.relative_to(ROOT) for p in PREVIEWS if p.exists()]
    if existing:raise SystemExit('Refusing to overwrite previews: '+', '.join(map(str,existing)))
    subprocess.run([blender,'--background','--python',str(ROOT/'scripts/blender_render_phase3d.py'),'--',
       str(scene),str(ROOT/'reports'),str(features)],check=True,cwd=ROOT)
    subprocess.run([os.environ.get('PYTHON_EXE') or sys.executable,
       str(ROOT/'scripts/render_phase3d_extent_overlay.py')],check=True,cwd=ROOT)
    missing=[p.relative_to(ROOT) for p in PREVIEWS if not p.is_file() or p.stat().st_size==0]
    if missing:raise SystemExit('Missing/empty previews: '+', '.join(map(str,missing)))
    print('Preview byte sizes:')
    for p in PREVIEWS:print(f'{p.relative_to(ROOT)}: {p.stat().st_size}')
if __name__=='__main__':main()
