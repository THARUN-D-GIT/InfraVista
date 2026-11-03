# Data dictionary: normalized OSM layers (run 20261103T154855Z_normalize)

Status: PROVISIONAL. CRS not approved. Rights `review_required` (ODbL, no legal review done).
Null/missing tag values mean "tag not present in the source", never zero and never "no".

## Layers (data/processed/20261103T154855Z_normalize/, GeoPackage, EPSG:32643)
| Layer | Source | Geometry | Features |
|---|---|---|---|
| roads_{zone} | osm_roads_2026_11 | LineString | hsr 4782, whitefield 3107 |
| road_nodes_{zone} | osm_roads_2026_11 | Point | hsr 854, whitefield 330 |
| water_lines_{zone} | osm_water_2026_11 | LineString | hsr 84, whitefield 118 |
| water_polygons_{zone} | osm_water_2026_11 | Polygon | hsr 38, whitefield 21 |
| facilities_points_{zone} | osm_facilities_2026_11 | Point | hsr 289, whitefield 102 |
| facilities_polygons_{zone} | osm_facilities_2026_11 | Polygon | hsr 59, whitefield 35 |

Zones: `hsr`, `whitefield` (circular clip areas in boundary_pilot_v1).
Quarantined (not released): osm_roads_2026_11 polygons, whitefield, 8 features,
data/interim/quarantine/20261103T154855Z_normalize/ (written unclipped).

## Added fields
| Field | Type | Meaning |
|---|---|---|
| feature_id | string | `element/id` (OSM element type and OSM id). Unique per layer (checked). |
| element, id | string, int | OSM element type and id as downloaded. |
| source_id | string | Manifest source ID. |
| zone_id | string | Clip zone. |
| evidence_type | string | Always `observed`. |
| accessed_at | UTC timestamp | When the raw file was downloaded (from download run record). NOT an observation date. |
| run_id | string | Normalization run that produced the row. |
| raw_file | string | Raw input file (checksum verified before use). |
| boundary_version | string | `boundary_pilot_v1`. |
| clipped_at_boundary | bool | True if the geometry was cut by the zone circle. Geometry then covers only the part inside. |
| quality_flags | string | Semicolon-separated: `clipped_at_boundary`, `osm_completeness_unverified`. |

## Source tag columns
Kept only where present: name, highway, railway, public_transport, amenity, healthcare,
leisure, natural, waterway, water, landuse, building, office, shop, operator, surface,
lanes, oneway, bridge, tunnel, maxspeed, access. Values are OSM-defined, not harmonized.

## Known limitations
- OSM completeness is unverified. No mapped feature does not mean no infrastructure.
- Clipped geometries are not original geometries. Lengths and areas are for the inside part only.
- Footways, paths, steps and construction roads are in `roads`. Filter on `highway`; P3 decides the classes.
- Observation date/vintage not captured; only accessed_at.
- Output is not in EPSG:4326. API delivery conversion is a later step.

## Note on road_nodes
Tagged OSM nodes found in the roads query (not network intersections or line vertices).
HSR (854): street_lamp 477, crossing 200, bus_stop 105, traffic_signals 65, elevator 4,
motorway_junction 1, stop 1, speed_camera 1; public_transport=platform on 101 rows (overlaps bus_stop);
railway=subway_entrance 1. Not suitable for connectivity analysis. Whitefield not yet summarized.
