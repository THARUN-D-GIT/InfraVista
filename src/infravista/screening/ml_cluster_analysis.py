
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


# ============================================================
# CONFIGURATION
# ============================================================

ROOT_DIR = Path(__file__).resolve().parents[3]

RAW_FEATURES_PATH = (
    ROOT_DIR / "data" / "processed" / "p4_ml"
    / "feature_matrix_raw.csv"
)

METADATA_PATH = (
    ROOT_DIR / "data" / "processed" / "p4_ml"
    / "feature_matrix_metadata.csv"
)

ASSIGNMENTS_PATH = (
    ROOT_DIR / "reports" / "p4_clustering"
    / "kmeans_cluster_assignments.csv"
)

OUTPUT_DIR = (
    ROOT_DIR / "reports" / "p4_clustering"
    / "cluster_analysis"
)

CANDIDATE_K_VALUES = [3, 4]

ID_COLUMNS = ["grid_id", "area_id"]


# ============================================================
# LOAD AND VALIDATE INPUT FILES
# ============================================================

def load_inputs():

    required_files = [
        RAW_FEATURES_PATH,
        METADATA_PATH,
        ASSIGNMENTS_PATH,
    ]

    for path in required_files:
        if not path.exists():
            raise FileNotFoundError(
                f"Required input file not found: {path}"
            )

    raw = pd.read_csv(RAW_FEATURES_PATH)
    metadata = pd.read_csv(METADATA_PATH)
    assignments = pd.read_csv(ASSIGNMENTS_PATH)

    # Validate feature and metadata identifiers.
    for name, frame in [
        ("Raw features", raw),
        ("Metadata", metadata),
    ]:

        missing = [
            column for column in ID_COLUMNS
            if column not in frame.columns
        ]

        if missing:
            raise ValueError(
                f"{name} is missing required columns: {missing}"
            )

        if frame.duplicated(ID_COLUMNS).any():
            raise ValueError(
                f"{name} contains duplicate grid_id/area_id pairs."
            )

    # Validate long-format assignment columns.
    required_assignment_columns = [
        "k",
        "grid_id",
        "area_id",
        "cluster",
    ]

    missing = [
        column for column in required_assignment_columns
        if column not in assignments.columns
    ]

    if missing:
        raise ValueError(
            "Assignments file is missing columns: "
            f"{missing}"
        )

    # Duplicates are allowed across different K values,
    # but not within the same K and grid cell.
    if assignments.duplicated(
        ["k", "grid_id", "area_id"]
    ).any():
        raise ValueError(
            "Duplicate assignments found for the same "
            "K value and grid cell."
        )

    assignments["k"] = pd.to_numeric(
        assignments["k"],
        errors="raise",
    ).astype(int)

    assignments["cluster"] = pd.to_numeric(
        assignments["cluster"],
        errors="raise",
    ).astype(int)

    raw = raw.sort_values(
        ID_COLUMNS
    ).reset_index(drop=True)

    metadata = metadata.sort_values(
        ID_COLUMNS
    ).reset_index(drop=True)

    return raw, metadata, assignments


# ============================================================
# MERGE DATASETS
# ============================================================

def prepare_dataset(raw, metadata, assignments):

    # Merge raw features with metadata.
    merged = raw.merge(
        metadata,
        on=ID_COLUMNS,
        how="left",
        validate="one_to_one",
        suffixes=("", "_metadata"),
    )

    # Validate required metadata.
    required_metadata = [
        "minimum_indicator_coverage",
        "quality_flags",
    ]

    for column in required_metadata:

        if column not in merged.columns:
            raise ValueError(
                f"Missing metadata column: {column}"
            )

        if merged[column].isna().any():
            raise ValueError(
                f"Missing values in metadata column: {column}"
            )

    merged["minimum_indicator_coverage"] = pd.to_numeric(
        merged["minimum_indicator_coverage"],
        errors="raise",
    )

    coverage_values = merged[
        "minimum_indicator_coverage"
    ].to_numpy(dtype=float)

    if not np.isfinite(coverage_values).all():
        raise ValueError(
            "Geometry coverage contains non-finite values."
        )

    if (
        (coverage_values < 0).any()
        or (coverage_values > 1).any()
    ):
        raise ValueError(
            "Geometry coverage must be between 0 and 1."
        )

    # Match assignments to the feature matrix.
    expected_keys = set(
        zip(raw["grid_id"], raw["area_id"])
    )

    # Extract and merge each candidate K separately.
    for k in CANDIDATE_K_VALUES:

        selected = assignments[
            assignments["k"] == k
        ].copy()

        if selected.empty:
            raise ValueError(
                f"No cluster assignments found for K={k}."
            )

        selected = selected[
            ID_COLUMNS + ["cluster"]
        ]

        actual_keys = set(
            zip(
                selected["grid_id"],
                selected["area_id"],
            )
        )

        if actual_keys != expected_keys:
            missing_keys = expected_keys - actual_keys
            extra_keys = actual_keys - expected_keys

            raise ValueError(
                f"K={k} assignment mismatch. "
                f"Missing cells: {len(missing_keys)}, "
                f"unexpected cells: {len(extra_keys)}."
            )

        if len(selected) != len(raw):
            raise ValueError(
                f"K={k}: expected {len(raw)} assignments, "
                f"found {len(selected)}."
            )

        # Give each K configuration its own cluster column.
        selected = selected.rename(
            columns={
                "cluster": f"k{k}_cluster"
            }
        )

        merged = merged.merge(
            selected,
            on=ID_COLUMNS,
            how="left",
            validate="one_to_one",
        )

        cluster_column = f"k{k}_cluster"

        if merged[cluster_column].isna().any():
            raise ValueError(
                f"K={k}: missing cluster assignments."
            )

        merged[cluster_column] = (
            merged[cluster_column].astype(int)
        )

        actual_clusters = sorted(
            merged[cluster_column].unique().tolist()
        )

        expected_clusters = list(range(k))

        if actual_clusters != expected_clusters:
            raise ValueError(
                f"K={k}: expected clusters "
                f"{expected_clusters}, "
                f"found {actual_clusters}."
            )

    if len(merged) != len(raw):
        raise ValueError(
            "Unexpected row count after merging datasets."
        )

    return merged


# ============================================================
# IDENTIFY FEATURE COLUMNS
# ============================================================

def get_feature_columns(raw):

    features = [
        column for column in raw.columns
        if column not in ID_COLUMNS
    ]

    if not features:
        raise ValueError(
            "No feature columns found."
        )

    for column in features:
        raw[column] = pd.to_numeric(
            raw[column],
            errors="raise",
        )

    feature_values = raw[
        features
    ].to_numpy(dtype=float)

    if not np.isfinite(feature_values).all():
        raise ValueError(
            "Raw feature matrix contains NaN or infinite values."
        )

    return features


# ============================================================
# 1. CLUSTER FEATURE PROFILES
# ============================================================

def calculate_feature_profiles(merged, features):

    results = []

    for k in CANDIDATE_K_VALUES:

        cluster_column = f"k{k}_cluster"

        for cluster_id, group in merged.groupby(
            cluster_column,
            sort=True,
        ):

            for feature in features:

                values = group[
                    feature
                ].astype(float)

                results.append({
                    "k": k,
                    "cluster": int(cluster_id),
                    "feature": feature,
                    "cell_count": len(group),
                    "mean": float(values.mean()),
                    "median": float(values.median()),
                    "std": float(values.std(ddof=0)),
                    "minimum": float(values.min()),
                    "maximum": float(values.max()),
                })

    return pd.DataFrame(results)


# ============================================================
# 2. AREA-WISE CLUSTER DISTRIBUTION
# ============================================================

def calculate_area_distribution(merged):

    all_distributions = []

    for k in CANDIDATE_K_VALUES:

        cluster_column = f"k{k}_cluster"

        distribution = (
            merged.groupby(
                [cluster_column, "area_id"]
            )
            .size()
            .reset_index(name="cell_count")
            .rename(columns={
                cluster_column: "cluster"
            })
        )

        distribution.insert(0, "k", k)

        all_distributions.append(distribution)

    return pd.concat(
        all_distributions,
        ignore_index=True,
    )


# ============================================================
# 3. CLUSTER COVERAGE AND QUALITY ANALYSIS
# ============================================================

def calculate_coverage_quality(merged):

    results = []

    for k in CANDIDATE_K_VALUES:

        cluster_column = f"k{k}_cluster"

        for cluster_id, group in merged.groupby(
            cluster_column,
            sort=True,
        ):

            coverage = group[
                "minimum_indicator_coverage"
            ].astype(float)

            low_coverage = coverage < 0.50

            results.append({
                "k": k,
                "cluster": int(cluster_id),
                "cell_count": len(group),
                "mean_geometry_coverage": float(
                    coverage.mean()
                ),
                "median_geometry_coverage": float(
                    coverage.median()
                ),
                "minimum_geometry_coverage": float(
                    coverage.min()
                ),
                "maximum_geometry_coverage": float(
                    coverage.max()
                ),
                "cells_below_50pct_coverage": int(
                    low_coverage.sum()
                ),
                "low_coverage_percentage": float(
                    low_coverage.mean() * 100
                ),
                "quality_flagged_cells": int(
                    group["quality_flags"]
                    .fillna("")
                    .astype(str)
                    .str.strip()
                    .ne("")
                    .sum()
                ),
            })

    return pd.DataFrame(results)


# ============================================================
# 4. CLUSTER SIZE SUMMARY
# ============================================================

def calculate_cluster_sizes(merged):

    results = []

    for k in CANDIDATE_K_VALUES:

        cluster_column = f"k{k}_cluster"

        counts = (
            merged[cluster_column]
            .value_counts()
            .sort_index()
        )

        for cluster_id, count in counts.items():

            results.append({
                "k": k,
                "cluster": int(cluster_id),
                "cell_count": int(count),
                "percentage_of_all_cells": round(
                    count / len(merged) * 100,
                    2,
                ),
            })

    return pd.DataFrame(results)


# ============================================================
# 5. OVERALL FEATURE REFERENCE
# ============================================================

def calculate_overall_feature_reference(
    merged,
    features,
):

    results = []

    for feature in features:

        values = merged[
            feature
        ].astype(float)

        results.append({
            "feature": feature,
            "overall_mean": float(values.mean()),
            "overall_median": float(values.median()),
            "overall_std": float(values.std(ddof=0)),
        })

    return pd.DataFrame(results)


# ============================================================
# SAVE OUTPUTS
# ============================================================

def save_outputs(
    profiles,
    area_distribution,
    coverage_quality,
    cluster_sizes,
    overall_reference,
):

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    outputs = {
        "cluster_feature_profiles.csv": profiles,
        "cluster_area_distribution.csv": area_distribution,
        "cluster_coverage_quality.csv": coverage_quality,
        "cluster_sizes.csv": cluster_sizes,
        "overall_feature_reference.csv": overall_reference,
    }

    for filename, dataframe in outputs.items():

        output_path = OUTPUT_DIR / filename

        dataframe.to_csv(
            output_path,
            index=False,
        )

        print(f"[SAVED] {output_path}")


# ============================================================
# PRINT INTERPRETATION SUMMARY
# ============================================================

def print_summary(
    merged,
    profiles,
    area_distribution,
    coverage_quality,
    cluster_sizes,
    features,
):

    print("\n" + "=" * 70)
    print("INFRAVISTA - CLUSTER ANALYSIS")
    print("=" * 70)

    print(f"Total grid cells: {len(merged)}")
    print(f"Total features: {len(features)}")
    print(
        f"Study areas: "
        f"{sorted(merged['area_id'].unique().tolist())}"
    )

    for k in CANDIDATE_K_VALUES:

        print("\n" + "-" * 70)
        print(f"K = {k}")
        print("-" * 70)

        print("\nCLUSTER SIZES")

        print(
            cluster_sizes[
                cluster_sizes["k"] == k
            ].to_string(index=False)
        )

        print("\nAREA DISTRIBUTION")

        print(
            area_distribution[
                area_distribution["k"] == k
            ].to_string(index=False)
        )

        print("\nCOVERAGE AND QUALITY")

        print(
            coverage_quality[
                coverage_quality["k"] == k
            ].to_string(index=False)
        )

        print("\nCLUSTER FEATURE MEANS")

        subset = profiles[
            profiles["k"] == k
        ]

        mean_table = subset.pivot(
            index="cluster",
            columns="feature",
            values="mean",
        )

        print(
            mean_table.round(3).to_string()
        )

    print("\n" + "=" * 70)
    print("CLUSTER ANALYSIS COMPLETED")
    print("=" * 70)

    print(
        "\nIMPORTANT: Cluster IDs are arbitrary labels, "
        "not infrastructure priority rankings."
    )

    print(
        "Geometry coverage measures grid-cell overlap "
        "with the pilot boundary, not OSM data completeness."
    )

    print(
        "Mapped facility and infrastructure counts do not "
        "establish service adequacy or infrastructure shortage."
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print("[INFO] Loading input datasets...")

    raw, metadata, assignments = load_inputs()

    print(
        f"[INFO] Raw feature rows: {len(raw)}"
    )

    print(
        f"[INFO] Assignment rows: {len(assignments)}"
    )

    print(
        f"[INFO] Available K values: "
        f"{sorted(assignments['k'].unique().tolist())}"
    )

    features = get_feature_columns(raw)

    print(
        f"[INFO] Identified {len(features)} features."
    )

    print("[INFO] Preparing merged dataset...")

    merged = prepare_dataset(
        raw,
        metadata,
        assignments,
    )

    print(
        f"[INFO] Prepared {len(merged)} grid cells."
    )

    print("[INFO] Calculating cluster feature profiles...")

    profiles = calculate_feature_profiles(
        merged,
        features,
    )

    print("[INFO] Calculating area distributions...")

    area_distribution = calculate_area_distribution(
        merged,
    )

    print("[INFO] Calculating coverage quality...")

    coverage_quality = calculate_coverage_quality(
        merged,
    )

    print("[INFO] Calculating cluster sizes...")

    cluster_sizes = calculate_cluster_sizes(
        merged,
    )

    print("[INFO] Calculating overall feature reference...")

    overall_reference = calculate_overall_feature_reference(
        merged,
        features,
    )

    print("[INFO] Saving analysis outputs...")

    save_outputs(
        profiles,
        area_distribution,
        coverage_quality,
        cluster_sizes,
        overall_reference,
    )

    print_summary(
        merged,
        profiles,
        area_distribution,
        coverage_quality,
        cluster_sizes,
        features,
    )


if __name__ == "__main__":
    main()
