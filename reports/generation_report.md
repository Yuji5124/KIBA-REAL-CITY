# KIBA REAL CITY generation report

- Status: converted
- Dataset: Project PLATEAU Tokyo Koto City 3D City Model (2023)
- Source files: 53394604_bldg_6697_op.gml (34438104 bytes), 53394614_bldg_6697_op.gml (36019668 bytes)
- CityGML spec/schema: 2.0 / PLATEAU IUR 3.0
- Area: Kiba Park, Koto City, Tokyo, Japan; center 35.67455, 139.8079; 500 m square
- Mesh codes (1 km): 53394604, 53394614
- Source building features: 6023
- Buildings in extent: 233
- LOD1 height range/mean: 3.0 / 60.007 / 9.818 m
- Footprint bounds (local m): [-250.0, -250.0, 250.0, 250.0]
- Per-building position/base/height records: 233 entries in generation_report.json
- Coordinate XY storage: 4 decimal places in metres; maximum rounding error 3.467022046436684e-05 m
- measuredHeight differs from LOD1 geometry on 151 features; LOD1 Solid Z extent is used for generated height
- BLEND: 1998516 bytes
- GLB: 380180 bytes
- CRS: EPSG:6677; vertical datum: JGD2011 gravity-related height from EPSG:6697 source coordinates
- Preview: reports/KIBA_REAL_CITY_preview.png

## Validation
- building_count_nonzero: PASS
- finite_source_coordinates: PASS
- blend_reopens_with_buildings: PASS
- glb_reimports_with_buildings: PASS
- all_expected_glb_buildings_present: PASS
- dimensions_preserved_to_2cm_in_blend: PASS
- dimensions_preserved_to_2cm_in_glb: PASS

## Data gaps and warnings
- Roads, vegetation, bridges and terrain are not converted in Phase 1.
- Dataset release year is from the supplied official dataset identifier; license is not present in the provided per-mesh archives and remains unverified.
