# Methods note (P3) — v0.1.0 DRAFT

1. Read the P2 package; abort if any layer checksum or feature count differs from `layer_catalog.json`.
2. Reproject layers to the processing CRS (config). Never measure in degrees.
3. Rebuild each 2.5 km study window from the zone centre (same as P2) and cut a fixed-origin 500 m grid; `cell_id` = `<zone>_g<size>_<ix>_<iy>` (absolute coordinates, stable across runs).
4. Roads: classify `highway` into config groups; unknown classes → `other_unmapped_class` (reported, never dropped). Split lines at cell borders with an overlay; length in the projected CRS.
5. Facilities: categorise by OSM tag; a polygon absorbs same-category points within 25 m (counted once). Raw and de-duplicated counts both logged in the run manifest.
6. Water: waterway length by type; polygon union area share.
7. Wrap each value in the canonical record (handbook §5), `evidence_type = derived`, quality flags, source IDs, `method_version`, `run_id`.
8. Write outputs to a new `data/processed/p3/<run_id>/`; write the run manifest with config hash, git commit and input checksums. Existing runs are never overwritten.

## Not done (and why)
- **Observed change / built-up:** no dated raster pair from P2 yet (see `src/infravista/change/__init__.py`).
- **Validation:** only P6 may label results validated. P3 supplies a sample package (step 8 of the guide).
- No forecast, ranking, gap or "underserved" claims.

## Independent reference (stdlib, approximate; counts exact, lengths ~±1%) — for P6 spot checks
Window area ≈ 19.63 km².
| zone | motorised km (density) | service/track | pedestrian/cycle | not_existing (ways) |
|---|---|---|---|---|
| hsr | 425.1 (21.65) | 64.4 | 58.7 | 10.4 km (39 ways) |
| whitefield | 241.4 (12.29) | 89.7 | 33.9 | 20.0 km (129 ways) |
Raw facility points/polygons and waterway counts: see `tools/reference_check.py` output.
