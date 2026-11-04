# P2 Completion Tracker — GIS & Data Engineering

**Role:** P2 — GIS & Data Engineer  
**Repository:** InfraVista  
**Status:** In progress  
**Last updated:** 2026-11-04

## Purpose

Track the completion of P2's data inventory, acquisition, normalization, quality assurance, reproducibility, documentation, and handoff responsibilities.

## Existing project context

- Pilot zones: HSR Layout and Whitefield, Bengaluru
- Boundary: `boundary_pilot_v1`
- Proposed processing CRS: EPSG:32643
- Published handoff CRS: EPSG:4326
- Sources: OpenStreetMap roads, water, and facilities
- Rights status: Review required; team use only pending review
- Known limitation: OSM completeness is unverified

## Existing evidence

| Deliverable | Existing evidence |
|---|---|
| Source register | `manifests/sources.yml` |
| File-level source metadata | `manifests/sources_files.yml` |
| Data dictionary | `docs/data-dictionary.md` |
| Coverage and QA report | `docs/coverage-qa.md` |
| OSM rights review | `docs/rights-review-osm.md` |
| Download run records | `manifests/runs/` |
| Normalization run record | `manifests/runs/20261103T154855Z_normalize.json` |
| Publish run record | `manifests/runs/20261104T092142Z_publish.json` |
| Published layer catalog | `manifests/catalog/20261104T092142Z_publish_layer_catalog.json` |
| Preflight report | `manifests/preflight/preflight_20261103T153530Z.json` |
| P2 to P1/P5 handoff | `docs/handoffs/P2-P1P5-001.md` |
| P2 to P3 handoff | `docs/handoffs/P2-P3-001.md` |

## Completion checklist

### 1. Data inventory and source review

- [x] Pilot zones and boundary source documented
- [x] OSM source records and access dates documented
- [x] Source-file checksums recorded
- [x] ODbL attribution and share-alike concerns documented
- [ ] Confirm source retention requirements with project team
- [ ] Complete required ODbL review before external publication

### 2. Acquisition and reproducibility

- [x] Download run records exist
- [x] Normalization run record exists
- [x] Publish run record exists
- [x] Download script records code revision, working-tree state, and rights status in future manifests
- [ ] Verify run records capture required inputs, outputs, configuration, and checksums
- [ ] Verify the documented reproduction commands work from a clean environment
- [ ] Add automated tests for ingestion and manifest generation

### 3. Data normalization and QA

- [x] Normalized layers created for both pilot zones
- [x] Geometry validity, empty features, duplicate IDs, and CRS checked
- [x] Known limitations and quarantined features documented
- [ ] Confirm EPSG:32643 with relevant project owners
- [ ] Confirm indicator-specific road-class filtering with P3

### 4. Published package and handoffs

- [x] Published GeoJSON package and layer catalog created
- [x] Package checksum recorded in handoff
- [x] P2-to-P1/P5 handoff drafted
- [x] P2-to-P3 handoff drafted
- [x] Verify the ZIP contents and checksum against the handoff
- [ ] Obtain receiver acknowledgments
- [ ] Update handoffs with resolved decisions

## Open decisions and dependencies

| Item | Current status | Owner / next action |
|---|---|---|
| Pilot confirmation | Pending | P1 to confirm |
| Processing CRS EPSG:32643 | Proposed | Relevant project owners to approve |
| Road-class inclusion | Pending | P3 to define indicator rules |
| `road_nodes` use | Pending | P3 to confirm need |
| `quality_flags` format | String in GeoJSON; list in catalog | Confirm consumer expectations |
| ODbL publication clearance | Review required | P6 / project review |
| Source retention | TBD | Project team to decide |

## Working rule

Do not mark a pending item complete without evidence. Keep OSM-derived data team-use only until rights review is complete. Keep receiver acknowledgments pending until the recipients confirm receipt.
