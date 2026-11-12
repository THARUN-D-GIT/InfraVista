
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[3]

RAW_FEATURES = ROOT / "data/processed/p4_ml/feature_matrix_raw.csv"
METADATA = ROOT / "data/processed/p4_ml/feature_matrix_metadata.csv"
ASSIGNMENTS = ROOT / "reports/p4_clustering/kmeans_cluster_assignments.csv"

OUTPUT_DIR = ROOT / "reports/p4_clustering/cluster_screening"

FEATURE_COLUMNS = [
    "facility_count_hospital",
    "facility_count_clinic",
    "facility_count_school",
    "road_density_km_per_km2_motorised_network",
    "road_density_km_per_km2_pedestrian_cycle",
    "road_density_km_per_km2_service_and_track",
    "facility_count_transit_platform",
    "facility_count_transit_stop_position",
    "water_area_share",
    "waterway_density_km_per_km2_all",
    "waterway_density_km_per_km2_drain",
]

CLUSTER_DESCRIPTIONS = {
    0: (
        "Lower mapped healthcare facility counts and relatively "
        "higher mapped waterway density."
    ),
    1: (
        "Higher mapped healthcare, education and transit counts, "
        "alongside higher motorised road density."
    ),
    2: (
        "Relatively lower mapped waterway density and lower "
        "mapped facility counts compared with Cluster 1."
    ),
}

GENERAL_LIMITATIONS = [
    "Cluster labels describe similarities in mapped indicators; they are not priority rankings.",
    "Zero means no feature was mapped in the available data, not confirmed infrastructure absence.",
    "OSM completeness and facility inventory completeness are unverified.",
    "Geometry coverage measures grid overlap, not source-data completeness or accuracy.",
    "The analysis covers only the two pilot study areas.",
    "Infrastructure shortage, service adequacy and investment priority are not established.",
]


def load_inputs():
    for path in [RAW_FEATURES, METADATA, ASSIGNMENTS]:
        if not path.exists():
            raise FileNotFoundError(f"Required input not found: {path}")

    features = pd.read_csv(RAW_FEATURES)
    metadata = pd.read_csv(METADATA)
    assignments = pd.read_csv(ASSIGNMENTS)

    required_feature_columns = [
        "grid_id", "area_id", *FEATURE_COLUMNS
    ]
    required_metadata_columns = [
        "grid_id",
        "area_id",
        "minimum_indicator_coverage",
        "quality_flags",
        "coverage_review",
    ]
    required_assignment_columns = [
        "k", "grid_id", "area_id", "cluster"
    ]

    for name, frame, required in [
        ("Feature matrix", features, required_feature_columns),
        ("Metadata", metadata, required_metadata_columns),
        ("Assignments", assignments, required_assignment_columns),
    ]:
        missing = set(required) - set(frame.columns)
        if missing:
            raise ValueError(
                f"{name} is missing columns: {sorted(missing)}"
            )

    return features, metadata, assignments


def validate_unique_keys(frame, name):
    keys = ["grid_id", "area_id"]

    if frame[keys].isna().any().any():
        raise ValueError(f"{name} contains missing grid or area IDs.")

    duplicates = frame.duplicated(keys)
    if duplicates.any():
        raise ValueError(
            f"{name} contains duplicate grid/area keys:\n"
            f"{frame.loc[duplicates, keys].head()}"
        )


def prepare_screening_data(features, metadata, assignments):
    validate_unique_keys(features, "Feature matrix")
    validate_unique_keys(metadata, "Metadata")

    # Select only the baseline K=3 assignments.
    k3 = assignments.loc[assignments["k"] == 3].copy()

    if k3.empty:
        raise ValueError("No K=3 assignments were found.")

    validate_unique_keys(k3, "K=3 assignments")

    expected_keys = set(
        zip(features["grid_id"], features["area_id"])
    )
    assigned_keys = set(
        zip(k3["grid_id"], k3["area_id"])
    )
    metadata_keys = set(
        zip(metadata["grid_id"], metadata["area_id"])
    )

    if expected_keys != assigned_keys:
        raise ValueError(
            "K=3 assignments do not match the feature matrix keys. "
            f"Missing assignments: {len(expected_keys - assigned_keys)}; "
            f"unexpected assignments: {len(assigned_keys - expected_keys)}."
        )

    if expected_keys != metadata_keys:
        raise ValueError(
            "Metadata keys do not match the feature matrix keys."
        )

    if len(features) != 201:
        raise ValueError(
            f"Expected 201 feature rows; found {len(features)}."
        )

    for column in FEATURE_COLUMNS:
        features[column] = pd.to_numeric(
            features[column], errors="raise"
        )

        if not np.isfinite(features[column]).all():
            raise ValueError(
                f"Non-finite values found in feature: {column}"
            )

    metadata["minimum_indicator_coverage"] = pd.to_numeric(
        metadata["minimum_indicator_coverage"],
        errors="raise",
    )

    if not metadata["minimum_indicator_coverage"].between(0, 1).all():
        raise ValueError("Coverage values must be between 0 and 1.")

    k3["cluster"] = pd.to_numeric(
        k3["cluster"], errors="raise"
    ).astype(int)

    if set(k3["cluster"].unique()) != {0, 1, 2}:
        raise ValueError(
            "Expected exactly three K=3 clusters: 0, 1 and 2."
        )

    merged = features.merge(
        metadata,
        on=["grid_id", "area_id"],
        how="left",
        validate="one_to_one",
    )

    merged = merged.merge(
        k3[["grid_id", "area_id", "cluster"]],
        on=["grid_id", "area_id"],
        how="left",
        validate="one_to_one",
    )

    if merged["cluster"].isna().any():
        raise ValueError("Some grid cells have no cluster assignment.")

    merged["cluster"] = merged["cluster"].astype(int)

    merged["cluster_description"] = merged["cluster"].map(
        CLUSTER_DESCRIPTIONS
    )

    merged["screening_interpretation"] = (
        "Descriptive mapped-infrastructure profile only; "
        "not an infrastructure shortage assessment."
    )

    merged["quality_review_required"] = (
        merged["quality_flags"].fillna("").str.strip().ne("")
    )

    return merged.sort_values(
        ["area_id", "cluster", "grid_id"]
    ).reset_index(drop=True)


def build_cluster_summary(data):
    summaries = []

    for cluster_id in sorted(data["cluster"].unique()):
        group = data[data["cluster"] == cluster_id]

        area_counts = (
            group["area_id"]
            .value_counts()
            .sort_index()
            .to_dict()
        )

        all_flags = []
        for value in group["quality_flags"].fillna(""):
            all_flags.extend(
                flag.strip()
                for flag in str(value).split(";")
                if flag.strip()
            )

        flag_counts = pd.Series(all_flags).value_counts().to_dict()

        feature_means = {
            column: round(float(group[column].mean()), 6)
            for column in FEATURE_COLUMNS
        }

        summaries.append({
            "cluster": int(cluster_id),
            "cluster_description": CLUSTER_DESCRIPTIONS[cluster_id],
            "grid_count": int(len(group)),
            "area_distribution": {
                key: int(value)
                for key, value in area_counts.items()
            },
            "mean_minimum_indicator_coverage": round(
                float(group["minimum_indicator_coverage"].mean()), 6
            ),
            "median_minimum_indicator_coverage": round(
                float(group["minimum_indicator_coverage"].median()), 6
            ),
            "cells_below_50_percent_coverage": int(
                (group["minimum_indicator_coverage"] < 0.50).sum()
            ),
            "quality_review_cells": int(
                group["quality_review_required"].sum()
            ),
            "quality_flag_counts": {
                str(key): int(value)
                for key, value in flag_counts.items()
            },
            "mean_raw_indicator_values": feature_means,
            "interpretation": "Descriptive profile; not a priority ranking.",
        })

    return summaries


def build_area_context(data):
    results = []

    for area_id, group in data.groupby("area_id"):
        results.append({
            "area_id": str(area_id),
            "grid_count": int(len(group)),
            "cluster_distribution": {
                str(int(cluster)): int(count)
                for cluster, count in
                group["cluster"].value_counts().sort_index().items()
            },
            "mean_minimum_indicator_coverage": round(
                float(group["minimum_indicator_coverage"].mean()), 6
            ),
            "cells_below_50_percent_coverage": int(
                (group["minimum_indicator_coverage"] < 0.50).sum()
            ),
        })

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Generate descriptive K=3 infrastructure screening output."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=OUTPUT_DIR,
    )
    args = parser.parse_args()

    features, metadata, assignments = load_inputs()

    data = prepare_screening_data(
        features, metadata, assignments
    )

    cluster_summary = build_cluster_summary(data)
    area_context = build_area_context(data)

    args.output_dir.mkdir(parents=True, exist_ok=True)

    grid_output = args.output_dir / "grid_cluster_screening.csv"
    summary_output = args.output_dir / "cluster_profile_summary.csv"
    report_output = args.output_dir / "cluster_screening_report.json"

    data.to_csv(grid_output, index=False)

    pd.DataFrame(cluster_summary).to_csv(
        summary_output, index=False
    )

    report = {
        "status": "PASS",
        "screening_version": "p4_cluster_screening_v0.1.0",
        "method": "numpy_kmeans_k3_baseline",
        "study_area_count": int(data["area_id"].nunique()),
        "grid_cell_count": int(len(data)),
        "feature_count": len(FEATURE_COLUMNS),
        "cluster_count": 3,
        "cluster_descriptions": {
            str(key): value
            for key, value in CLUSTER_DESCRIPTIONS.items()
        },
        "clusters": cluster_summary,
        "area_context": area_context,
        "limitations": GENERAL_LIMITATIONS,
        "decision": {
            "primary_configuration": "K=3 provisional",
            "priority_ranking": "not_assessed",
            "infrastructure_shortage": "not_established",
            "service_adequacy": "not_established",
        },
        "outputs": {
            "grid_screening": str(grid_output),
            "cluster_summary": str(summary_output),
        },
    }

    with report_output.open("w", encoding="utf-8") as file:
        json.dump(report, file, indent=2, ensure_ascii=False)

    print("\nP4 CLUSTER SCREENING OUTPUT")
    print("=" * 45)
    print("Status: PASS")
    print("Grid cells:", len(data))
    print("Study areas:", data["area_id"].nunique())
    print("Features:", len(FEATURE_COLUMNS))
    print("Clusters:", data["cluster"].nunique())

    print("\nCluster sizes:")
    print(
        data.groupby("cluster")
        .size()
        .rename("grid_cells")
        .to_string()
    )

    print("\nCluster descriptions:")
    for item in cluster_summary:
        print(
            f"\nCluster {item['cluster']} "
            f"({item['grid_count']} cells)"
        )
        print(item["cluster_description"])
        print(
            "Mean minimum coverage:",
            item["mean_minimum_indicator_coverage"],
        )
        print(
            "Cells below 50% coverage:",
            item["cells_below_50_percent_coverage"],
        )

    print("\nOutputs:")
    print(grid_output)
    print(summary_output)
    print(report_output)

    print("\nImportant: These are descriptive clusters, not priority rankings.")


if __name__ == "__main__":
    main()
