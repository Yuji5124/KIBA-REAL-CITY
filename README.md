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

## Reusable location configuration

Edit `config/kiba_park.json` to select another center, projected CRS, and square size. All features use the same projected local origin; Blender X is east, Y north, and Z up. `data/raw` is an ingestion location for manually downloaded official packages when automated catalog access is unavailable.

## Data and license

Use official Project PLATEAU Koto City CityGML and preserve its attribution and license terms with any redistribution. The pipeline records the configured dataset citation and source URLs in its report. Check the source package's release year, LOD, CRS, vertical datum, and license metadata before processing; these are read from source metadata where present and must not be guessed. No source data is committed to Git.
