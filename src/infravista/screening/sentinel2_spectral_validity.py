import json
from pathlib import Path

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.vrt import WarpedVRT
from rasterio.features import geometry_mask
from rasterio.warp import transform_geom

base = Path("data/raw/historical_sentinel2")
geojson = Path(
    r"C:\Users\Varun\AppData\Local\Temp\infravista_p4_audit\indicators_window.geojson"
)

with geojson.open(encoding="utf-8") as f:
    features = json.load(f)["features"]

hsr = next(
    feature["geometry"]
    for feature in features
    if feature["properties"]["area_id"] == "hsr"
)

report = {}

for date in ["2017-02-03", "2025-02-06"]:
    folder = base / date / "hsr"

    print(f"\nDATE: {date}")

    with rasterio.open(folder / "SCL_20m.jp2") as reference:
        projected = transform_geom(
            "EPSG:4326", reference.crs, hsr
        )

        inside = geometry_mask(
            [projected],
            out_shape=reference.shape,
            transform=reference.transform,
            invert=True
        )

        scl = reference.read(1)
        clear = inside & ~np.isin(
            scl, [0, 1, 3, 7, 8, 9, 10, 11]
        )

        date_result = {
            "reference_crs": str(reference.crs),
            "reference_transform": list(reference.transform),
            "clear_window_pixels": int(clear.sum()),
            "bands": {}
        }

        for band in ["B04_20m", "B08_10m", "B11_20m", "B12_20m"]:
            with rasterio.open(folder / f"{band}.jp2") as src:
                if src.crs != reference.crs:
                    raise RuntimeError(f"CRS mismatch: {band}")

                if band == "B08_10m":
                    with WarpedVRT(
                        src,
                        crs=reference.crs,
                        transform=reference.transform,
                        width=reference.width,
                        height=reference.height,
                        resampling=Resampling.average
                    ) as aligned:
                        from rasterio.windows import from_bounds
                        win = from_bounds(
                            *rasterio.features.bounds(projected),
                            transform=reference.transform
                        ).round_offsets().round_lengths()
                        arr = aligned.read(
                            1,
                            window=win,
                            masked=True
                        )
                        mask_window = clear[
                            int(win.row_off):int(win.row_off + win.height),
                            int(win.col_off):int(win.col_off + win.width)
                        ]
                else:
                    if (
                        src.shape != reference.shape
                        or not src.transform.almost_equals(reference.transform)
                    ):
                        raise RuntimeError(f"Grid mismatch: {band}")

                    from rasterio.windows import from_bounds
                    win = from_bounds(
                        *rasterio.features.bounds(projected),
                        transform=reference.transform
                    ).round_offsets().round_lengths()
                    arr = src.read(1, window=win, masked=True)
                    mask_window = clear[
                        int(win.row_off):int(win.row_off + win.height),
                        int(win.col_off):int(win.col_off + win.width)
                    ]

                if arr.shape != mask_window.shape:
                    raise RuntimeError(
                        f"Window shape mismatch: {band}"
                    )

                valid = mask_window & ~np.ma.getmaskarray(arr)
                values = np.asarray(arr)[valid]
                values = values[values != 0]

                if values.size == 0:
                    raise RuntimeError(f"No valid values: {band}")

                stats = {
                    "source_resolution": list(src.res),
                    "sample_count": int(values.size),
                    "min": float(np.min(values)),
                    "p01": float(np.percentile(values, 1)),
                    "median": float(np.median(values)),
                    "p99": float(np.percentile(values, 99)),
                    "max": float(np.max(values)),
                    "scale_metadata": list(src.scales),
                    "offset_metadata": list(src.offsets),
                    "tags": src.tags()
                }

                date_result["bands"][band] = stats

                print(
                    f"{band}: n={values.size:,}, "
                    f"min={stats['min']:.0f}, "
                    f"median={stats['median']:.0f}, "
                    f"max={stats['max']:.0f}"
                )
                print(
                    "  Scale metadata:",
                    stats["scale_metadata"],
                    "Offset metadata:",
                    stats["offset_metadata"]
                )

        report[date] = date_result

output = Path(
    "reports/p4_historical_growth/sentinel2_spectral_validity.json"
)
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(
    json.dumps(report, indent=2, default=str),
    encoding="utf-8"
)

print("\nReport saved:", output)
print("SPECTRAL VALIDITY CHECK: COMPLETE")
