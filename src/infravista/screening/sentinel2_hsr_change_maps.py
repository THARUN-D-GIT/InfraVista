from pathlib import Path

import numpy as np
import rasterio
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm

SOURCE = Path(
    "reports/p4_historical_growth/hsr_spectral_change_2017_2025.tif"
)
OUTPUT = Path("reports/p4_historical_growth/maps")
OUTPUT.mkdir(parents=True, exist_ok=True)

with rasterio.open(SOURCE) as src:
    ndvi = src.read(1, masked=True)
    ndbi = src.read(2, masked=True)

    print("CRS:", src.crs)
    print("Resolution:", src.res)
    print("Raster dimensions:", src.width, "x", src.height)

def save_map(array, title, filename, limit=0.4):
    fig, ax = plt.subplots(figsize=(8, 7))

    image = ax.imshow(
        array,
        cmap="RdBu",
        norm=TwoSlopeNorm(
            vmin=-limit,
            vcenter=0,
            vmax=limit
        ),
        interpolation="nearest"
    )

    ax.set_title(title, fontsize=13)
    ax.set_xlabel("Raster column")
    ax.set_ylabel("Raster row")

    fig.colorbar(
        image,
        ax=ax,
        label="Index change (2025 - 2017)",
        shrink=0.8
    )

    fig.tight_layout()
    path = OUTPUT / filename
    fig.savefig(path, dpi=180)
    plt.close(fig)
    print("Saved:", path)

save_map(
    ndvi,
    "HSR NDVI Change: 2017 to 2025",
    "hsr_ndvi_change.png"
)

save_map(
    ndbi,
    "HSR NDBI Change: 2017 to 2025",
    "hsr_ndbi_change.png"
)

fig, axes = plt.subplots(1, 2, figsize=(14, 6))

for ax, data, title in zip(
    axes,
    [ndvi, ndbi],
    ["NDVI Change", "NDBI Change"]
):
    im = ax.imshow(
        data,
        cmap="RdBu",
        norm=TwoSlopeNorm(
            vmin=-0.4,
            vcenter=0,
            vmax=0.4
        ),
        interpolation="nearest"
    )
    ax.set_title(title)
    ax.set_xlabel("Raster column")
    ax.set_ylabel("Raster row")

fig.suptitle("HSR Pilot Window: Spectral Change 2017–2025")
fig.colorbar(
    im,
    ax=axes,
    shrink=0.8,
    label="Index change (2025 - 2017)"
)

combined = OUTPUT / "hsr_spectral_change_comparison.png"
fig.savefig(combined, dpi=180, bbox_inches="tight")
plt.close(fig)

print("Saved:", combined)
print("SPECTRAL CHANGE MAP GENERATION: COMPLETE")
