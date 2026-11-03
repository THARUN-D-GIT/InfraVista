# Rights review: OpenStreetMap sources

Reviewed by: Person 2
Date: 2026-11-03
Source page: https://www.openstreetmap.org/copyright
Applies to: osm_roads_2026_11, osm_water_2026_11, osm_facilities_2026_11

| Question | Answer (from the page) |
|---|---|
| Can we access it? | Yes. The page says OSM is open data under the Open Data Commons Open Database License (ODbL), published by the OpenStreetMap Foundation. |
| Can we store a copy? | Yes. The page says users are free to "copy, distribute, transmit and adapt" the data, as long as OpenStreetMap and its contributors are credited. |
| Can we transform / derive? | Yes. Adapting the data is allowed. If we alter or build upon the data, the result may be distributed only under the same license (share-alike). |
| Can we combine with other data? | Not directly stated on this page. Combining counts as building on the data, so the share-alike condition may apply to the combined database. Full legal code: https://opendatacommons.org/licenses/odbl/1-0/. Needs review. |
| Can we display in a web map? | Yes, with attribution. The page says attribution rules differ by use (browsable map, printed map, static image). Guidelines: https://osmfoundation.org/wiki/Licence/Attribution_Guidelines. Our web map must show the notice. |
| Can we export / redistribute? | Yes, under ODbL. If we distribute OSM in data form, we must name and link directly to the license. Redistributing a derived database falls under share-alike. Needs review. |
| Attribution required (exact text)? | Two things are required: (1) credit OpenStreetMap by displaying the attribution notice, and (2) make clear the data is available under the Open Database License, for example by linking to https://www.openstreetmap.org/copyright. Standard notice we will use: "© OpenStreetMap contributors". |
| Commercial use allowed? | Not explicitly stated on this page. The page grants broad freedom to copy and adapt with credit and does not mention a commercial restriction. Confirm with the full ODbL text and P6. |
| Share-alike / derived database obligations? | Yes. The page says anyone who alters or builds on the data may distribute the result only under the same license. Whether our derived layers count as a "derived database" and what we must publish depends on how we distribute them. Needs P6 / legal review. |

## Additional service policies (not covered by the data license)

The page says OSM cannot provide a free-of-charge map API or map tiles for third parties. These services have separate usage policies:

- API Usage Policy: https://operations.osmfoundation.org/policies/api/
- Tile Usage Policy: https://operations.osmfoundation.org/policies/tiles/
- Nominatim Usage Policy: https://operations.osmfoundation.org/policies/nominatim/

Consequences for InfraVista:

- Do not use the public OSM tile server as the basemap of the final map without checking the Tile Usage Policy. P5 should choose a basemap source whose terms allow our use.
- Downloading data through a public API (Overpass, Nominatim, OSMnx) must be small and polite. We are downloading only two study windows, which fits.

## Data limitations (from our own caveats, not from the license)

- Volunteer-mapped; completeness is not guaranteed.
- A missing feature does not mean there is no infrastructure on the ground. It means "not mapped".
- Storm drains and small drains are often incompletely mapped.
- Facilities may be mapped as points or polygons inconsistently.

## Status

**REVIEW REQUIRED**

P6 and the data owner / legal reviewer must confirm before any public display, export, or redistribution. Until then, these sources are for internal use only.

Open items for P6:
1. Does combining OSM layers with other data trigger share-alike for the whole database?
2. What exact attribution text and placement are needed on the map and in exported reports?
3. Is the commercial or non-commercial status of the project relevant?
4. Which basemap will P5 use, given the tile policy?