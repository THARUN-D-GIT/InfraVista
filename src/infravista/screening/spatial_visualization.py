
"""Create spatial cluster outputs and exploratory maps for InfraVista P4."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.colors import ListedColormap


PROJECT_ROOT = Path(__file__).resolve().parents[3]

DEFAULT_GEOMETRY = (
    Path.home()
    / "AppData"
    / "Local"
    / "Temp"
    / "infravista_p4_audit"
    / "indicators_grid.geojson"
)

DEFAULT_ASSIGNMENTS = (
    PROJECT_ROOT
    / "reports"
    / "p4_clustering"
    / "cluster_screening"
    / "grid_cluster_screening.csv"
)

DEFAULT_OUTPUT = PROJECT_ROOT / "reports" / "p4_spatial"

CLUSTER_COLORS = ["#4C78A8", "#F2A541", "#59A14F"]


def recover_grid_ids(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Recover grid IDs from feature IDs using indicator suffixes."""

    required = {"feature_id", "indicator_id", "area_id"}

    missing = required - set(gdf.columns)
    if missing:
        raise ValueError(
            f"GeoJSON is missing required columns: {sorted(missing)}"
        )

    result = gdf.copy()

    recovered = []

    for feature_id, indicator_id in zip(
        result["feature_id"].astype(str),
        result["indicator_id"].astype(str),
    ):
        suffix = "_" + indicator_id

        if not feature_id.endswith(suffix):
            raise ValueError(
                f"Cannot recover grid ID from feature ID: {feature_id}"
            )

        recovered.append(feature_id[:-len(suffix)])

    result["grid_id"] = recovered

    if result["grid_id"].isna().any():
        raise ValueError("Recovered grid IDs contain missing values.")

    return result


def validate_geometry_records(
    gdf: gpd.GeoDataFrame,
) -> gpd.GeoDataFrame:
    """Validate geometry consistency and produce one polygon per grid."""

    if gdf.crs is None:
        raise ValueError("Source GeoJSON has no declared CRS.")

    if gdf.geometry.isna().any():
        raise ValueError("Source geometry contains missing geometries.")

    if gdf.geometry.is_empty.any():
        raise ValueError("Source geometry contains empty geometries.")

    if not gdf.geometry.is_valid.all():
        raise ValueError("Source geometry contains invalid geometries.")

    key_columns = ["grid_id", "area_id"]

    geometry_counts = (
        gdf.groupby(key_columns)["geometry"]
        .apply(lambda values: len({geometry.wkb for geometry in values}))
    )

    if (geometry_counts != 1).any():
        raise ValueError(
            "Conflicting geometries found for one or more grid cells."
        )

    grid_geometry = gdf[
        ["grid_id", "area_id", "geometry"]
    ].drop_duplicates(subset=key_columns)

    if grid_geometry.duplicated(key_columns).any():
        raise ValueError("Duplicate grid/area polygons remain.")

    return gpd.GeoDataFrame(
        grid_geometry,
        geometry="geometry",
        crs=gdf.crs,
    )


def validate_assignments(df: pd.DataFrame) -> None:
    """Validate the cluster assignment table."""

    required = {
        "grid_id",
        "area_id",
        "cluster",
        "minimum_indicator_coverage",
        "quality_flags",
        "coverage_review",
        "quality_review_required",
        "cluster_description",
        "screening_interpretation",
    }

    missing = required - set(df.columns)

    if missing:
        raise ValueError(
            f"Cluster CSV is missing required columns: {sorted(missing)}"
        )

    if df[["grid_id", "area_id"]].isna().any().any():
        raise ValueError("Cluster assignments contain missing identifiers.")

    if df.duplicated(["grid_id", "area_id"]).any():
        raise ValueError("Cluster assignments contain duplicate grid IDs.")

    if not pd.to_numeric(df["cluster"], errors="coerce").notna().all():
        raise ValueError("Cluster assignments contain invalid cluster IDs.")

    coverage = pd.to_numeric(
        df["minimum_indicator_coverage"],
        errors="coerce",
    )

    if coverage.isna().any() or not coverage.between(0, 1).all():
        raise ValueError("Minimum indicator coverage must be within [0, 1].")


def build_spatial_layer(
    geometry_path: Path,
    assignments_path: Path,
) -> gpd.GeoDataFrame:
    """Recover grid polygons and join existing cluster assignments."""

    if not geometry_path.exists():
        raise FileNotFoundError(
            f"Geometry file not found: {geometry_path}"
        )

    if not assignments_path.exists():
        raise FileNotFoundError(
            f"Assignment file not found: {assignments_path}"
        )

    source = gpd.read_file(geometry_path)
    assignments = pd.read_csv(assignments_path)

    source = recover_grid_ids(source)
    grid_geometry = validate_geometry_records(source)
    validate_assignments(assignments)

    geometry_keys = set(
        zip(grid_geometry["grid_id"], grid_geometry["area_id"])
    )
    assignment_keys = set(
        zip(assignments["grid_id"], assignments["area_id"])
    )

    if geometry_keys != assignment_keys:
        missing_geometry = sorted(assignment_keys - geometry_keys)
        missing_assignment = sorted(geometry_keys - assignment_keys)

        raise ValueError(
            "Geometry and assignment IDs do not match exactly. "
            f"Missing geometry: {missing_geometry[:5]}; "
            f"missing assignments: {missing_assignment[:5]}"
        )

    result = grid_geometry.merge(
        assignments,
        on=["grid_id", "area_id"],
        how="inner",
        validate="one_to_one",
    )

    result = gpd.GeoDataFrame(
        result,
        geometry="geometry",
        crs=grid_geometry.crs,
    )

    if len(result) != len(assignments):
        raise ValueError("Spatial join changed the assignment row count.")

    if result[["grid_id", "area_id"]].duplicated().any():
        raise ValueError("Spatial output contains duplicate grid cells.")

    return result


def build_spatial_summary(
    gdf: gpd.GeoDataFrame,
) -> dict:
    """Create descriptive spatial cluster and coverage statistics."""

    areas = []

    for area_id, area in gdf.groupby("area_id"):
        clusters = []

        for cluster_id, group in area.groupby("cluster"):
            clusters.append(
                {
                    "cluster": int(cluster_id),
                    "grid_count": int(len(group)),
                    "mean_minimum_indicator_coverage": float(
                        group["minimum_indicator_coverage"].mean()
                    ),
                    "cells_below_50_percent_coverage": int(
                        (
                            group["minimum_indicator_coverage"] < 0.50
                        ).sum()
                    ),
                    "quality_review_cells": int(
                        group["quality_review_required"]
                        .astype(str)
                        .str.lower()
                        .isin(["true", "1"])
                        .sum()
                    ),
                }
            )

        areas.append(
            {
                "area_id": str(area_id),
                "grid_count": int(len(area)),
                "cluster_distribution": clusters,
                "cells_below_50_percent_coverage": int(
                    (area["minimum_indicator_coverage"] < 0.50).sum()
                ),
            }
        )

    return {
        "report_type": "exploratory_spatial_cluster_visualization",
        "method": "existing_kmeans_k3_baseline_assignments",
        "source_geometry_crs": str(gdf.crs),
        "output_crs": "EPSG:4326",
        "grid_cell_count": int(len(gdf)),
        "area_count": int(gdf["area_id"].nunique()),
        "cluster_count": int(gdf["cluster"].nunique()),
        "areas": areas,
        "interpretation": (
            "Maps show descriptive mapped-infrastructure cluster "
            "patterns only. They do not establish infrastructure "
            "shortages, service adequacy, or investment priorities."
        ),
        "limitations": [
            "OSM completeness is unverified.",
            "Geometry coverage is not a measure of OSM completeness.",
            "P6 independent validation remains pending.",
            "OSM/ODbL rights review remains pending; team use only.",
            "Cluster assignments are exploratory and provisional.",
        ],
    }


def create_cluster_maps(
    gdf: gpd.GeoDataFrame,
    output_dir: Path,
) -> list[Path]:
    """Create individual cluster maps for each study area."""

    output_dir.mkdir(parents=True, exist_ok=True)

    cmap = ListedColormap(CLUSTER_COLORS)
    outputs = []

    for area_id in sorted(gdf["area_id"].unique()):
        area = gdf[gdf["area_id"] == area_id]

        fig, ax = plt.subplots(figsize=(9, 8))

        area.plot(
            column="cluster",
            categorical=True,
            cmap=cmap,
            legend=True,
            edgecolor="black",
            linewidth=0.15,
            ax=ax,
            legend_kwds={"title": "Cluster"},
        )

        ax.set_title(
            f"InfraVista — {str(area_id).upper()} "
            "Spatial Cluster Map\n"
            "Descriptive mapped-infrastructure profiles",
            fontsize=13,
        )

        ax.set_axis_off()
        fig.tight_layout()

        path = output_dir / f"cluster_map_{area_id}.png"
        fig.savefig(path, dpi=220, bbox_inches="tight")
        plt.close(fig)

        outputs.append(path)

    return outputs


def create_coverage_map(
    gdf: gpd.GeoDataFrame,
    output_dir: Path,
) -> Path:
    """Highlight cells requiring coverage review."""

    fig, axes = plt.subplots(
        1,
        gdf["area_id"].nunique(),
        figsize=(14, 7),
    )

    if not hasattr(axes, "__len__"):
        axes = [axes]

    for ax, area_id in zip(
        axes,
        sorted(gdf["area_id"].unique()),
    ):
        area = gdf[gdf["area_id"] == area_id]

        reviewed = area[
            area["minimum_indicator_coverage"] < 0.50
        ]
        remaining = area[
            area["minimum_indicator_coverage"] >= 0.50
        ]

        remaining.plot(
            ax=ax,
            color="#B8C5D1",
            edgecolor="white",
            linewidth=0.15,
        )

        if not reviewed.empty:
            reviewed.plot(
                ax=ax,
                color="#E45756",
                edgecolor="black",
                linewidth=0.2,
            )

        ax.set_title(str(area_id).upper())
        ax.set_axis_off()

    fig.suptitle(
        "InfraVista — Indicator Coverage Review\n"
        "Red: minimum indicator coverage below 0.50",
        fontsize=13,
    )

    fig.tight_layout()

    path = output_dir / "coverage_review_map.png"
    fig.savefig(path, dpi=220, bbox_inches="tight")
    plt.close(fig)

    return path


def generate_outputs(
    geometry_path: Path,
    assignments_path: Path,
    output_dir: Path,
) -> dict:
    """Generate all spatial outputs."""

    output_dir.mkdir(parents=True, exist_ok=True)

    spatial = build_spatial_layer(
        geometry_path,
        assignments_path,
    )

    # Preserve the original geographic output CRS.
    spatial = spatial.to_crs("EPSG:4326")

    geojson_path = output_dir / "spatial_cluster_grid.geojson"
    csv_path = output_dir / "spatial_cluster_grid.csv"
    summary_path = output_dir / "cluster_spatial_summary.json"

    spatial.to_file(
        geojson_path,
        driver="GeoJSON",
    )

    spatial.drop(columns="geometry").to_csv(
        csv_path,
        index=False,
    )

    summary = build_spatial_summary(spatial)

    summary_path.write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )

    cluster_maps = create_cluster_maps(spatial, output_dir)
    coverage_map = create_coverage_map(spatial, output_dir)

    return {
        "geojson": geojson_path,
        "csv": csv_path,
        "summary": summary_path,
        "cluster_maps": cluster_maps,
        "coverage_map": coverage_map,
        "grid_cell_count": len(spatial),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate InfraVista P4 spatial cluster outputs."
    )

    parser.add_argument(
        "--geometry",
        type=Path,
        default=DEFAULT_GEOMETRY,
    )
    parser.add_argument(
        "--assignments",
        type=Path,
        default=DEFAULT_ASSIGNMENTS,
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
    )

    args = parser.parse_args()

    outputs = generate_outputs(
        args.geometry,
        args.assignments,
        args.output,
    )

    print("\n========== SPATIAL OUTPUT GENERATION ==========")
    print("Status: PASS")
    print("Grid cells:", outputs["grid_cell_count"])

    for key, value in outputs.items():
        if key != "grid_cell_count":
            print(f"{key}: {value}")


if __name__ == "__main__":
    main()
