"""Phase 3D extent and OSM source geometry helpers."""
from __future__ import annotations
import sys
from pathlib import Path
from xml.etree import ElementTree as ET
from pyproj import Transformer
from shapely.geometry import Polygon, box
from shapely.ops import unary_union

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from common import mesh_1km_codes

ORIGIN=(-2302.317826321731,-36106.717222697174)
OLD_BOUNDS=(-250.0,-250.0,250.0,250.0)
MUSEUM_RELATION='12077221'
PARK_RELATION='14273608'
TO_LOCAL=Transformer.from_crs('EPSG:4326','EPSG:6677',always_xy=True)
TO_GEO=Transformer.from_crs('EPSG:6677','EPSG:4326',always_xy=True)

def tags(element):
    return {item.attrib['k']:item.attrib['v'] for item in element.findall('tag')}

def relation_polygon(xml_path:Path,relation_id:str):
    root=ET.parse(xml_path).getroot()
    elements={f'{e.tag.rsplit("}",1)[-1]}|{e.attrib.get("id","")}':e for e in root}
    relation=elements.get(f'relation|{relation_id}')
    if relation is None: raise ValueError(f'relation/{relation_id} absent from {xml_path}')
    roles={'outer':[],'inner':[]}
    for member in relation.findall('member'):
        if member.attrib.get('type')!='way': continue
        way=elements.get('way|'+member.attrib['ref'])
        if way is None: raise ValueError(f'Missing member way/{member.attrib["ref"]} in relation/{relation_id}')
        points=[]
        for nd in way.findall('nd'):
            node=elements.get('node|'+nd.attrib['ref'])
            if node is None: raise ValueError(f'Missing node/{nd.attrib["ref"]} in way/{member.attrib["ref"]}')
            x,y=TO_LOCAL.transform(float(node.attrib['lon']),float(node.attrib['lat']))
            points.append((x-ORIGIN[0],y-ORIGIN[1]))
        if len(points)<4 or points[0]!=points[-1]:
            raise ValueError(f'Incomplete closed ring way/{member.attrib["ref"]}')
        roles[member.attrib.get('role','')].append(Polygon(points))
    if not roles['outer']: raise ValueError(f'relation/{relation_id} has no outer ring')
    outers=unary_union(roles['outer'])
    inners=unary_union(roles['inner']) if roles['inner'] else Polygon()
    return relation,tags(relation),outers.difference(inners)

def target_extent(museum_xml:Path,park_xml:Path):
    museum,museum_tags,museum_geom=relation_polygon(museum_xml,MUSEUM_RELATION)
    park,park_tags,park_geom=relation_polygon(park_xml,PARK_RELATION)
    if museum_tags.get('name')!='東京都現代美術館' or museum_tags.get('tourism')!='museum':
        raise ValueError('Museum relation identity did not match expected OSM tags.')
    if park_tags.get('name')!='木場公園' or park_tags.get('leisure')!='park':
        raise ValueError('Kiba Park relation identity did not match expected OSM tags.')
    # No independent museum parcel polygon is mapped. Include the whole mapped
    # Kiba Park boundary, which contains the museum relation, and the original
    # v04 square. This is the smallest axis-aligned rectangle for those data.
    geometry=unary_union([box(*OLD_BOUNDS),park_geom,museum_geom])
    return {'museum_relation':museum,'museum_tags':museum_tags,'museum_geometry':museum_geom,
            'park_relation':park,'park_tags':park_tags,'park_geometry':park_geom,
            'bounds_local_m':tuple(float(x) for x in geometry.bounds),
            'museum_bounds_local_m':tuple(float(x) for x in museum_geom.bounds),
            'park_bounds_local_m':tuple(float(x) for x in park_geom.bounds)}

def projected_bounds_to_wgs84(bounds_abs,pad_m=0.0,steps=100):
    west,south,east,north=bounds_abs
    west-=pad_m; south-=pad_m; east+=pad_m; north+=pad_m
    points=[]
    for i in range(steps+1):
        f=i/steps
        for x,y in ((west+(east-west)*f,south),(west+(east-west)*f,north),
                    (west,south+(north-south)*f),(east,south+(north-south)*f)):
            points.append(TO_GEO.transform(x,y))
    return (min(x for x,y in points),min(y for x,y in points),
            max(x for x,y in points),max(y for x,y in points))

def extent_metadata(bounds_local):
    abs_bounds=(ORIGIN[0]+bounds_local[0],ORIGIN[1]+bounds_local[1],
                ORIGIN[0]+bounds_local[2],ORIGIN[1]+bounds_local[3])
    lonlat=projected_bounds_to_wgs84(abs_bounds)
    meshes=mesh_1km_codes(abs_bounds)
    return {'bounds_local_m':list(bounds_local),'bounds_projected_epsg6677_m':list(abs_bounds),
            'bounds_wgs84_lonlat':list(lonlat),
            'width_m':abs_bounds[2]-abs_bounds[0],'height_m':abs_bounds[3]-abs_bounds[1],
            'mesh_codes_1km':meshes}
