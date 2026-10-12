"""Discover and download official Koto City packages from the Geospatial Information Center CKAN catalog."""
from __future__ import annotations
import argparse, json, re, sys, urllib.parse, urllib.request, zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/'scripts'))
from common import load_config
API='https://www.geospatial.jp/ckan/api/3/action/package_search'

def api_json(url):
    req=urllib.request.Request(url,headers={'User-Agent':'KibaRealCity/0.1 (open source CityGML tooling)'})
    with urllib.request.urlopen(req,timeout=60) as response: return json.load(response)

def search(query):
    url=API+'?'+urllib.parse.urlencode({'q':query,'rows':100})
    payload=api_json(url)
    if not payload.get('success'): raise RuntimeError('CKAN package search returned success=false')
    return payload['result'].get('results',[])

def safe_extract(archive,dest):
    root=dest.resolve(); dest.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(archive) as z:
        for item in z.infolist():
            target=(dest/item.filename).resolve()
            if target!=root and root not in target.parents: raise RuntimeError(f'Unsafe ZIP path rejected: {item.filename}')
        z.extractall(dest)

def main():
    cfg=load_config(); parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package',help='Exact CKAN package slug; defaults to listing candidates')
    parser.add_argument('--list',action='store_true',help='List packages matching Koto City and PLATEAU')
    args=parser.parse_args()
    packages=search('江東区 PLATEAU')
    packages=[p for p in packages if '江東区' in (p.get('title','')+' '+p.get('name','')) and 'plateau' in (p.get('title','')+' '+p.get('name','')+' '+' '.join(t.get('name','') for t in p.get('tags',[]))).lower()]
    if args.list or not args.package:
        if not packages: print('No matching catalog records. Check official PLATEAU download pages or place an official extracted CityGML package in data/raw/.')
        for p in packages:
            print(f"{p.get('name')} | {p.get('title')} | license={p.get('license_title')} | resources={len(p.get('resources',[]))}")
            for r in p.get('resources',[]): print(f"  {r.get('format','?')} | {r.get('name','')} | {r.get('url','')}")
        return
    package=next((p for p in packages if p.get('name')==args.package),None)
    if package is None: raise SystemExit(f"Package slug {args.package!r} was not in the official Koto City PLATEAU search. Run --list.")
    candidates=[r for r in package.get('resources',[]) if r.get('url') and (r.get('format','').lower() in {'zip','application/zip'} or urllib.parse.urlparse(r['url']).path.lower().endswith('.zip'))]
    if not candidates: raise SystemExit('Selected package has no ZIP resources. Download from its official resource page and extract under data/raw/.')
    raw=ROOT/cfg['input_dir']; raw.mkdir(parents=True,exist_ok=True)
    for i,r in enumerate(candidates,1):
        url=r['url']; name=Path(urllib.parse.urlparse(url).path).name or f"{package['name']}-{i}.zip"
        name=re.sub(r'[^A-Za-z0-9._-]+','_',name); archive=raw/name
        if not archive.exists():
            req=urllib.request.Request(url,headers={'User-Agent':'KibaRealCity/0.1'})
            with urllib.request.urlopen(req,timeout=180) as response,archive.open('wb') as out:
                while chunk:=response.read(1024*1024): out.write(chunk)
        target=raw/package['name']/str(i); safe_extract(archive,target)
        print(f"Downloaded and extracted {archive.relative_to(ROOT)} -> {target.relative_to(ROOT)}")
    print(f"Package: {package.get('title')}\nLicense: {package.get('license_title')}\nCatalog URL: {package.get('url')}\nSource metadata: {json.dumps(package.get('extras',[]),ensure_ascii=False)}")

if __name__=='__main__': main()
