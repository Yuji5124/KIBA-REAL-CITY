"""Create a diagnostic overlay of the OSM extract against GSI standard map tiles."""
from __future__ import annotations
import json, math, sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from PIL import Image, ImageDraw, ImageFont
from pyproj import Transformer
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, load_config, area, write_json

ZOOM=17
TEMPLATE='https://cyberjapandata.gsi.go.jp/xyz/std/{z}/{x}/{y}.png'

def lonlat_pixel(lon,lat):
    scale=256*(2**ZOOM)
    x=(lon+180.0)/360.0*scale
    lat_rad=math.radians(lat)
    y=(1.0-math.asinh(math.tan(lat_rad))/math.pi)/2.0*scale
    return x,y

def main():
    cfg=load_config(); (west,south,east,north),center=area(cfg); half=cfg['extent_m']/2
    inv=Transformer.from_crs(cfg['local_crs'],'EPSG:4326',always_xy=True)
    corners=[inv.transform(x,y) for x,y in ((west,south),(west,north),(east,south),(east,north))]
    pix=[lonlat_pixel(lon,lat) for lon,lat in corners]
    n=2**ZOOM; tile_min_x=max(0,int(min(x for x,y in pix)//256)-1); tile_max_x=min(n-1,int(max(x for x,y in pix)//256)+1)
    tile_min_y=max(0,int(min(y for x,y in pix)//256)-1); tile_max_y=min(n-1,int(max(y for x,y in pix)//256)+1)
    cache=ROOT/'data/raw/gsi_std_z17'; cache.mkdir(parents=True,exist_ok=True)
    canvas=Image.new('RGB',((tile_max_x-tile_min_x+1)*256,(tile_max_y-tile_min_y+1)*256),(245,245,245))
    tiles=[]
    for ty in range(tile_min_y,tile_max_y+1):
        for tx in range(tile_min_x,tile_max_x+1):
            url=TEMPLATE.format(z=ZOOM,x=tx,y=ty); path=cache/f'{tx}_{ty}.png'
            if not path.exists():
                req=Request(url,headers={'User-Agent':'KIBA-REAL-CITY/Phase2A map QA'})
                with urlopen(req,timeout=30) as response:
                    if response.status!=200: raise SystemExit(f'GSI map tile request failed: HTTP {response.status}')
                    path.write_bytes(response.read())
            tile=Image.open(path).convert('RGB')
            canvas.paste(tile,((tx-tile_min_x)*256,(ty-tile_min_y)*256))
            tiles.append({'url':url,'x':tx,'y':ty,'bytes':path.stat().st_size})
    overlay=Image.new('RGBA',canvas.size,(0,0,0,0)); draw=ImageDraw.Draw(overlay,'RGBA')
    def xy(local_x,local_y):
        lon,lat=inv.transform(center[0]+local_x,center[1]+local_y)
        px,py=lonlat_pixel(lon,lat)
        return (px-tile_min_x*256,py-tile_min_y*256)
    features=json.loads((ROOT/'data/processed/phase2a_features.json').read_text(encoding='utf-8'))
    for road in features['roads']:
        for poly in road['polygons']:
            outer=[xy(x,y) for x,y in poly['exterior']]
            if len(outer)>=3: draw.polygon(outer,fill=(230,25,25,100),outline=(180,0,0,220))
    for poly in features['park']['polygons']:
        outer=[xy(x,y) for x,y in poly['exterior']]
        if len(outer)>=3: draw.polygon(outer,fill=(0,220,20,70),outline=(0,130,0,255),width=3)
        for ring in poly.get('interiors',[]): draw.polygon([xy(x,y) for x,y in ring],fill=(0,0,0,0),outline=(0,130,0,255),width=3)
    buildings=json.loads((ROOT/'data/processed/buildings.json').read_text(encoding='utf-8'))
    for building in buildings['buildings']:
        for ring in building['footprints']:
            points=[xy(x,y) for x,y in ring]
            if len(points)>=3: draw.line(points,fill=(115,0,180,245),width=2)
    edge=[xy(-half,-half),xy(-half,half),xy(half,half),xy(half,-half),xy(-half,-half)]
    draw.line(edge,fill=(20,70,255,255),width=3)
    result=Image.alpha_composite(canvas.convert('RGBA'),overlay).convert('RGB')
    margin=10.0
    context=[inv.transform(center[0]+x,center[1]+y) for x,y in ((-half-margin,-half-margin),(-half-margin,half+margin),(half+margin,-half-margin),(half+margin,half+margin))]
    context_px=[lonlat_pixel(lon,lat) for lon,lat in context]
    crop=(max(0,int(min(x for x,y in context_px)-tile_min_x*256)),max(0,int(min(y for x,y in context_px)-tile_min_y*256)),
          min(result.width,int(max(x for x,y in context_px)-tile_min_x*256)),min(result.height,int(max(y for x,y in context_px)-tile_min_y*256)))
    result=result.crop(crop)
    caption=Image.new('RGB',(result.width,30),(255,255,255)); ImageDraw.Draw(caption).text((8,8),'Basemap: GSI standard map tiles | Overlays: OSM roads/park; Phase 1 PLATEAU buildings',fill=(25,25,25),font=ImageFont.load_default())
    result=Image.new('RGB',(result.width,result.height+30),(255,255,255)); result.paste(caption,(0,0)); result.paste(Image.alpha_composite(canvas.convert('RGBA'),overlay).convert('RGB').crop(crop),(0,30))
    out=ROOT/'reports/phase2a_map_check.png'; out.parent.mkdir(parents=True,exist_ok=True); result.save(out)
    write_json('data/processed/phase2a_map_tiles.json',{
        'dataset':'GSI tiles (standard map), used only as independent visual QA backdrop',
        'retrieved_at_utc':datetime.now(timezone.utc).isoformat(),'tile_url_template':TEMPLATE,
        'zoom':ZOOM,'tile_count':len(tiles),'tiles':tiles,'output':str(out.relative_to(ROOT)),
        'license_terms_reference':'https://www.gsi.go.jp/kikakuchousei/kikakuchousei40182.html',
        'attribution':'地理院タイル（標準地図）','coordinate_alignment':'OSM WGS84 was projected to EPSG:6677, then transformed back to EPSG:4326 and Web Mercator pixels for this overlay.'})
    print(f'Wrote {out.relative_to(ROOT)} using {len(tiles)} GSI tiles at z{ZOOM}')

if __name__=='__main__': main()
