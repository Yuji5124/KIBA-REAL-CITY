# Data sources, attribution, and publication status

This file records source and terms checks performed on 2026-10-12 (UTC); URL availability was rechecked at 21:55 UTC. It does not grant rights beyond the source providers' terms.

## Project PLATEAU — Koto City 2023 buildings

- Dataset: Project PLATEAU, Tokyo Koto City 3D City Model, 2023 release.
- Catalog: <https://www.geospatial.jp/ckan/dataset/plateau-13108-koto-ku-2023>
- Official catalog API: <https://api.plateauview.mlit.go.jp/datacatalog/plateau-datasets>
- Local source meshes used: `53394604_bldg_6697_op.gml` and `53394614_bldg_6697_op.gml` (building LOD1).
- Official general terms checked: <https://www.mlit.go.jp/plateau/site-policy/> (HTTP 200 at 2026-10-12 21:55 UTC). The page says 3D city model open data published through the Geospatial Information Center is normally under the Public Data License 1.0 (PDL 1.0) unless a rights notice says otherwise; it identifies municipalities as copyright owners of those datasets and says PDL 1.0 is CC BY 4.0 compatible. It asks users to cite the source and identify modifications.
- Official PDL 1.0 text: <https://www.digital.go.jp/resources/open_data/public_data_license_v1.0> (proxy CONNECT failed at 21:55 UTC; not directly reviewed). The description above reflects the official MLIT policy page's summary, not a direct check of the PDL text.
- Koto 2023 dataset-specific license field / rights notice: **not directly verified**. Both the CKAN page and CKAN package API returned HTTP 403 at 21:55 UTC. The official PLATEAU datacatalog API returned HTTP 200 and lists Koto 2025 CityGML with `bldg`, `brid`, and `veg` feature types, but its current payload has no Koto 2023 record. The 2025 listing does not prove the 2023 package's individual notice.
- Suggested attribution following the general PDL example, pending confirmation against the 2023 dataset page: `出典：Project PLATEAU 江東区2023年度3D都市モデル（江東区・国土交通省）を加工して作成。` Include the dataset URL above and state that the model was clipped/reprojected/extruded. Do not present this as the dataset's verified exact credit line.
- The two corresponding ZIP archives were already tracked and publicly available before this Phase 2B work. `1e4657d` (`Add Koto City building mesh archives`) added `53394604_bldg_6697_op.zip` (1,664,984 bytes) and `53394614_bldg_6697_op.zip` (1,300,570 bytes). Their local SHA-256 values match the Git blobs. The anonymous raw GitHub URL for the first ZIP returned HTTP 200, confirming that the repository exposes it. The ZIPs contain only the respective GML files (34,438,104 and 36,019,668 bytes). No deletion, history rewrite, or force push was performed.
- Deletion decision: the official general rule supports reuse when no specific rights notice overrides it, so immediate deletion is not justified by the evidence collected. Because the 2023 dataset-specific notice could not be read, treat its exact attribution/any exception as unresolved and do not add new PLATEAU-derived outputs publicly. If a later check finds a conflicting notice, remove tracked copies with a normal follow-up commit while retaining a verified backup; removing old blobs from Git history would require history rewriting and is a separate, explicitly approved operation.

## OpenStreetMap — roads and Kiba Park boundary

- Source: OpenStreetMap API map extract, retrieved 2026-10-12 UTC for the configured area.
- API response metadata declared copyright `OpenStreetMap and contributors`, attribution URL <https://www.openstreetmap.org/copyright>, and license URL <https://opendatacommons.org/licenses/odbl/1-0/> (the response itself used the equivalent `http://` links).
- Attribution string observed in the API metadata: **OpenStreetMap and contributors**. Use the attribution URL above and retain the snapshot date. The common display form `© OpenStreetMap contributors` is also consistent with the requested attribution, but the API's literal value is the directly observed text.
- The API XML declared ODbL 1.0 and this is the license of the OSM database/features used in the local model. The full copyright/license pages were not independently reachable (proxy CONNECT returned HTTP 000 at 21:55 UTC); the API-provided declarations/URLs were available in the local source XML. Feature IDs and provenance are retained in v03 Blender objects. The local v03 model and extracts are excluded from the public commit while reviewing redistribution obligations.
- Park boundary: OSM multipolygon `relation/14273608` (`木場公園` / `Kiba Park`).

## Geospatial Information Authority of Japan (GSI) map tiles

- GSI standard-map tiles were used only as a visual alignment reference for a local QA image.
- Official terms page: <https://maps.gsi.go.jp/development/terms.html>; tile list: <https://maps.gsi.go.jp/development/ichiran.html>. Both were blocked by proxy CONNECT at 2026-10-12 21:55 UTC (HTTP 000), so applicable license and required attribution text remain **unverified**.
- The tile image and the comparison image containing tile pixels are excluded from this public commit. No GSI tile imagery was used in the Phase 2B model.

## Publication decision for this commit

Included: reproducible Phase 2A/2B scripts, dependency declaration, and this source/terms record. Detailed data-derived reports are local and ignored.

Kept local and excluded from this public commit because they contain or depict source-derived data with unresolved redistribution conditions:

- `output/KIBA_REAL_CITY_v02.blend`, `output/KIBA_REAL_CITY_v02.glb`, `output/geo_reference_v02.json`, and the Phase 2B v03 outputs.
- `reports/KIBA_REAL_CITY_v02_preview.png`, `reports/KIBA_REAL_CITY_v03_preview.png`, `reports/phase2a_map_check.png`, and `reports/KIBA_REAL_CITY_preview_45deg.png`.
- `reports/phase2a_report.json`, `reports/phase2a_report.md`, `reports/phase2b_report.json`, `reports/phase2b_report.md`, and the modified Phase 1 `reports/generation_report.json` / `.md` (the detailed reports include PLATEAU-derived building attributes or OSM feature data).
- Downloaded OSM extracts, GSI tile images, and extracted CityGML source files under `data/raw/`.

These files remain available in the local workspace. Do not add them to a public repository or Git LFS until the relevant redistribution terms have been confirmed; Git LFS does not change the underlying license obligations. Phase 1 BLEND/GLB already present in the repository history are not modified by this commit.

## Phase 3D extension: Museum of Contemporary Art and expanded Kiba Park

Sources checked on 2026-10-12 UTC through the official PLATEAU catalog API and
OpenStreetMap API. API payload snapshots and derived geometry are local under
`data/processed/` and `data/raw/` and are excluded from Git.

### PLATEAU Koto City 2023 and 2025 catalog checks

- 2023 dataset: <https://www.geospatial.jp/ckan/dataset/plateau-13108-koto-ku-2023>.
  The CKAN dataset page/package remained inaccessible (HTTP 403), so the exact
  Koto 2023 dataset-specific rights notice and attribution wording remain
  **unverified**. The two local 2023 source meshes are
  `53394604_bldg_6697_op.gml` and `53394614_bldg_6697_op.gml`; both use PLATEAU
  building data in EPSG:6697 and were transformed to EPSG:6677 for the model.
- Official rectangular query used for the expanded extent:
  <https://api.plateauview.mlit.go.jp/datacatalog/citygml/r:139.8051362713,35.6713587727,139.8107204991,35.6802912945>.
  The response is saved locally in `data/processed/phase3d_plateau_catalog.json`.
  It reported Koto 2025 spec 5.0; 2742 building features (143 LOD2) for mesh
  `53394604`; 3243 building features and **0 LOD2** for `53394614`, which
  contains the museum. Koto 2025 LOD2 3D Tiles are listed in the catalog, but
  their direct `assets.cms.plateau.reearth.io` host was blocked by the network
  proxy; no such tile was treated as downloaded or used.
- General PLATEAU policy page: <https://www.mlit.go.jp/plateau/site-policy/>;
  official PDL 1.0 text: <https://www.digital.go.jp/resources/open_data/public_data_license_v1.0>.
  As recorded above, the general policy summarizes PDL 1.0 as the usual license
  for Geospatial Information Center PLATEAU publications, subject to any
  dataset-specific rights notice. The dataset-specific 2023 notice was not
  checked successfully. Suggested attribution remains provisional:
  `出典：Project PLATEAU 江東区2023年度3D都市モデル（江東区・国土交通省）を加工して作成。`
  Identify the source URL and modifications if/when publication rights are
  confirmed. This exact line is not represented as an officially verified
  dataset credit.

### OpenStreetMap extension

- Extract URL:
  <https://api.openstreetmap.org/api/0.6/map?bbox=139.8043074543,35.6706825459,139.8115491626,35.6809674762>.
  Retrieved 2026-10-12 22:51:51 UTC; server `Date` header was
  `Mon, 12 Oct 2026 22:51:50 GMT`. The API XML declares
  <https://opendatacommons.org/licenses/odbl/1-0/> and the attribution
  <https://www.openstreetmap.org/copyright>; the literal API metadata says
  `OpenStreetMap and contributors`. The full ODbL terms page could not be
  independently opened in this environment, so this check records the API's
  declaration, not a fresh legal review of the complete terms.
- Museum: OSM multipolygon `relation/12077221`, tagged `東京都現代美術館`.
  Kiba Park: `relation/14273608`. No separate museum parcel/cadastral polygon
  was mapped; the complete mapped park relation supplies the wider grounds
  context. It is not a legal parcel boundary.
- The local extent comparison is drawn from OSM vector features and includes
  `© OpenStreetMap contributors`, snapshot date, and source URL in this file;
  it uses no GSI tile image.

### Phase 3D publication status

The v05 BLEND/GLB, local OSM extracts, PLATEAU-derived extensions, their
previews, and detailed reports remain excluded from public Git while the exact
2023 package rights notice and full ODbL terms have not been independently
confirmed. Source-derived geometry in a preview/report is also treated as
restricted for publication until the terms are resolved. The new reproducible
scripts and this documentation can be reviewed separately; no generated v05
asset is included in a code-only commit.
