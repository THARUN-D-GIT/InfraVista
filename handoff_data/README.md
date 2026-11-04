# handoff_data: P2 data package for backend and frontend (P1, P5)

Data (c) OpenStreetMap contributors, ODbL. License: https://www.openstreetmap.org/copyright
Status: rights review_required, CRS EPSG:32643 proposed (not approved). Team use only.
The map must show the attribution: (c) OpenStreetMap contributors, with the license link.

File: 20261104T092142Z_publish.zip
SHA-256: ED487FD6CDEAC2BFFCD211EFE4C4D12E93EC586313A3F46DEDA55A2C72ED8842
Contents: 12 GeoJSON layers (EPSG:4326) + layer_catalog.json (one record per layer)

## How to use
1. Clone the repo or download the zip from GitHub.
2. Verify: Get-FileHash <zip> -Algorithm SHA256 and compare. If it differs, do not use it.
3. Unzip: Expand-Archive <zip> -DestinationPath <folder>
4. Read docs/data-dictionary.md, docs/coverage-qa.md and docs/handoffs/P2-P1P5-001.md first.

## Things to know
- quality_flags is a semicolon-separated string inside the GeoJSON features and a list in the catalog.
- roads include construction, proposed, footway, path, steps and service ways.
- road_nodes are tagged points (lamps, crossings, bus stops, signals), not network nodes.
- Missing features mean unknown, not absent. Show "no data", never zero.
