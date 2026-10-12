"""Render the saved v03 overview camera to a local, ignored preview PNG."""
from __future__ import annotations
import os, shutil, subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
    exe=os.environ.get('BLENDER_EXE') or shutil.which('blender')
    blend=ROOT/'output/KIBA_REAL_CITY_v03.blend'; preview=ROOT/'reports/KIBA_REAL_CITY_v03_preview.png'
    if not exe: raise SystemExit('Blender not found. Add it to PATH or set BLENDER_EXE.')
    if not blend.is_file(): raise SystemExit('Missing output/KIBA_REAL_CITY_v03.blend.')
    if preview.exists(): raise SystemExit('Preview already exists; refusing to overwrite.')
    expr="import bpy; from mathutils import Vector; s=bpy.context.scene; c=s.camera; c.location=(390,-470,480); d=Vector((0,0,0))-c.location; c.rotation_euler=d.to_track_quat('-Z','Y').to_euler(); c.data.lens=48; s.render.engine='BLENDER_EEVEE_NEXT'; s.render.resolution_x=1600; s.render.resolution_y=1200; s.render.resolution_percentage=100; s.render.image_settings.file_format='PNG'; s.render.filepath=r'"+str(preview)+"'; bpy.ops.render.render(write_still=True)"
    subprocess.run([exe,'--background',str(blend),'--python-expr',expr],check=True,cwd=ROOT)
    if not preview.is_file() or preview.stat().st_size < 10000: raise SystemExit('Preview render is missing or unexpectedly small.')
    print(f'Wrote {preview.relative_to(ROOT)} ({preview.stat().st_size} bytes)')
if __name__=='__main__': main()
