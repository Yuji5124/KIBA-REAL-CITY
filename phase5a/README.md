# KIBA REAL CITY Phase 5A

Phase 5A adds local editable OSM roads, individually mapped trees, and vegetation overlays to the Phase 4A Three.js viewer. It keeps the v07 GLB and georeference files as hash-checked source assets. The data importer never edits those assets.

## Build local feature data

From the repository root, with Python dependencies from `requirements.txt` available:

```bash
python phase5a/scripts/build_feature_data.py
```

The builder reuses `data/raw/kiba_phase3d_osm_map.osm`; it does not contact Overpass. It reads the extent and origin from `output/geo_reference_v07.json`, transforms OSM WGS84 coordinates to EPSG:6677 using `pyproj` (`always_xy=True`), then maps local coordinates to Three.js `X=east, Y=up, Z=-north`.

Current retained extract snapshot: 2026-10-12 22:51:51 UTC, SHA-256 `20ed66d5e2a35e7d54306ce311d5ab1ae2576a4d65326f78db8e6a0e3f3bc36f`. Current output contains 334 road features, 43 individually mapped tree points, and 27 vegetation features. The snapshot has no measured road widths or tree species/heights/crown sizes. Road display widths and tree display dimensions are explicitly estimated; OSM does not enumerate every tree in the park.

Generated files under `phase5a/processed`, `phase5a/metadata`, and `phase5a/edits` are ignored by Git. Do not publish the OSM-derived data until its database rights and distribution obligations have been reviewed.

## Run the local editor

```bash
cd phase4-web
npm ci
npm run dev
```

Open the Vite local URL. The viewer exposes local same-origin API routes only while the development server is running. By default Vite binds to `127.0.0.1`; do not change it to a public interface. Feature data is served from the ignored local processed file, and changes are stored separately in `phase5a/edits/edits.json`. The editor uses a source snapshot hash and per-feature hashes to reject stale diffs. Regeneration leaves edit files untouched and reports source conflicts.

Road widths are editable and flagged as estimated unless an OSM width tag exists. Trees can be moved, assigned a display model, or given edited height, crown diameter, species, and rotation. A manually added tree is labeled as manual/unverified. Mapped vegetation is selectable and read-only so the source polygon is not silently changed. Undo, per-feature revert, and reset operate on the edit-diff layer.

## Elevation status

Terrain is intentionally **BLOCKED**. Existing local GSI PNG candidates do not establish the official product metadata, vertical datum, or usage terms needed for safe height integration. No terrain mesh, elevation edit surface, or invented elevation is produced. The terrain toggle stays disabled; buildings are never moved to fit elevation samples.

## Sources and license state

The OSM API extract metadata declares ODbL 1.0. Attribution shown in the viewer is `© OpenStreetMap contributors`, with the copyright URL `https://www.openstreetmap.org/copyright`. The official full terms could not be fetched in the current restricted runtime, so the derived feature files remain local and Git-ignored. A fresh OSM request was not made because the effective network policy does not allow `api.openstreetmap.org`.

The v07 PLATEAU-derived GLB is served from the existing local repository asset endpoint and remains protected by its preexisting SHA-256. This feature adds no redistributed OSM/GSI/PLATEAU source files. Review the repository's `LICENSE_DATA.md` before sharing derived models or screenshots.

## Validation

```bash
python phase5a/scripts/build_feature_data.py
python -m unittest discover -s phase5a/tests -v
cd phase4-web
npm run build
```

The Python test verifies the retained snapshot counts, identifiers, CRS and axes, explicit missing tree attributes, blocked terrain state, and that edit diffs survive regeneration. Browser-driven touch/desktop interaction and device performance still require an actual browser/device test; they are not inferred from build success.
