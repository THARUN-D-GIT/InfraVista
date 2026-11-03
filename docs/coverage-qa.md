# Coverage and QA note: run 20261103T154855Z_normalize

## Preflight decision: PASS WITH LIMITATIONS
Usable for describing mapped OSM roads, water and facilities inside the two pilot zones (hsr, whitefield).
Not usable as evidence of absence, and not cleared for publication (rights: review_required).

## Pre-clip vs post-clip (EPSG:32643, proposed CRS)
| Layer | Pre-clip | Post-clip | Features cut at boundary |
|---|---|---|---|
| roads hsr | 614.559 km | 557.386 km | 210 |
| roads whitefield | 476.982 km | 384.268 km | 181 |
| water lines hsr | 24.98 km | 20.688 km | 7 |
| water lines whitefield | 35.597 km | 24.828 km | 9 |
| water polygons hsr | 4.5122 km2 | 1.2192 km2 | 6 |
| water polygons whitefield | 1.791 km2 | 0.5888 km2 | 3 |
| facilities polygons hsr | 0.2747 km2 | 0.2473 km2 | 3 |
| facilities polygons whitefield | 0.7856 km2 | 0.6906 km2 | 4 |
| road_nodes, facilities points (all) | counts unchanged | counts unchanged | 0 |

Post-clip feature counts: roads 4782 / 3107; road_nodes 854 / 330; water lines 84 / 118;
water polygons 38 / 21; facilities points 289 / 102; facilities polygons 59 / 35 (hsr / whitefield).

## Checks performed (all passed)
- Raw file checksums matched the download run record before processing.
- All 12 layers: 0 invalid, 0 empty geometries, 0 duplicate feature_id, CRS EPSG:32643.
- Boundary checksum matched the download record; git tree clean at run time.

## Quarantined
8 Whitefield road polygons (0.0139 km2), written unclipped to data/interim/quarantine/. Not released.

## Limitations
- OSM completeness is unverified. Missing features mean unknown, not absent.
- Clipped geometries cover only the part inside the zone circle.
- Zones are circles, not administrative boundaries.
- No observation date. Only accessed_at (download time) is recorded.
- Processing CRS EPSG:32643 is a proposal. Output is not in EPSG:4326.
- construction and proposed highways are included in roads; flagged in the handoff, not filtered.
- Rights: ODbL, no legal review done. Status review_required. Do not publish.
