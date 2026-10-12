# KIBA REAL CITY

Python pipeline for building an editable Blender city from real CityGML. The initial area is a 500 m square around Kiba Park, Tokyo. No sample geometry is passed off as real data: fixtures are used only by automated tests.

## Requirements

- Python 3.10 or newer
- Blender 4.x with the bundled Python API and glTF 2.0 exporter
- Python packages in `requirements.txt`
- Official Koto City PLATEAU CityGML files (`bldg` GML); put extracted files under `data/raw/`. Keep source archives out of Git.

GDAL/OGR may be used to inspect files (`ogrinfo -ro -so file.gml`), but the pipeline reads CityGML directly so it does not depend on an assumed PLATEAU Converter CLI.

## Windows setup

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python scripts/check_environment.py
```

Set `BLENDER_EXE` to the Blender executable if `blender` is not on PATH. Discover/download an official Koto City package from the Geospatial Information Center catalog with `python scripts/download_data.py --list`, then use its exact package slug with `python scripts/download_data.py --package <slug>`. Or download and extract official CityGML beneath `data/raw/`. Then run:

```powershell
python scripts/inspect_citygml.py
python scripts/convert_data.py
python scripts/build_blender.py
python scripts/validate_output.py
```

Run the synthetic no-source-data round-trip check with `python tests/run_fixture.py`. Its building is explicitly labeled test-only and is never written to the production output folder.

`convert_data.py` inspects the configured center and square, computes intersecting 1 km third-level Japanese mesh codes, transforms EPSG:6677 coordinates into a shared local east/north/up frame, and writes filtered building footprints to `data/processed/buildings.json`. Buildings intersecting the square are clipped to its boundary. Their source IDs and height provenance are retained. The initial release supports CityGML building footprints and extruded block models; other feature types are reported as unavailable until a source is configured.

Outputs are `output/KIBA_REAL_CITY_v01.blend`, `output/KIBA_REAL_CITY_v01.glb`, `output/geo_reference.json`, and JSON/Markdown generation reports under `reports/`. Blender is run headlessly. The GLB is re-imported in a second Blender process for validation.

## Phase 2A: OSM roads and Kiba Park boundary

Phase 2A retrieves the live OpenStreetMap API map extract for the exact EPSG:6677 500 m square plus a 12 m query margin, then clips features back to the square. To reproduce:

```powershell
python scripts/download_phase2a_data.py
python scripts/convert_phase2a_osm.py
python scripts/compare_phase2a_map.py
python scripts/build_phase2a_blender.py
python scripts/validate_phase2a.py
```

The OSM API response declares the Open Data Commons Open Database License (ODbL) 1.0 and attribution `OpenStreetMap and contributors`; those values are preserved in scene and feature metadata. OSM is a live database, so the locally generated run report records retrieval/server time rather than an annual release. OSM highway centerlines do not usually encode width: explicit width tags are used where available; otherwise a highway-class estimate is recorded on each object. OSM provides no elevation for these features, so roads and park use the shared local origin and a nominal zero-ground display level. This does not alter Phase 1 building geometry.

The Kiba Park boundary is OSM multipolygon `relation/14273608`, tagged `木場公園` / `Kiba Park`; its OSM tags link to the Tokyo Metropolitan Park Association page. The local map-check PNG compares geometry with GSI standard-map tiles. See [LICENSE_DATA.md](LICENSE_DATA.md) for source terms, verification limits, and the publication status of generated assets. The detailed run report and map-check images are kept local while redistribution terms remain unresolved; this public commit contains the automated validation summary. The Phase 2A build writes new `KIBA_REAL_CITY_v02` files and refuses to overwrite existing v02 outputs; move aside those two files before deliberately rebuilding. It never writes the v01 BLEND or GLB.

## Reusable location configuration

Edit `config/kiba_park.json` to select another center, projected CRS, and square size. All features use the same projected local origin; Blender X is east, Y north, and Z up. `data/raw` is an ingestion location for manually downloaded official packages when automated catalog access is unavailable.

## Data and license

See [LICENSE_DATA.md](LICENSE_DATA.md) before publishing input data or generated outputs. The Koto City 2023 PLATEAU source terms and GSI tile terms used in this run could not be verified, so new derived models, references, reports with building attributes, and map imagery are intentionally not in this public Phase 2A commit. The two PLATEAU mesh ZIPs were already tracked before this commit; this commit does not add or modify them. Newly downloaded source files and local build outputs remain ignored by Git.
