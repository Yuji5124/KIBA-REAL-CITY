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

## Phase 2B: mapped park vegetation, paths, water, and bridges

Phase 2B uses the saved real OSM extract and requires the locally generated v02 BLEND. It does not fabricate tree locations or green polygons. In the 2026-10-12 extract it found 33 tagged tree points (no species/height/crown dimensions), 17 visible mapped green polygons, 14 water features, and 2 mapped bridge footprints including Kiba Park Bridge. Unknown tree shape/size, linear-water width, and bridge display elevation are explicitly labeled estimates on each Blender object.

```powershell
python scripts/convert_phase2b_osm.py
python scripts/build_phase2b_blender.py
python scripts/validate_phase2b.py
python scripts/render_phase2b_preview.py
```

The build preserves all 233 building meshes, all 236 road/path feature IDs and meshes, and the Phase 2A park boundary. It moves 108 existing park walking corridors to `08_PARK_PATHS` without changing their geometry, then adds separate `04_TREES`, `07_GRASS`, `09_WATER`, and `06_BRIDGES` features. Outputs are `output/KIBA_REAL_CITY_v03.blend`, `output/KIBA_REAL_CITY_v03.glb`, `output/geo_reference_v03.json`, and local reports/previews under `reports/`. The v03 build refuses to overwrite existing files. The local output remains excluded from this public commit while data redistribution terms are reviewed; see [LICENSE_DATA.md](LICENSE_DATA.md).

## Reusable location configuration

Edit `config/kiba_park.json` to select another center, projected CRS, and square size. All features use the same projected local origin; Blender X is east, Y north, and Z up. `data/raw` is an ingestion location for manually downloaded official packages when automated catalog access is unavailable.

## Data and license

See [LICENSE_DATA.md](LICENSE_DATA.md) before publishing input data or generated outputs. The Koto City 2023 PLATEAU source terms and GSI tile terms used in this run could not be verified, so new derived models, references, reports with building attributes, and map imagery are intentionally not in the public Phase 2A commit. The two PLATEAU mesh ZIPs were already tracked before that commit; this documentation does not add or modify them. Newly downloaded source files and local build outputs remain ignored by Git.

# Phase 3 visual revision (local)

Phase 3 creates a new v04 from the locally stored Phase 2B v03
outputs. It verifies the v03 BLEND and GLB SHA-256 hashes before opening the
scene, refuses to overwrite any existing v04 files, and keeps v01-v03 intact.

```bash
python scripts/build_phase3.py
python scripts/validate_phase3.py
python scripts/render_phase3_preview.py
```

This writes `output/KIBA_REAL_CITY_v04.blend`, `output/KIBA_REAL_CITY_v04.glb`,
`output/geo_reference_v04.json`, `reports/phase3_report.json`,
`reports/phase3_report.md`, and `reports/KIBA_REAL_CITY_v04_preview.png`.
The model outputs remain local because the composite-data redistribution
conditions have not been resolved; they are ignored by Git.

Materials change appearance only. The 33 Phase 2B tree source meshes and
coordinates are retained hidden in `99_REFERENCE`; editable display trees are
separate meshes at those same OSM positions. Their species and forms are not
asserted as measured data. The Phase 3 validator compares IDs, world-space
vertices, faces, and tree positions with v03, then reimports the GLB and checks
building bounds and tree source IDs.

## Phase 3D: Kiba Park to the Museum of Contemporary Art Tokyo

Phase 3D extends the model north to the real mapped Tokyo Metropolitan Museum of
Contemporary Art while including the whole mapped Kiba Park multipolygon. The
smallest EPSG:6677 axis-aligned rectangle that includes both and the full v04
500 m square measures approximately 505.24 m east-west by 990.86 m north-south.
It retains the original v04 projected origin. The museum was identified by OSM
`relation/12077221` and matched to PLATEAU CityGML building
`bldg_41c3fd1a-c5a7-4e60-b4dc-e51c08ea895a`; the source is real 2023 LOD1.
Its LOD1 solid height (16.627 m) differs from `measuredHeight` (24.1 m), so both
values and the difference are kept in the report. The official 2025 extent
query reports no LOD2 CityGML building feature in mesh `53394614`; the listed
2025 LOD2 3D Tiles were not used because their asset host was inaccessible.

The v05 build requires the existing local v04 files, the two already downloaded
Koto mesh GMLs, and a fresh OSM extract. It refuses to overwrite v05 output or
preview files. The build verifies the immutable v04 BLEND/GLB hashes before
starting. Original v04 geodata stays intact in the scene; added building
continuations, tree visuals, and overlap-partitioned display surfaces are
separate objects. The new flat ground plane is presentation-only and is not
measured terrain.

```powershell
python scripts/download_phase3d_data.py
python scripts/inspect_phase3d_plateau.py
python scripts/convert_phase3d_buildings.py
python scripts/prepare_phase3d_features.py
python scripts/prepare_phase3d_display_surfaces.py
python scripts/build_phase3d.py
python scripts/render_phase3d_previews.py
python scripts/validate_phase3d.py
```

The outputs are `output/KIBA_REAL_CITY_v05.blend`,
`output/KIBA_REAL_CITY_v05.glb`, `output/geo_reference_v05.json`, the Phase 3D
JSON/Markdown report, four Blender renders (overview, museum, Kiba Park Bridge,
and top view), and an OSM-vector map comparing old/new extents. The extent map
includes OpenStreetMap attribution and does not use GSI map tiles. Data-derived
outputs, source extracts, and previews remain local; PLATEAU dataset-specific
terms and independent access to the ODbL text remain unverified. See
[LICENSE_DATA.md](LICENSE_DATA.md) before distributing them. The validation
compares per-object source IDs and world-space vertex/face hashes between v04
and v05, checks the original tree positions, and reimports the GLB.
