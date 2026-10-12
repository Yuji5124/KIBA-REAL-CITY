from __future__ import annotations
import sys
from pathlib import Path
from xml.etree import ElementTree as ET
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from common import load_config

def local(tag): return tag.rsplit('}', 1)[-1]

def main():
    cfg=load_config(); files=sorted(p for p in (ROOT/cfg['input_dir']).rglob('*') if p.suffix.lower() in {'.gml','.xml'})
    if not files: raise SystemExit(f"No CityGML files found under {cfg['input_dir']}; obtain and extract the official Koto City package there.")
    for f in files:
        root=ET.parse(f).getroot()
        names={local(e.tag) for e in root.iter()}
        buildings=sum(local(e.tag)=='Building' for e in root.iter())
        srs=sorted({e.attrib.get('srsName') for e in root.iter() if e.attrib.get('srsName')})
        print(f"{f.relative_to(ROOT)}: buildings={buildings}, srsName={srs[:5]}, feature types={sorted(names & {'Building','Road','Railway','ReliefFeature','PlantCover','SolitaryVegetationObject','Bridge'})}")

if __name__=='__main__': main()
