# Indicator definitions (P3) — DRAFT, needs P1 approval

Status: PROPOSED. P1 approves definitions/units/thresholds; P6 reviews independently. Evidence type: **derived**.
Inputs: P2 package `20261104T092142Z_publish` (OSM, ODbL, rights `review_required`, team use only).
Processing CRS: EPSG:32643 (proposed by P2, **not approved**). Outputs delivered in EPSG:4326.

| indicator_id | Meaning | Units | Denominator | Notes |
|---|---|---|---|---|
| `road_density_km_per_km2_<group>` | Centreline length of OSM `highway` ways in the group, per km² of window/cell area | km/km2 | area in window (km²) | Centreline, not lane-km; dual carriageways count twice; footways along roads add to `pedestrian_cycle`. |
| `facility_count_<category>` | Mapped facilities after point/polygon de-dup | count | none | Not a complete inventory. 0 = none mapped, not confirmed absent. `transit_*` categories are not additive (a stop may be mapped as platform and stop_position). |
| `waterway_density_km_per_km2_<type>` / `_all` | Length of OSM `waterway` lines per km² | km/km2 | area in window | Storm drains are often unmapped. |
| `water_area_share` | Union area of `natural=water` polygons / area in window | fraction | area in window (m²) | Union avoids double counting. |

Road groups (config `road_groups`): motorised_network, service_and_track, pedestrian_cycle, **not_existing** (construction, proposed — never mixed with existing), other_unmapped_class.

## Missing vs zero (contract rule)
- Cell value `0` carries flag `none_mapped_not_confirmed_absent`. P5 must show it as "none mapped", not "no infrastructure". **Decision needed (P1/P6/P5):** show as no-data instead?
- `coverage_fraction` = share of the grid cell inside the study window (edge cells < 1). It is NOT an accuracy or completeness score.
- Cells with coverage < `min_coverage_for_density` get `small_denominator`: do not rank them.

## Open decisions
1. Which road classes count as "existing road network" (P1 + P3).
2. Grid size 500 m (P1/P5).
3. De-dup tolerance 25 m (P3 + P6).
4. Confirm processing CRS (P1/P3/P4).
