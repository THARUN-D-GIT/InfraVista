import json
from pathlib import Path

import numpy as np
import rasterio
from rasterio.features import geometry_mask
from rasterio.warp import transform_geom

base = Path("data/raw/historical_sentinel2")

paths = {
    "2017": base / "2017-02-03/hsr/SCL_20m.jp2",
    "2025": base / "2025-02-06/hsr/SCL_20m.jp2",
}

geojson = Path(
    r"C:\Users\Varun\AppData\Local\Temp\infravista_p4_audit\indicators_window.geojson"
)

output = Path(
    "reports/p4_historical_growth/sentinel2_scl_temporal_quality.json"
)

with geojson.open(encoding="utf-8") as f:
    features = json.load(f)["features"]

windows = {}

for feature in features:
    area = feature["properties"]["area_id"]
    geometry = feature["geometry"]

    if area not in windows:
        windows[area] = geometry
    elif windows[area] != geometry:
        raise ValueError(f"Conflicting geometry: {area}")

excluded = [0, 1, 3, 7, 8, 9, 10, 11]
cloud_shadow = [3, 8, 9, 10]

report = {"areas": {}, "limitations": [
    "P3 pilot geometries are not approved authoritative boundaries.",
    "SCL quality is not built-up classification or growth measurement.",
    "This checks only the downloaded T43PGQ tile.",
    "Additional spectral bands and classification validation are required."
]}

with rasterio.open(paths["2017"]) as old, rasterio.open(paths["2025"]) as new:

    if old.crs != new.crs or old.shape != new.shape:
        raise RuntimeError("Raster grids are incompatible")

    if not old.transform.almost_equals(new.transform):
        raise RuntimeError("Raster pixel transforms differ")

    a = old.read(1)
    b = new.read(1)

    for area, geometry in windows.items():
        projected = transform_geom("EPSG:4326", old.crs, geometry)

        inside = geometry_mask(
            [projected],
            out_shape=old.shape,
            transform=old.transform,
            invert=True,
            all_touched=False
        )

        total = int(inside.sum())

        if total == 0:
            print(f"{area}: no intersecting pixels")
            continue

        old_pixels = a[inside]
        new_pixels = b[inside]

        old_usable = ~np.isin(old_pixels, excluded)
        new_usable = ~np.isin(new_pixels, excluded)
        common = old_usable & new_usable

        result = {
            "window_pixels": total,
            "2017_usable_pixels": int(old_usable.sum()),
            "2025_usable_pixels": int(new_usable.sum()),
            "common_usable_pixels": int(common.sum()),
            "common_usable_percentage": round(
                100 * float(common.mean()), 4
            ),
            "2017_cloud_shadow_pixels": int(
                np.isin(old_pixels, cloud_shadow).sum()
            ),
            "2025_cloud_shadow_pixels": int(
                np.isin(new_pixels, cloud_shadow).sum()
            ),
            "2017_class_counts": {
                str(int(k)): int(v)
                for k, v in zip(*np.unique(old_pixels, return_counts=True))
            },
            "2025_class_counts": {
                str(int(k)): int(v)
                for k, v in zip(*np.unique(new_pixels, return_counts=True))
            }
        }

        report["areas"][area] = result

        print(f"\n{area.upper()}")
        print("Window pixels:", total)
        print("2017 usable:", result["2017_usable_pixels"])
        print("2025 usable:", result["2025_usable_pixels"])
        print(
            "Common usable:",
            result["common_usable_pixels"],
            f'({result["common_usable_percentage"]}%)'
        )
        print("2017 cloud/shadow:", result["2017_cloud_shadow_pixels"])
        print("2025 cloud/shadow:", result["2025_cloud_shadow_pixels"])

output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(report, indent=2), encoding="utf-8")

print("\nSaved:", output)
print("TEMPORAL SCL QUALITY CHECK: COMPLETE")
