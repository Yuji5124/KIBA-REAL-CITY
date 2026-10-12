"""Draw an OSM-vector context map comparing the old and expanded rectangles."""
from __future__ import annotations
import json, math
from pathlib import Path
from xml.etree import ElementTree as ET
from PIL import Image,ImageDraw,ImageFont
from pyproj import Transformer
from shapely.geometry import LineString,Polygon
from shapely.ops import unary_union
from phase3d_common import ROOT,ORIGIN,TO_LOCAL,relation_polygon

OUT=ROOT/'reports/KIBA_REAL_CITY_v05_extent_comparison.png'
def font(size,bold=False):
    candidates=(['/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc','/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'] if bold else
      ['/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc','/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'])
    for candidate in candidates:
        if Path(candidate).is_file():return ImageFont.truetype(candidate,size)
    return ImageFont.load_default()
def main():
    if OUT.exists():raise SystemExit(f'Refusing to overwrite {OUT.relative_to(ROOT)}')
    source=json.loads((ROOT/'data/processed/phase3d_source.json').read_text(encoding='utf-8'))
    data=json.loads((ROOT/'data/processed/phase3d_features.json').read_text(encoding='utf-8'))
    west,south,east,north=map(float,data['bounds_local_m'])
    width,height=1320,1580;margin=100;scale=min((width-2*margin)/(east-west),(height-2*margin)/(north-south))
    px=lambda x:round(margin+(x-west)*scale)
    py=lambda y:round(height-margin-(y-south)*scale)
    image=Image.new('RGB',(width,height),'#f4f5f1');draw=ImageDraw.Draw(image)
    raw=ET.parse(ROOT/'data/raw/kiba_phase3d_osm_map.osm').getroot()
    nodes={n.attrib['id']:(float(n.attrib['lon']),float(n.attrib['lat'])) for n in raw.findall('node')}
    ways=raw.findall('way')
    # OSM roadway and building vectors provide geographically anchored context;
    # no tile imagery is embedded in this graphic.
    for way in ways:
        tags={e.attrib['k']:e.attrib['v'] for e in way.findall('tag')}
        refs=[e.attrib['ref'] for e in way.findall('nd')]
        coords=[]
        for ref in refs:
            lonlat=nodes.get(ref)
            if lonlat:
                x,y=TO_LOCAL.transform(*lonlat);coords.append((x-ORIGIN[0],y-ORIGIN[1]))
        if tags.get('building') and len(coords)>=4 and coords[0]==coords[-1]:
            points=[(px(x),py(y)) for x,y in coords]
            draw.polygon(points,fill='#d5d7d2',outline='#b0b3ad')
    for way in ways:
        tags={e.attrib['k']:e.attrib['v'] for e in way.findall('tag')}
        if not tags.get('highway'):continue
        points=[]
        for nd in way.findall('nd'):
            lonlat=nodes.get(nd.attrib['ref'])
            if lonlat:
                x,y=TO_LOCAL.transform(*lonlat);points.append((px(x-ORIGIN[0]),py(y-ORIGIN[1])))
        if len(points)>1:draw.line(points,fill='#aab2b5',width=2)
    park=source['park']['bounds_local_m']
    # Draw relation components from full OSM multipolygons, including the area
    # outside the downloaded map crop.
    from shapely.geometry import Polygon as SPolygon
    def draw_geometry(geom,fill,outline,outline_width=3):
        geoms=[geom] if geom.geom_type=='Polygon' else list(getattr(geom,'geoms',[]))
        for poly in geoms:
            if poly.geom_type!='Polygon':continue
            pts=[(px(x),py(y)) for x,y in poly.exterior.coords]
            if fill:draw.polygon(pts,fill=fill)
            draw.line(pts,fill=outline,width=outline_width)
            for hole in poly.interiors:draw.line([(px(x),py(y)) for x,y in hole.coords],fill=outline,width=outline_width)
    museum_geom=relation_polygon(ROOT/'data/raw/kiba_phase3d_museum_relation.osm','12077221')[2]
    park_geom=relation_polygon(ROOT/'data/raw/kiba_phase3d_park_relation.osm','14273608')[2]
    draw_geometry(park_geom,'#b9d7a5','#709b5b',3)
    # redraw OSM roads above the light green park context
    for way in ways:
        tags={e.attrib['k']:e.attrib['v'] for e in way.findall('tag')}
        if tags.get('highway'):
            points=[]
            for nd in way.findall('nd'):
                lonlat=nodes.get(nd.attrib['ref'])
                if lonlat:
                    x,y=TO_LOCAL.transform(*lonlat);points.append((px(x-ORIGIN[0]),py(y-ORIGIN[1])))
            if len(points)>1:draw.line(points,fill='#aab2b5',width=2)
    draw_geometry(museum_geom,'#f1ad72','#ad5d22',4)
    old=[(-250,-250),(250,-250),(250,250),(-250,250),(-250,-250)]
    expanded=[(west,south),(east,south),(east,north),(west,north),(west,south)]
    draw.line([(px(x),py(y)) for x,y in expanded],fill='#145f9c',width=6)
    # dashed existing extent outline
    pts=[(px(x),py(y)) for x,y in old]
    for a,b in zip(pts,pts[1:]):
        dx=b[0]-a[0];dy=b[1]-a[1];length=math.hypot(dx,dy);steps=max(1,int(length/18))
        for i in range(0,steps,2):
            t0=i/steps;t1=min((i+1)/steps,1)
            draw.line((a[0]+dx*t0,a[1]+dy*t0,a[0]+dx*t1,a[1]+dy*t1),fill='#bd3c3c',width=5)
    # Title, north arrow, scale and attribution.
    draw.text((48,28),'木場公園 — 東京都現代美術館 | 範囲比較',font=font(32,True),fill='#18252c')
    draw.text((48,72),f'新範囲: {east-west:.1f} m × {north-south:.1f} m  |  背景: OpenStreetMap ベクター',font=font(20),fill='#34434a')
    nx,ny=width-90,145;draw.line((nx,ny+74,nx,ny),fill='#18252c',width=6);draw.polygon([(nx,ny-14),(nx-14,ny+15),(nx+14,ny+15)],fill='#18252c');draw.text((nx-13,ny-46),'N',font=font(22,True),fill='#18252c')
    bar=round(100*scale);bx,by=58,height-86;draw.line((bx,by,bx+bar,by),fill='#18252c',width=7);draw.line((bx,by-9,bx,by+9),fill='#18252c',width=4);draw.line((bx+bar,by-9,bx+bar,by+9),fill='#18252c',width=4);draw.text((bx,by-38),'100 m',font=font(19,True),fill='#18252c')
    legend_y=height-180
    draw.rectangle((55,legend_y,83,legend_y+22),outline='#bd3c3c',width=4);draw.text((98,legend_y-1),'既存 v04 範囲 (500 m × 500 m)',font=font(18),fill='#18252c')
    draw.rectangle((460,legend_y,488,legend_y+22),outline='#145f9c',width=5);draw.text((503,legend_y-1),'v05 拡張範囲',font=font(18),fill='#18252c')
    draw.rectangle((740,legend_y,768,legend_y+22),fill='#f1ad72',outline='#ad5d22',width=2);draw.text((782,legend_y-1),'東京都現代美術館',font=font(18),fill='#18252c')
    draw.rectangle((1050,legend_y,1078,legend_y+22),fill='#b9d7a5',outline='#709b5b',width=2);draw.text((1090,legend_y-1),'木場公園',font=font(18),fill='#18252c')
    draw.text((48,height-40),f'© OpenStreetMap contributors | 抽出: {source["osm_extract"]["retrieved_at_utc"]} | 実測標高を示す地形図ではありません',font=font(16),fill='#3e4c52')
    OUT.parent.mkdir(parents=True,exist_ok=True);image.save(OUT,optimize=True)
    print(f'Wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size} bytes)')
if __name__=='__main__':main()
