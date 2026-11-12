import json
from pathlib import Path

import numpy as np
import rasterio
from rasterio.features import geometry_mask
from rasterio.warp import transform_geom

GEOJSON = Path(
    r"C:\Users\Varun\AppData\Local\Temp\infravista_p4_audit\indicators_window.geojson"
)
RASTER = Path(
    "data/raw/historical_sentinel2/2017-02-03/hsr/SCL_20m.jp2"
)
OUTPUT = Path(
    "reports/p4_historical_growth/sentinel2_study_window_coverage.json"
)

with GEOJSON.open(encoding="utf-8") as f:
    data = json.load(f)

# Deduplicate the repeated P3 indicator geometries.
windows = {}

for feature in data["features"]:
    area_id = feature["properties"]["area_id"]
    geom = feature["geometry"]

    if area_id not in windows:
        windows[area_id] = geom
    elif windows[area_id] != geom:
        raise ValueError(f"Conflicting geometries for {area_id}")

class_names = {
    0: "no_data",
    1: "saturated_or_defective",
    2: "dark_area",
    3: "cloud_shadow",
    4: "vegetation",
    5: "bare_soil",
    6: "water",
    7: "unclassified",
    8: "medium_probability_cloud",
    9: "high_probability_cloud",
    10: "thin_cirrus",
    11: "snow_or_ice",
}

results = {}

with rasterio.open(RASTER) as src:
    print("Raster CRS:", src.crs)
    print("Raster resolution:", src.res)

    for area_id, geom in windows.items():

        # GDAL performs the coordinate transformation.
        projected = transform_geom(
            "EPSG:4326",
            src.crs,
            geom,
            precision=-1
        )

        inside = geometry_mask(
            [projected],
            out_shape=(src.height, src.width),
            transform=src.transform,
            invert=True,
            all_touched=False,
        )

        total = int(inside.sum())

        if total == 0:
            print(f"\n{area_id.upper()}: NO INTERSECTING PIXELS")
            continue

        pixels = src.read(1)[inside]
        values, counts = np.unique(pixels, return_counts=True)

        distribution = {
            class_names.get(int(v), f"unknown_{v}"): {
                "pixel_count": int(c),
                "percentage": round(float(c / total * 100), 4),
            }
            for v, c in zip(values, counts)
        }

        excluded = {0, 1, 3, 7, 8, 9, 10, 11}
        usable = ~np.isin(pixels, list(excluded))

        results[area_id] = {
            "geometry_crs_assumption": "EPSG:4326",
            "raster_crs": str(src.crs),
            "window_pixel_count": total,
            "usable_pixel_count": int(usable.sum()),
            "usable_pixel_percentage": round(
                float(usable.mean() * 100), 4
            ),
            "class_distribution": distribution,
        }

        print(f"\n{area_id.upper()}")
        print("Window pixels:", total)
        print(
            "Usable pixels:",
            int(usable.sum()),
            f"({usable.mean() * 100:.4f}%)"
        )

        for name, item in distribution.items():
            print(
                f"  {name}: {item['pixel_count']:,} "
                f"({item['percentage']}%)"
            )

report = {
    "date": "2017-02-03",
    "asset": "SCL_20m",
    "method": "GDAL geometry transformation; pixel-centre inclusion",
    "limitations": [
        "P3 pilot windows are not approved authoritative boundaries.",
        "EPSG:4326 is inferred from GeoJSON longitude/latitude coordinates.",
        "Only the HSR tile is downloaded; Whitefield may need multiple tiles.",
        "Class 2 dark-area pixels remain uncertain.",
        "No historical change assessment has been performed."
    ],
    "areas": results,
}

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
OUTPUT.write_text(json.dumps(report, indent=2), encoding="utf-8")

print("\nReport saved:", OUTPUT)
print("STUDY WINDOW COVERAGE CHECK: COMPLETE")
