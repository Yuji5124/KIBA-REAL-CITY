# Data sources, attribution, and publication status

This file records what was checked for Phase 2A. It does not grant rights beyond the source providers' terms.

## Project PLATEAU — Koto City 2023 buildings

- Dataset: Project PLATEAU, Tokyo Koto City 3D City Model, 2023 release.
- Catalog: <https://www.geospatial.jp/ckan/dataset/plateau-13108-koto-ku-2023>
- Official catalog API: <https://api.plateauview.mlit.go.jp/datacatalog/plateau-datasets>
- Local source meshes used: `53394604_bldg_6697_op.gml` and `53394614_bldg_6697_op.gml` (building LOD1).
- Required attribution and applicable redistribution terms: **not verified from the official dataset metadata during this run**. Do not redistribute the source meshes or derivative geometry until the dataset's current license and attribution notice have been checked.
- The two corresponding ZIP archives were already tracked in the repository before this Phase 2A commit. This commit does not add or modify those archives; this note does not resolve their license status.

## OpenStreetMap — roads and Kiba Park boundary

- Source: OpenStreetMap API map extract, retrieved 2026-10-12 UTC for the configured area.
- API response metadata declared copyright `OpenStreetMap and contributors`, attribution URL <https://www.openstreetmap.org/copyright>, and license URL <https://opendatacommons.org/licenses/odbl/1-0/> (the response itself used the equivalent `http://` links).
- Attribution to retain: **© OpenStreetMap contributors**.
- The ODbL declaration was observed in the API response. The full terms page was not independently reachable/verified during this run; check it before redistributing a database or derivative database. The relation and feature records used to build v02 are therefore excluded from this public commit.
- Park boundary: OSM multipolygon `relation/14273608` (`木場公園` / `Kiba Park`).

## Geospatial Information Authority of Japan (GSI) map tiles

- GSI standard-map tiles were used only as a visual alignment reference for a local QA image.
- Applicable tile terms and required attribution were not verified during this run. The tile image and the comparison image containing tile pixels are excluded from this public commit.

## Publication decision for this commit

Included: reproducible Phase 2A scripts, dependency declaration, validation summary, and this source/terms record.

Kept local and excluded from this public commit because they contain or depict source-derived data with unresolved redistribution conditions:

- `output/KIBA_REAL_CITY_v02.blend`, `output/KIBA_REAL_CITY_v02.glb`, and `output/geo_reference_v02.json`.
- `reports/KIBA_REAL_CITY_v02_preview.png`, `reports/phase2a_map_check.png`, and `reports/KIBA_REAL_CITY_preview_45deg.png`.
- `reports/phase2a_report.json`, `reports/phase2a_report.md`, and the modified Phase 1 `reports/generation_report.json` / `.md` (the JSON/Markdown include PLATEAU-derived building attributes).
- Downloaded OSM extracts, GSI tile images, and extracted CityGML source files under `data/raw/`.

These files remain available in the local workspace. Do not add them to a public repository or Git LFS until the relevant redistribution terms have been confirmed; Git LFS does not change the underlying license obligations. Phase 1 BLEND/GLB already present in the repository history are not modified by this commit.
