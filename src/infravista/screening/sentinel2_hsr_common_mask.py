import json
import xml.etree.ElementTree as ET
from pathlib import Path
from contextlib import ExitStack

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.vrt import WarpedVRT
from rasterio.features import geometry_mask
from rasterio.warp import transform_geom
from rasterio.windows import from_bounds, transform as window_transform

BASE = Path("data/raw/historical_sentinel2")
OUT = Path("reports/p4_historical_growth")
GEOJSON = Path(
    r"C:\Users\Varun\AppData\Local\Temp\infravista_p4_audit\indicators_window.geojson"
)

DATES = ["2017-02-03", "2025-02-06"]
BANDS = {
    "B03": ("B03_20m.jp2", "2"),
    "B04": ("B04_20m.jp2", "3"),
    "B08": ("B08_10m.jp2", "7"),
    "B11": ("B11_20m.jp2", "11"),
    "B12": ("B12_20m.jp2", "12"),
}
EXCLUDED_SCL = [0, 1, 3, 7, 8, 9, 10, 11]

with GEOJSON.open(encoding="utf-8") as f:
    features = json.load(f)["features"]

hsr = next(
    f["geometry"] for f in features
    if f["properties"]["area_id"] == "hsr"
)

def get_calibration(date):
    root = ET.parse(BASE / date / "hsr" / "MTD_MSIL2A.xml").getroot()
    quant = None
    offsets = {}

    for element in root.iter():
        name = element.tag.rsplit("}", 1)[-1]
        if name == "BOA_QUANTIFICATION_VALUE":
            quant = float(element.text)
        elif name == "BOA_ADD_OFFSET":
            offsets[element.attrib["band_id"]] = float(element.text)

    if quant is None or quant <= 0:
        raise RuntimeError(f"Invalid calibration for {date}")

    for band, (_, band_id) in BANDS.items():
        if band_id not in offsets:
            raise RuntimeError(f"Missing offset for {date} {band}")

    return quant, offsets

def index(a, b):
    result = np.full(a.shape, np.nan, dtype=np.float32)
    denominator = a + b
    np.divide(
        a - b,
        denominator,
        out=result,
        where=np.isfinite(denominator) & (np.abs(denominator) > 1e-6)
    )
    return result

with rasterio.open(BASE / DATES[0] / "hsr" / "SCL_20m.jp2") as ref:
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

    datasets = {}
    common = inside.copy()

    for date in DATES:
        folder = BASE / date / "hsr"
        quant, offsets = get_calibration(date)
        data = {}

        with ExitStack() as stack:
            scl_src = stack.enter_context(
                rasterio.open(folder / "SCL_20m.jp2")
            )
            if (
                scl_src.crs != ref.crs
                or scl_src.shape != ref.shape
                or not scl_src.transform.almost_equals(ref.transform)
            ):
                raise RuntimeError(f"SCL grid mismatch: {date}")

            scl = scl_src.read(1, window=window)
            valid = inside & ~np.isin(scl, EXCLUDED_SCL)

            for band, (filename, band_id) in BANDS.items():
                src = stack.enter_context(rasterio.open(folder / filename))

                if src.crs != ref.crs:
                    raise RuntimeError(f"CRS mismatch: {date} {band}")

                if band == "B08":
                    vrt = stack.enter_context(
                        WarpedVRT(
                            src,
                            crs=ref.crs,
                            transform=ref.transform,
                            width=ref.width,
                            height=ref.height,
                            resampling=Resampling.average
                        )
                    )
                    dn = vrt.read(1, window=window).astype(np.float32)
                else:
                    if (
                        src.shape != ref.shape
                        or not src.transform.almost_equals(ref.transform)
                    ):
                        raise RuntimeError(f"Grid mismatch: {date} {band}")

                    dn = src.read(1, window=window).astype(np.float32)

                rho = (dn + offsets[band_id]) / quant
                valid &= (
                    (dn > 0)
                    & np.isfinite(rho)
                    & (rho >= 0)
                )
                data[band] = rho

            datasets[date] = data
            common &= valid

    if not common.any():
        raise RuntimeError("No common valid pixels")

    report = {
        "area": "hsr",
        "dates": DATES,
        "common_valid_pixels": int(common.sum()),
        "total_window_pixels": int(inside.sum()),
        "indices": {},
        "limitations": [
            "Pilot boundary only.",
            "No independent classification validation.",
            "Spectral indices are not direct built-up measurements."
        ]
    }

    for date in DATES:
        d = datasets[date]
        indices = {
            "NDVI": index(d["B08"], d["B04"]),
            "NDBI": index(d["B11"], d["B08"]),
            "MNDWI": index(d["B03"], d["B11"])
        }

        report["indices"][date] = {}

        for name, arr in indices.items():
            values = arr[common & np.isfinite(arr)]

            stats = {
                "count": int(values.size),
                "mean": float(values.mean()),
                "median": float(np.median(values)),
                "p05": float(np.percentile(values, 5)),
                "p95": float(np.percentile(values, 95))
            }

            report["indices"][date][name] = stats
            print(
                f"{date} {name}: "
                f"n={stats['count']}, "
                f"mean={stats['mean']:.4f}, "
                f"median={stats['median']:.4f}"
            )

    mask_path = OUT / "hsr_common_spectral_mask_2017_2025.tif"

    profile = {
        "driver": "GTiff",
        "height": int(window.height),
        "width": int(window.width),
        "count": 1,
        "dtype": "uint8",
        "crs": ref.crs,
        "transform": window_transform(window, ref.transform),
        "nodata": 0,
        "compress": "deflate"
    }

    OUT.mkdir(parents=True, exist_ok=True)

    with rasterio.open(mask_path, "w", **profile) as dst:
        dst.write(common.astype(np.uint8), 1)
        dst.set_band_description(1, "Common valid spectral pixels")

    report_path = OUT / "sentinel2_hsr_common_spectral_indices.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("\nCommon valid pixels:", int(common.sum()))
    print("Total window pixels:", int(inside.sum()))
    print("Mask saved:", mask_path)
    print("Report saved:", report_path)
    print("COMMON SPECTRAL MASK: COMPLETE")
