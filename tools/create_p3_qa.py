from pathlib import Path
import geopandas as gpd
import matplotlib.pyplot as plt
import pandas as pd

RUN_ID = "20261106T140957Z_indicators"

INPUT = (
    Path("data/processed/p3")
    / RUN_ID
    / "indicators_grid.geojson"
)

OUTPUT = Path("reports/p3_qa") / RUN_ID
OUTPUT.mkdir(parents=True, exist_ok=True)

print("Reading P3 grid data...")
gdf = gpd.read_file(INPUT)

if gdf.crs is None:
    raise ValueError("Input GeoJSON has no CRS.")

if gdf.empty:
    raise ValueError("Input GeoJSON contains no features.")

if gdf.geometry.isna().any() or gdf.geometry.is_empty.any():
    raise ValueError("Null or empty geometries found.")

if (~gdf.geometry.is_valid).any():
    raise ValueError("Invalid geometries found.")

# Each map uses one indicator per grid cell.
maps = {
    "01_motorised_road_density": (
        "road_density_km_per_km2_motorised_network",
        "Motorised road density",
        "km per km2",
    ),
    "02_school_distribution": (
        "facility_count_school",
        "Mapped schools",
        "Count",
    ),
    "03_hospital_distribution": (
        "facility_count_hospital",
        "Mapped hospitals",
        "Count",
    ),
    "04_total_waterway_density": (
        "waterway_density_km_per_km2_all",
        "Total mapped waterway density",
        "km per km2",
    ),
    "05_drain_density": (
        "waterway_density_km_per_km2_drain",
        "Mapped drain density",
        "km per km2",
    ),
}

print("\nGenerating indicator maps...")

for filename, (indicator, title, units) in maps.items():
    subset = gdf[gdf["indicator_id"] == indicator].copy()

    if subset.empty:
        print("SKIPPED: no records for", indicator)
        continue

    fig, ax = plt.subplots(figsize=(10, 8))

    subset.plot(
        column="value",
        cmap="viridis",
        legend=True,
        edgecolor="white",
        linewidth=0.08,
        ax=ax,
        legend_kwds={"label": units, "shrink": 0.7},
    )

    ax.set_title(
        f"{title}\nHSR and Whitefield | {RUN_ID}",
        fontsize=13,
    )
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.set_aspect("equal")
    ax.grid(alpha=0.2)

    fig.tight_layout()
    fig.savefig(OUTPUT / f"{filename}.png", dpi=200)
    plt.close(fig)

    print("Created:", filename + ".png")

# Coverage fraction is repeated for each indicator.
# Use one indicator to avoid duplicate grid polygons.
coverage = gdf[
    gdf["indicator_id"]
    == "road_density_km_per_km2_motorised_network"
].copy()

fig, ax = plt.subplots(figsize=(10, 8))
coverage.plot(
    column="coverage_fraction",
    cmap="YlOrRd",
    legend=True,
    edgecolor="white",
    linewidth=0.08,
    ax=ax,
    vmin=0,
    vmax=1,
    legend_kwds={"label": "Fraction of grid cell inside study window"},
)
ax.set_title("Grid-cell coverage fraction\nHSR and Whitefield")
ax.set_xlabel("Longitude")
ax.set_ylabel("Latitude")
ax.set_aspect("equal")
ax.grid(alpha=0.2)
fig.tight_layout()
fig.savefig(OUTPUT / "06_grid_coverage_fraction.png", dpi=200)
plt.close(fig)

print("Created: 06_grid_coverage_fraction.png")

# Summary statistics for each indicator and zone.
rows = []

for (area, indicator), group in gdf.groupby(
    ["area_id", "indicator_id"]
):
    values = group["value"]

    rows.append({
        "area_id": area,
        "indicator_id": indicator,
        "record_count": len(group),
        "minimum": values.min(),
        "median": values.median(),
        "maximum": values.max(),
        "zero_value_count": int((values == 0).sum()),
        "partial_coverage_count": int(
            (group["coverage_fraction"] < 1).sum()
        ),
        "small_denominator_count": int(
            group["quality_flags"].fillna("").str.contains(
                "small_denominator", regex=False
            ).sum()
        ),
    })

summary = pd.DataFrame(rows)
summary.to_csv(OUTPUT / "indicator_summary.csv", index=False)

# Count quality flags. These are flag occurrences, not unique cells.
flag_counts = {}
for value in gdf["quality_flags"].fillna(""):
    for flag in value.split(";"):
        if flag:
            flag_counts[flag] = flag_counts.get(flag, 0) + 1

report = [
    "# P3 Spatial QA Report",
    "",
    f"**Run:** `{RUN_ID}`",
    "",
    "## Input checks",
    "",
    f"- Input records: {len(gdf)}",
    f"- CRS: {gdf.crs}",
    f"- Geometry types: {', '.join(gdf.geom_type.unique())}",
    f"- Invalid geometries: {int((~gdf.geometry.is_valid).sum())}",
    f"- Empty geometries: {int(gdf.geometry.is_empty.sum())}",
    f"- Null geometries: {int(gdf.geometry.isna().sum())}",
    f"- Zones: {', '.join(sorted(gdf['area_id'].unique()))}",
    "",
    "## Coverage",
    "",
    f"- Partial-coverage indicator records: {int((gdf['coverage_fraction'] < 1).sum())}",
    f"- Grid cells with zero coverage: {int((coverage['coverage_fraction'] == 0).sum())}",
    f"- Grid cells with partial coverage: {int(((coverage['coverage_fraction'] > 0) & (coverage['coverage_fraction'] < 1)).sum())}",
    f"- Grid cells with very small positive coverage (<0.001): {int(((coverage['coverage_fraction'] > 0) & (coverage['coverage_fraction'] < 0.001)).sum())}",
    f"- Minimum coverage fraction: {gdf['coverage_fraction'].min():.8f}",
    f"- Maximum coverage fraction: {gdf['coverage_fraction'].max():.8f}",
    "",
    "## Quality flag occurrences",
    "",
    "| Flag | Occurrences |",
    "|---|---:|",
]

for flag, count in sorted(flag_counts.items()):
    report.append(f"| `{flag}` | {count} |")

report.extend([
    "",
    "## Interpretation and limitations",
    "",
    "- These maps show derived indicators from mapped OSM features.",
    "- Zero means none mapped for that indicator, not confirmed absence.",
    "- OSM completeness is unverified.",
    "- Coverage fraction describes the share of a grid cell inside the study window; it is not an accuracy or completeness score.",
    "- Quality-flag counts are indicator-record occurrences, not unique grid-cell counts.",
    "- Very small positive-coverage boundary slivers are retained; cells flagged `small_denominator` should not be ranked.",
    "- Waterway and drain maps do not establish that the drainage network is complete or functional.",
    "- These outputs are not independently validated by P6.",
    "- OSM rights remain `review_required`; these outputs are for team review, not cleared for publication.",
    "",
    "## Generated files",
    "",
])

for filename in sorted(p.name for p in OUTPUT.glob("*.png")):
    report.append(f"- `{filename}`")

report.extend([
    "- `indicator_summary.csv`",
    "- `p3_spatial_qa_report.md`",
    "",
])

(OUTPUT / "p3_spatial_qa_report.md").write_text(
    "\n".join(report), encoding="utf-8"
)

print("\nQA summary:")
print("Output folder:", OUTPUT)
print("Maps created:", len(list(OUTPUT.glob("*.png"))))
print("Summary CSV:", OUTPUT / "indicator_summary.csv")
print("QA report:", OUTPUT / "p3_spatial_qa_report.md")
print("\nP3 QA map generation completed.")
