# P3 Spatial QA Report

**Run:** `20261106T191045Z_indicators`

## Input checks

- Input records: 3618
- CRS: EPSG:4326
- Geometry types: Polygon
- Invalid geometries: 0
- Empty geometries: 0
- Null geometries: 0
- Zones: hsr, whitefield

## Coverage

- Partial-coverage indicator records: 1440
- Grid cells with zero coverage: 0
- Grid cells with partial coverage: 80
- Grid cells with very small positive coverage (<0.001): 4
- Minimum coverage fraction: 0.00000556
- Maximum coverage fraction: 1.00000000

## Quality flag occurrences

| Flag | Occurrences |
|---|---:|
| `none_mapped_not_confirmed_absent` | 2301 |
| `osm_completeness_unverified` | 3618 |
| `partial_cell_coverage` | 1440 |
| `point_polygon_dedupe_assumption` | 1407 |
| `small_denominator` | 540 |
| `storm_drains_often_unmapped` | 1206 |

## Interpretation and limitations

- These maps show derived indicators from mapped OSM features.
- Zero means none mapped for that indicator, not confirmed absence.
- OSM completeness is unverified.
- Coverage fraction describes the share of a grid cell inside the study window; it is not an accuracy or completeness score.
- Quality-flag counts are indicator-record occurrences, not unique grid-cell counts.
- Very small positive-coverage boundary slivers are retained; cells flagged `small_denominator` should not be ranked.
- Waterway and drain maps do not establish that the drainage network is complete or functional.
- These outputs are not independently validated by P6.
- OSM rights remain `review_required`; these outputs are for team review, not cleared for publication.

## Generated files

- `01_motorised_road_density.png`
- `02_school_distribution.png`
- `03_hospital_distribution.png`
- `04_total_waterway_density.png`
- `05_drain_density.png`
- `06_grid_coverage_fraction.png`
- `indicator_summary.csv`
- `p3_spatial_qa_report.md`
