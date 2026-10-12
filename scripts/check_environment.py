from __future__ import annotations
import os, shutil, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from common import load_config, area, mesh_1km_codes

def main():
    import pyproj, shapely
    cfg = load_config(); bounds, center = area(cfg)
    blender = os.environ.get('BLENDER_EXE') or shutil.which('blender')
    if blender:
        probe=subprocess.run([blender,'--background','--python-expr',"import bpy; print('BLENDER_VERSION=' + bpy.app.version_string)"],capture_output=True,text=True,check=True)
        version=next((line.split('=',1)[1] for line in probe.stdout.splitlines() if line.startswith('BLENDER_VERSION=')),'available')
    else: version='not found (set BLENDER_EXE)'
    print(f"Blender: {version}")
    print(f"pyproj: {pyproj.__version__}; Shapely: {shapely.__version__}")
    print(f"Blender executable: {blender or 'not found (set BLENDER_EXE)'}")
    print(f"Center projected ({cfg['local_crs']}): {center[0]:.3f}, {center[1]:.3f}")
    print(f"Square bounds: {bounds}")
    print(f"Intersecting 1 km mesh codes: {', '.join(mesh_1km_codes(bounds))}")
    if not list((ROOT / cfg['input_dir']).rglob('*.gml')) and not list((ROOT / cfg['input_dir']).rglob('*.xml')):
        print(f"No source CityGML found under {cfg['input_dir']} yet.")

if __name__ == '__main__': main()
