import json
from pathlib import Path
from contextlib import ExitStack

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.vrt import WarpedVRT
from rasterio.windows import from_bounds
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap, BoundaryNorm
from matplotlib.patches import Patch

BASE = Path("data/raw/historical_sentinel2")
OUT = Path("reports/p4_historical_growth")
MAPS = OUT / "maps"
MAPS.mkdir(parents=True, exist_ok=True)

DATES = ["2017-02-03", "2025-02-06"]
THRESHOLD = 0.05

mask_path = OUT / "hsr_common_spectral_mask_2017_2025.tif"

def ndi(a, b):
    result = np.full(a.shape, np.nan, dtype=np.float32)
    denominator = a + b
    np.divide(
        a - b,
        denominator,
        out=result,
        where=np.isfinite(denominator) & (np.abs(denominator) > 1e-6)
    )
    return result

with rasterio.open(mask_path) as mask_src:
    common_mask = mask_src.read(1) == 1
    shape = common_mask.shape
    profile = mask_src.profile.copy()
    mask_bounds = mask_src.bounds

candidates = {}

for date in DATES:
    folder = BASE / date / "hsr"

    with ExitStack() as stack:
        ref = stack.enter_context(
            rasterio.open(folder / "SCL_20m.jp2")
        )

        window = from_bounds(
            *mask_bounds,
            transform=ref.transform
        ).round_offsets().round_lengths()

        if (
            ref.crs != profile["crs"]
            or not rasterio.windows.transform(
                window, ref.transform
            ).almost_equals(profile["transform"])
            or (int(window.height), int(window.width)) != shape
        ):
            raise RuntimeError(f"Reference alignment mismatch: {date}")

        def read_band(filename, resample=False):
            src = stack.enter_context(
                rasterio.open(folder / filename)
            )

            if resample:
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
                return vrt.read(1, window=window).astype(np.float32)

            if (
                src.crs != ref.crs
                or src.shape != ref.shape
                or not src.transform.almost_equals(ref.transform)
            ):
                raise RuntimeError(f"Band alignment mismatch: {filename}")

            return src.read(1, window=window).astype(np.float32)

        green = (read_band("B03_20m.jp2") - 1000) / 10000
        red = (read_band("B04_20m.jp2") - 1000) / 10000
        nir = (read_band("B08_10m.jp2", True) - 1000) / 10000
        swir = (read_band("B11_20m.jp2") - 1000) / 10000

        ndvi = ndi(nir, red)
        ndbi = ndi(swir, nir)
        mndwi = ndi(green, swir)

        candidate = (
            common_mask
            & np.isfinite(ndvi)
            & np.isfinite(ndbi)
            & np.isfinite(mndwi)
            & (ndbi > THRESHOLD)
            & (ndbi > ndvi)
            & (mndwi < 0)
        )

        candidates[date] = candidate

        print(
            f"{date} candidate pixels:",
            int(candidate.sum())
        )

old = candidates[DATES[0]]
new = candidates[DATES[1]]

transition = np.zeros(shape, dtype=np.uint8)

transition[common_mask & ~old & ~new] = 1
transition[common_mask & old & new] = 2
transition[common_mask & old & ~new] = 3
transition[common_mask & ~old & new] = 4

labels = {
    1: "Non-candidate both dates",
    2: "Candidate both dates",
    3: "Candidate only in 2017",
    4: "Candidate only in 2025"
}

counts = {
    labels[value]: int(np.count_nonzero(transition == value))
    for value in labels
}

assert sum(counts.values()) == int(common_mask.sum())
assert counts[labels[2]] + counts[labels[3]] == int(old.sum())
assert counts[labels[2]] + counts[labels[4]] == int(new.sum())

print("\nTRANSITION COUNTS")
for label, count in counts.items():
    print(f"{label}: {count:,}")

tif_path = OUT / "hsr_candidate_transition_2017_2025.tif"

profile.update(
    driver="GTiff",
    dtype="uint8",
    count=1,
    nodata=0,
    compress="deflate"
)

with rasterio.open(tif_path, "w", **profile) as dst:
    dst.write(transition, 1)
    dst.set_band_description(1, "Exploratory candidate transitions")
    dst.update_tags(
        rule="NDBI > 0.05 AND NDBI > NDVI AND MNDWI < 0",
        status="exploratory_unvalidated"
    )

colors = [
    "#eeeeee",
    "#d6d6d6",
    "#396b9c",
    "#df9251",
    "#58a878"
]

cmap = ListedColormap(colors)
norm = BoundaryNorm(np.arange(-0.5, 5.5, 1), cmap.N)

fig, ax = plt.subplots(figsize=(9, 8))
ax.imshow(transition, cmap=cmap, norm=norm, interpolation="nearest")
ax.set_title(
    "HSR candidate spectral transitions (2017–2025)\n"
    "Exploratory screening — not validated urban growth"
)
ax.set_axis_off()

legend = [
    Patch(facecolor=colors[i], label=labels[i])
    for i in labels
]

ax.legend(
    handles=legend,
    loc="lower center",
    bbox_to_anchor=(0.5, -0.08),
    ncol=2,
    fontsize=9
)

fig.tight_layout()
png_path = MAPS / "hsr_candidate_transition_2017_2025.png"
fig.savefig(png_path, dpi=180, bbox_inches="tight")
plt.close(fig)

report = {
    "area": "hsr",
    "dates": DATES,
    "threshold": THRESHOLD,
    "rule": "NDBI > threshold AND NDBI > NDVI AND MNDWI < 0",
    "common_valid_pixels": int(common_mask.sum()),
    "candidate_2017": int(old.sum()),
    "candidate_2025": int(new.sum()),
    "transition_counts": counts,
    "limitations": [
        "Exploratory spectral-screening transitions only.",
        "Not a validated built-up land-cover classification.",
        "Candidate losses are not confirmed demolition.",
        "Candidate gains are not confirmed construction.",
        "No urban growth rate or area estimate is established."
    ]
}

json_path = OUT / "hsr_candidate_transition_2017_2025.json"
json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

print("\nSaved GeoTIFF:", tif_path)
print("Saved PNG:", png_path)
print("Saved JSON:", json_path)
print("CANDIDATE TRANSITION ANALYSIS: COMPLETE")
