import json
from pathlib import Path

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.vrt import WarpedVRT

BASE = Path("data/raw/historical_sentinel2")
OUT = Path("reports/p4_historical_growth")
DATES = ["2017-02-03", "2025-02-06"]

mask_path = OUT / "hsr_common_spectral_mask_2017_2025.tif"

with rasterio.open(mask_path) as ref:
    mask = ref.read(1) == 1
    transform = ref.transform
    crs = ref.crs
    shape = ref.shape

    results = {}

    for date in DATES:
        folder = BASE / date / "hsr"

        with rasterio.open(folder / "SCL_20m.jp2") as full_ref:
            from rasterio.windows import from_bounds

            bounds = rasterio.transform.array_bounds(
                shape[0], shape[1], transform
            )
            window = from_bounds(
                *bounds, transform=full_ref.transform
            ).round_offsets().round_lengths()

            def read_band(filename, resample=False):
                with rasterio.open(folder / filename) as src:
                    if resample:
                        with WarpedVRT(
                            src,
                            crs=full_ref.crs,
                            transform=full_ref.transform,
                            width=full_ref.width,
                            height=full_ref.height,
                            resampling=Resampling.average
                        ) as vrt:
                            return vrt.read(1, window=window).astype(np.float32)

                    return src.read(1, window=window).astype(np.float32)

            green = (read_band("B03_20m.jp2") - 1000) / 10000
            red = (read_band("B04_20m.jp2") - 1000) / 10000
            nir = (read_band("B08_10m.jp2", True) - 1000) / 10000
            swir = (read_band("B11_20m.jp2") - 1000) / 10000

            def ndi(a, b):
                result = np.full(a.shape, np.nan, dtype=np.float32)
                np.divide(
                    a - b, a + b, out=result,
                    where=np.abs(a + b) > 1e-6
                )
                return result

            ndvi = ndi(nir, red)
            ndbi = ndi(swir, nir)
            mndwi = ndi(green, swir)

            if ndvi.shape != shape:
                raise RuntimeError("Window alignment mismatch")

            print(f"\nDATE: {date}")
            results[date] = {}

            for threshold in [0.0, 0.05, 0.10]:
                candidate = (
                    mask
                    & np.isfinite(ndvi)
                    & np.isfinite(ndbi)
                    & np.isfinite(mndwi)
                    & (ndbi > threshold)
                    & (ndbi > ndvi)
                    & (mndwi < 0)
                )

                count = int(candidate.sum())
                percentage = round(
                    100 * count / int(mask.sum()), 4
                )

                results[date][str(threshold)] = {
                    "candidate_pixels": count,
                    "percentage_of_valid_pixels": percentage
                }

                print(
                    f"NDBI > {threshold:.2f}: "
                    f"{count:,} candidate pixels "
                    f"({percentage:.4f}%)"
                )

report = {
    "area": "hsr",
    "method": "Exploratory NDVI/NDBI/MNDWI candidate screening",
    "thresholds": [0.0, 0.05, 0.10],
    "results": results,
    "limitations": [
        "Candidate pixels are not validated built-up pixels.",
        "Bare soil and other surfaces may be misclassified.",
        "No independent reference labels or accuracy assessment.",
        "No urban-growth estimate should be derived from these counts."
    ]
}

output = OUT / "hsr_candidate_builtup_sensitivity.json"
output.write_text(json.dumps(report, indent=2), encoding="utf-8")

print("\nSaved:", output)
print("CANDIDATE BUILT-UP SENSITIVITY: COMPLETE")
