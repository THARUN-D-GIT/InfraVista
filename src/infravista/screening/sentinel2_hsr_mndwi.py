import json
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import rasterio
from rasterio.features import geometry_mask
from rasterio.warp import transform_geom
from rasterio.windows import from_bounds, transform as window_transform

BASE = Path("data/raw/historical_sentinel2")
GEOJSON = Path(
    r"C:\Users\Varun\AppData\Local\Temp\infravista_p4_audit\indicators_window.geojson"
)
OUTPUT = Path(
    "reports/p4_historical_growth/sentinel2_hsr_mndwi.json"
)

with GEOJSON.open(encoding="utf-8") as f:
    features = json.load(f)["features"]

hsr = next(
    f["geometry"] for f in features
    if f["properties"]["area_id"] == "hsr"
)

dates = ["2017-02-03", "2025-02-06"]
excluded_scl = [0, 1, 3, 7, 8, 9, 10, 11]

def calibration_for(date):
    root = ET.parse(BASE / date / "hsr" / "MTD_MSIL2A.xml").getroot()
    quant = None
    offsets = {}

    for element in root.iter():
        name = element.tag.rsplit("}", 1)[-1]

        if name == "BOA_QUANTIFICATION_VALUE":
            quant = float(element.text)

        elif name == "BOA_ADD_OFFSET":
            offsets[element.attrib.get("band_id")] = float(element.text)

    # Sentinel-2 MSI band IDs: B03=2, B11=11.
    if quant is None or "2" not in offsets or "11" not in offsets:
        raise RuntimeError(f"Incomplete B03/B11 calibration for {date}")

    return quant, offsets["2"], offsets["11"]

arrays = {}

with rasterio.open(BASE / dates[0] / "hsr" / "SCL_20m.jp2") as ref:
    projected = transform_geom("EPSG:4326", ref.crs, hsr)
    window = from_bounds(
        *rasterio.features.bounds(projected),
        transform=ref.transform
    ).round_offsets().round_lengths()

    inside = geometry_mask(
        [projected],
        out_shape=(int(window.height), int(window.width)),
        transform=window_transform(window, ref.transform),
        invert=True
    )

    for date in dates:
        folder = BASE / date / "hsr"
        quant, green_offset, swir_offset = calibration_for(date)

        print(f"\nDATE: {date}")
        print("BOA quantification:", quant)
        print("B03 offset:", green_offset)
        print("B11 offset:", swir_offset)

        with (
            rasterio.open(folder / "B03_20m.jp2") as green,
            rasterio.open(folder / "B11_20m.jp2") as swir,
            rasterio.open(folder / "SCL_20m.jp2") as scl
        ):
            for src in [green, swir, scl]:
                if (
                    src.crs != ref.crs
                    or src.shape != ref.shape
                    or not src.transform.almost_equals(ref.transform)
                ):
                    raise RuntimeError(f"Grid mismatch for {date}")

            green_dn = green.read(1, window=window).astype(np.float32)
            swir_dn = swir.read(1, window=window).astype(np.float32)
            scl_data = scl.read(1, window=window)

        valid = (
            inside
            & ~np.isin(scl_data, excluded_scl)
            & (green_dn > 0)
            & (swir_dn > 0)
        )

        green_rho = (green_dn + green_offset) / quant
        swir_rho = (swir_dn + swir_offset) / quant

        denominator = green_rho + swir_rho
        valid &= (
            np.isfinite(denominator)
            & (green_rho >= 0)
            & (swir_rho >= 0)
            & (np.abs(denominator) > 1e-6)
        )

        mndwi = np.full(green_rho.shape, np.nan, dtype=np.float32)
        np.divide(
            green_rho - swir_rho,
            denominator,
            out=mndwi,
            where=valid
        )

        arrays[date] = {"mndwi": mndwi, "valid": valid}

common = arrays[dates[0]]["valid"] & arrays[dates[1]]["valid"]

if not common.any():
    raise RuntimeError("No common valid MNDWI pixels")

report = {
    "area": "hsr",
    "common_valid_pixels": int(common.sum()),
    "dates": {},
    "limitations": [
        "Common mask applies to B03/B11 and SCL, not all spectral bands.",
        "MNDWI is water-sensitive, not a validated water classification.",
        "No built-up area or historical growth is estimated."
    ]
}

for date in dates:
    values = arrays[date]["mndwi"][common]
    stats = {
        "mean": float(values.mean()),
        "median": float(np.median(values)),
        "p05": float(np.percentile(values, 5)),
        "p95": float(np.percentile(values, 95))
    }
    report["dates"][date] = stats

    print(
        f"{date} MNDWI: mean={stats['mean']:.4f}, "
        f"median={stats['median']:.4f}, "
        f"p05={stats['p05']:.4f}, p95={stats['p95']:.4f}"
    )

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
OUTPUT.write_text(json.dumps(report, indent=2), encoding="utf-8")

print("\nCommon valid pixels:", int(common.sum()))
print("Report saved:", OUTPUT)
print("MNDWI CALIBRATION AND ANALYSIS: COMPLETE")
