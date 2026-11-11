import json
import numpy as np
import rasterio
from pathlib import Path

raster_path = Path(
    "data/raw/historical_sentinel2/2017-02-03/hsr/SCL_20m.jp2"
)

class_names = {
    0: "No data",
    1: "Saturated or defective",
    2: "Dark area pixels",
    3: "Cloud shadows",
    4: "Vegetation",
    5: "Bare soil",
    6: "Water",
    7: "Unclassified",
    8: "Medium probability clouds",
    9: "High probability clouds",
    10: "Thin cirrus",
    11: "Snow or ice",
}

with rasterio.open(raster_path) as src:
    scl = src.read(1)

values, counts = np.unique(scl, return_counts=True)
total = scl.size

print("SCL PIXEL QUALITY REPORT")
print("Total pixels:", total)
print("Raster dimensions:", src.width, "x", src.height)
print("\nClass distribution:")

class_report = {}

for value, count in zip(values, counts):
    percentage = count / total * 100
    name = class_names.get(int(value), "Unknown class")

    class_report[str(int(value))] = {
        "name": name,
        "pixel_count": int(count),
        "percentage": round(float(percentage), 4),
    }

    print(
        f"Class {value:2d} | {name:30s} | "
        f"{count:10,d} pixels | {percentage:8.4f}%"
    )

report = {
    "raster": str(raster_path),
    "total_pixels": int(total),
    "classes": class_report,
    "nodata_metadata": src.nodata,
}

output = Path(
    "reports/p4_historical_growth/sentinel2_scl_quality_report.json"
)
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(report, indent=2), encoding="utf-8")

print("\nReport saved:", output)
