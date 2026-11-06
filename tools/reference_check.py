"""Independent, standard-library cross-check of P3 numbers (counts exact, lengths ~1%).
Deliberately does NOT use geopandas, so a bug in the main pipeline cannot hide here.
Usage: python tools/reference_check.py <p2-package.zip>
Keep ROAD_GROUPS in sync with config/indicators.yml by hand (that is the point: two copies)."""
import collections, json, math, sys, zipfile

ROAD_GROUPS = {
    "motorised_network": {"motorway", "motorway_link", "trunk", "trunk_link", "primary", "primary_link",
                          "secondary", "secondary_link", "tertiary", "tertiary_link", "unclassified",
                          "residential", "living_street"},
    "service_and_track": {"service", "track"},
    "pedestrian_cycle": {"footway", "path", "steps", "cycleway", "pedestrian"},
    "not_existing": {"construction", "proposed"},
}
CENTERS = {"hsr": (12.9116, 77.6389), "whitefield": (12.9698, 77.7500)}


def seg_len(c, lat0):
    k = 111_320
    t = 0.0
    for (x1, y1), (x2, y2) in zip(c, c[1:]):
        t += math.hypot((x2 - x1) * k * math.cos(math.radians(lat0)), (y2 - y1) * k)
    return t


def lines(g):
    if g["type"] == "LineString":
        yield g["coordinates"]
    elif g["type"] == "MultiLineString":
        yield from g["coordinates"]


def main(zp):
    z = zipfile.ZipFile(zp)
    files = {n.replace("\\", "/").split("/")[-1]: n for n in z.namelist() if not n.endswith("/")}
    load = lambda lid: json.loads(z.read(files[lid + ".geojson"]))["features"]
    for zone, (lat0, _) in CENTERS.items():
        print(f"\n=== {zone} ===")
        tot = collections.Counter(); cnt = collections.Counter()
        for f in load(f"roads_{zone}"):
            h = f["properties"]["highway"]
            grp = next((n for n, s in ROAD_GROUPS.items() if h in s), "other_unmapped_class")
            cnt[grp] += 1
            tot[grp] += sum(seg_len(c, lat0) for c in lines(f["geometry"]))
        area = math.pi * 2.5**2
        for grp in list(ROAD_GROUPS) + ["other_unmapped_class"]:
            print(f"roads {grp:22s} ways={cnt[grp]:5d} length_km~{tot[grp]/1000:8.2f} density~{tot[grp]/1000/area:6.2f} km/km2")
        pc = collections.Counter(); gc = collections.Counter()
        for f in load(f"facilities_points_{zone}"):
            p = f["properties"]; pc[p.get("amenity") or ("pt:" + str(p.get("public_transport")))] += 1
        for f in load(f"facilities_polygons_{zone}"):
            p = f["properties"]; gc[p.get("amenity") or ("pt:" + str(p.get("public_transport")))] += 1
        print("facility points  (raw):", dict(pc))
        print("facility polygons(raw):", dict(gc))
        w = collections.Counter(f["properties"].get("waterway") for f in load(f"water_lines_{zone}"))
        print("waterway counts:", dict(w), "| water polygons:", len(load(f"water_polygons_{zone}")))


if __name__ == "__main__":
    main(sys.argv[1])
