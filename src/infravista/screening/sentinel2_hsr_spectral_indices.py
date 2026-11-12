import json
from pathlib import Path
from contextlib import ExitStack

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.features import geometry_mask
from rasterio.warp import transform_geom
from rasterio.windows import from_bounds, transform as window_transform
from rasterio.vrt import WarpedVRT

BASE = Path("data/raw/historical_sentinel2")
REPORT = Path(
    "reports/p4_historical_growth/sentinel2_hsr_spectral_indices.json"
)
GEOJSON = Path(
    r"C:\Users\Varun\AppData\Local\Temp\infravista_p4_audit\indicators_window.geojson"
)
CALIBRATION = Path(
    "reports/p4_historical_growth/sentinel2_radiometric_calibration.json"
)

with GEOJSON.open(encoding="utf-8") as f:
    features = json.load(f)["features"]

hsr = next(
    feature["geometry"]
    for feature in features
    if feature["properties"]["area_id"] == "hsr"
)

with CALIBRATION.open(encoding="utf-8") as f:
    calibration = json.load(f)

dates = ["2017-02-03", "2025-02-06"]
excluded_scl = [0, 1, 3, 7, 8, 9, 10, 11]

def normalized_difference(a, b):
    denominator = a + b
    result = np.full(a.shape, np.nan, dtype=np.float32)
    np.divide(
        a - b,
        denominator,
        out=result,
        where=np.abs(denominator) > 1e-6
    )
    return result

def read_date(date, reference, window):
    folder = BASE / date / "hsr"
    metadata = calibration[date]

    quant = float(metadata["boa_quantification_values"][0])
    offsets = metadata["boa_add_offsets"]

    if quant <= 0:
        raise ValueError("Invalid quantification value")

    output = {}

    with ExitStack() as stack:
        for band, filename in [
            ("B04", "B04_20m.jp2"),
            ("B08", "B08_10m.jp2"),
            ("B11", "B11_20m.jp2"),
        ]:
            src = stack.enter_context(
                rasterio.open(folder / filename)
            )

            if src.crs != reference.crs:
                raise RuntimeError(f"CRS mismatch: {date} {band}")

            if band == "B08":
                vrt = stack.enter_context(
                    WarpedVRT(
                        src,
                        crs=reference.crs,
                        transform=reference.transform,
                        width=reference.width,
                        height=reference.height,
                        resampling=Resampling.average
                    )
                )
                dn = vrt.read(1, window=window).astype(np.float32)
            else:
                if (
                    src.shape != reference.shape
                    or not src.transform.almost_equals(reference.transform)
                ):
                    raise RuntimeError(f"Grid mismatch: {date} {band}")

                dn = src.read(1, window=window).astype(np.float32)

            valid_dn = np.isfinite(dn) & (dn > 0)
            rho = (dn + float(offsets[band])) / quant
            rho[~valid_dn] = np.nan

            output[band] = rho

        with rasterio.open(folder / "SCL_20m.jp2") as scl_src:
            if (
                scl_src.crs != reference.crs
                or scl_src.shape != reference.shape
                or not scl_src.transform.almost_equals(reference.transform)
            ):
                raise RuntimeError(f"SCL grid mismatch: {date}")

            scl = scl_src.read(1, window=window)
            output["scl_valid"] = ~np.isin(scl, excluded_scl)

    return output

with rasterio.open(BASE / dates[0] / "hsr" / "SCL_20m.jp2") as ref:
    projected = transform_geom("EPSG:4326", ref.crs, hsr)
    bounds = rasterio.features.bounds(projected)

    window = from_bounds(*bounds, transform=ref.transform)
    window = window.round_offsets().round_lengths()

    inside = geometry_mask(
        [projected],
        out_shape=(int(window.height), int(window.width)),
        transform=window_transform(window, ref.transform),
        invert=True,
        all_touched=False
    )

    old = read_date(dates[0], ref, window)
    new = read_date(dates[1], ref, window)

common = inside & old["scl_valid"] & new["scl_valid"]

for item in (old, new):
    for band in ["B04", "B08", "B11"]:
        common &= np.isfinite(item[band])
        common &= item[band] >= 0

print("Common valid pixels:", int(common.sum()))

if common.sum() == 0:
    raise RuntimeError("No common valid spectral pixels")

report = {
    "area": "hsr",
    "dates": dates,
    "common_valid_pixels": int(common.sum()),
    "indices": {},
    "limitations": [
        "Pilot P3 window, not an approved authoritative boundary.",
        "NDBI is not a built-up land-cover classification.",
        "No independent classification accuracy assessment.",
        "No urban-growth measurement or forecast performed."
    ]
}

for date, data in zip(dates, [old, new]):
    ndvi = normalized_difference(data["B08"], data["B04"])
    ndbi = normalized_difference(data["B11"], data["B08"])

    report["indices"][date] = {}

    for name, arr in [("NDVI", ndvi), ("NDBI", ndbi)]:
        values = arr[common & np.isfinite(arr)]

        if len(values) == 0:
            raise RuntimeError(f"No valid {name} values for {date}")

        stats = {
            "count": int(len(values)),
            "mean": float(np.mean(values)),
            "median": float(np.median(values)),
            "p05": float(np.percentile(values, 5)),
            "p95": float(np.percentile(values, 95))
        }

        report["indices"][date][name] = stats

        print(
            f"{date} {name}: "
            f"mean={stats['mean']:.4f}, "
            f"median={stats['median']:.4f}, "
            f"p05={stats['p05']:.4f}, "
            f"p95={stats['p95']:.4f}"
        )

REPORT.parent.mkdir(parents=True, exist_ok=True)
REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")

print("\nReport saved:", REPORT)
print("CALIBRATED SPECTRAL INDEX ANALYSIS: COMPLETE")

# Step 33: Paired spectral-index change analysis.
paired_report = {
    "area": "hsr",
    "date_from": dates[0],
    "date_to": dates[1],
    "indices": {},
    "interpretation": "Descriptive paired spectral changes only; not land-cover transitions."
}

for name, first, second in [
    (
        "NDVI",
        normalized_difference(old["B08"], old["B04"]),
        normalized_difference(new["B08"], new["B04"])
    ),
    (
        "NDBI",
        normalized_difference(old["B11"], old["B08"]),
        normalized_difference(new["B11"], new["B08"])
    ),
]:
    valid = common & np.isfinite(first) & np.isfinite(second)
    change = (second - first)[valid]

    if change.size == 0:
        raise RuntimeError(f"No paired values for {name}")

    stats = {
        "paired_pixels": int(change.size),
        "mean_change": float(np.mean(change)),
        "median_change": float(np.median(change)),
        "p05_change": float(np.percentile(change, 5)),
        "p95_change": float(np.percentile(change, 95)),
        "increased_pixels": int(np.count_nonzero(change > 0)),
        "decreased_pixels": int(np.count_nonzero(change < 0)),
        "unchanged_pixels": int(np.count_nonzero(change == 0))
    }

    paired_report["indices"][name] = stats

    print(f"\n{name} PAIRED CHANGE")
    for key, value in stats.items():
        print(f"  {key}: {value}")

paired_output = Path(
    "reports/p4_historical_growth/sentinel2_hsr_paired_changes.json"
)
paired_output.write_text(
    json.dumps(paired_report, indent=2),
    encoding="utf-8"
)

print("\nSaved:", paired_output)
print("PAIRED SPECTRAL CHANGE ANALYSIS: COMPLETE")

# Step 34: Export georeferenced paired spectral changes.
change_output = Path(
    "reports/p4_historical_growth/hsr_spectral_change_2017_2025.tif"
)

nodata_value = -9999.0

with rasterio.open(BASE / dates[0] / "hsr" / "SCL_20m.jp2") as reference:
    profile = {
        "driver": "GTiff",
        "height": int(window.height),
        "width": int(window.width),
        "count": 2,
        "dtype": "float32",
        "crs": reference.crs,
        "transform": window_transform(window, reference.transform),
        "nodata": nodata_value,
        "compress": "deflate"
    }

    ndvi_old = normalized_difference(old["B08"], old["B04"])
    ndvi_new = normalized_difference(new["B08"], new["B04"])
    ndbi_old = normalized_difference(old["B11"], old["B08"])
    ndbi_new = normalized_difference(new["B11"], new["B08"])

    change_output.parent.mkdir(parents=True, exist_ok=True)

    with rasterio.open(change_output, "w", **profile) as dst:
        for index, (name, before, after) in enumerate([
            ("NDVI_change", ndvi_old, ndvi_new),
            ("NDBI_change", ndbi_old, ndbi_new)
        ], start=1):

            valid = common & np.isfinite(before) & np.isfinite(after)

            change = np.full(
                before.shape, nodata_value, dtype=np.float32
            )
            change[valid] = after[valid] - before[valid]

            dst.write(change, index)
            dst.set_band_description(index, name)

            print(
                f"{name}: {int(valid.sum()):,} valid pixels"
            )

print("\nGeoTIFF saved:", change_output)
print("SPATIAL SPECTRAL CHANGE EXPORT: COMPLETE")
