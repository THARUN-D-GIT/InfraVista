
from __future__ import annotations

import argparse
from itertools import permutations
from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[3]

DEFAULT_FEATURES = (
    PROJECT_ROOT / "data/processed/p4_ml/feature_matrix_raw.csv"
)
DEFAULT_ASSIGNMENTS = (
    PROJECT_ROOT
    / "reports/p4_clustering/coverage_sensitivity/"
    / "coverage_sensitivity_assignments.csv"
)
DEFAULT_OUTPUT = (
    PROJECT_ROOT / "reports/p4_clustering/cluster_stability"
)

KEYS = ["grid_id", "area_id"]
THRESHOLDS = [0.0, 0.50, 0.75]
K_VALUES = [3, 4]


def load_inputs(
    features_path: Path,
    assignments_path: Path,
) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    """Load raw feature values and sensitivity assignments."""

    features = pd.read_csv(features_path)
    assignments = pd.read_csv(assignments_path)

    required_features = set(KEYS)
    required_assignments = {
        "grid_id",
        "area_id",
        "coverage_threshold",
        "minimum_indicator_coverage",
        "k",
        "cluster",
    }

    if not required_features.issubset(features.columns):
        raise ValueError("Raw feature matrix is missing grid_id or area_id.")

    if not required_assignments.issubset(assignments.columns):
        missing = required_assignments - set(assignments.columns)
        raise ValueError(f"Assignments missing columns: {sorted(missing)}")

    if features.duplicated(KEYS).any():
        raise ValueError("Duplicate grid_id/area_id in raw features.")

    if assignments.duplicated(
        ["coverage_threshold", "k", "grid_id", "area_id"]
    ).any():
        raise ValueError("Duplicate grid assignment for a threshold and K.")

    feature_columns = [
        col for col in features.columns if col not in KEYS
    ]

    if not feature_columns:
        raise ValueError("No raw feature columns found.")

    for col in feature_columns:
        features[col] = pd.to_numeric(features[col], errors="raise")

    if not np.isfinite(
        features[feature_columns].to_numpy(dtype=float)
    ).all():
        raise ValueError("Raw feature matrix contains non-finite values.")

    return features, assignments, feature_columns


def align_cluster_labels(
    baseline: pd.DataFrame,
    current: pd.DataFrame,
    k: int,
) -> dict[int, int]:
    """
    Map current cluster IDs to baseline IDs by maximizing
    matching grid-cell assignments.
    """

    comparison = baseline[KEYS + ["cluster"]].merge(
        current[KEYS + ["cluster"]],
        on=KEYS,
        how="inner",
        suffixes=("_baseline", "_current"),
        validate="one_to_one",
    )

    if comparison.empty:
        raise ValueError("No common grid cells for cluster alignment.")

    baseline_ids = sorted(
        comparison["cluster_baseline"].unique().astype(int)
    )
    current_ids = sorted(
        comparison["cluster_current"].unique().astype(int)
    )

    if len(baseline_ids) != k or len(current_ids) != k:
        raise ValueError(
            f"Expected {k} clusters for alignment; "
            f"found baseline={len(baseline_ids)}, current={len(current_ids)}."
        )

    best_mapping = None
    best_overlap = -1

    for candidate in permutations(baseline_ids):
        mapping = dict(zip(current_ids, candidate))

        mapped = comparison["cluster_current"].map(mapping)

        overlap = int(
            (mapped == comparison["cluster_baseline"]).sum()
        )

        if overlap > best_overlap:
            best_overlap = overlap
            best_mapping = mapping

    if best_mapping is None:
        raise RuntimeError("Unable to align cluster labels.")

    return best_mapping


def build_outputs(
    features: pd.DataFrame,
    assignments: pd.DataFrame,
    feature_columns: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:

    profile_rows = []
    area_rows = []
    size_rows = []

    for k in K_VALUES:
        baseline = assignments[
            (assignments["coverage_threshold"] == 0.0)
            & (assignments["k"] == k)
        ].copy()

        if len(baseline) != len(features):
            raise ValueError(
                f"Baseline K={k} has {len(baseline)} assignments, "
                f"but raw features contain {len(features)} cells."
            )

        for threshold in THRESHOLDS:

            current = assignments[
                (assignments["coverage_threshold"] == threshold)
                & (assignments["k"] == k)
            ].copy()

            if current.empty:
                raise ValueError(
                    f"No assignments for threshold={threshold}, K={k}."
                )

            if threshold == 0.0:
                mapping = {
                    int(cluster): int(cluster)
                    for cluster in sorted(current["cluster"].unique())
                }
            else:
                mapping = align_cluster_labels(
                    baseline,
                    current,
                    k,
                )

            current["matched_baseline_cluster"] = (
                current["cluster"].map(mapping)
            )

            if current["matched_baseline_cluster"].isna().any():
                raise ValueError("Some cluster IDs could not be aligned.")

            merged = current.merge(
                features,
                on=KEYS,
                how="left",
                validate="one_to_one",
            )

            if merged[feature_columns].isna().any().any():
                raise ValueError(
                    "Some assigned cells could not be matched to raw features."
                )

            # Cluster sizes
            sizes = (
                merged.groupby("matched_baseline_cluster")
                .size()
                .to_dict()
            )

            for cluster_id, group in merged.groupby(
                "matched_baseline_cluster"
            ):
                cluster_id = int(cluster_id)

                # Feature statistics
                for feature in feature_columns:
                    values = group[feature].astype(float)

                    profile_rows.append({
                        "coverage_threshold": threshold,
                        "k": k,
                        "matched_baseline_cluster": cluster_id,
                        "cell_count": len(group),
                        "feature": feature,
                        "mean": float(values.mean()),
                        "median": float(values.median()),
                        "std": float(values.std(ddof=0)),
                        "minimum": float(values.min()),
                        "maximum": float(values.max()),
                    })

                # Coverage statistics
                coverage = group[
                    "minimum_indicator_coverage"
                ].astype(float)

                size_rows.append({
                    "coverage_threshold": threshold,
                    "k": k,
                    "matched_baseline_cluster": cluster_id,
                    "cell_count": len(group),
                    "cell_percentage": (
                        len(group) / len(merged) * 100
                    ),
                    "mean_geometry_coverage": float(coverage.mean()),
                    "median_geometry_coverage": float(coverage.median()),
                    "minimum_geometry_coverage": float(coverage.min()),
                    "maximum_geometry_coverage": float(coverage.max()),
                    "cells_below_50_percent": int(
                        (coverage < 0.50).sum()
                    ),
                    "cells_below_75_percent": int(
                        (coverage < 0.75).sum()
                    ),
                })

            # Area-wise cluster distribution
            area_counts = (
                merged.groupby(
                    ["matched_baseline_cluster", "area_id"]
                )
                .size()
                .reset_index(name="cell_count")
            )

            for _, row in area_counts.iterrows():
                area_rows.append({
                    "coverage_threshold": threshold,
                    "k": k,
                    "matched_baseline_cluster": int(
                        row["matched_baseline_cluster"]
                    ),
                    "area_id": row["area_id"],
                    "cell_count": int(row["cell_count"]),
                })

            print(
                f"[INFO] K={k}, threshold={threshold:.2f}: "
                f"{len(merged)} cells, "
                f"cluster sizes={sizes}, "
                f"label mapping={mapping}"
            )

    return (
        pd.DataFrame(profile_rows),
        pd.DataFrame(area_rows),
        pd.DataFrame(size_rows),
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Compare infrastructure cluster profiles "
            "across coverage sensitivity thresholds."
        )
    )

    parser.add_argument(
        "--features",
        type=Path,
        default=DEFAULT_FEATURES,
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

    features, assignments, feature_columns = load_inputs(
        args.features,
        args.assignments,
    )

    args.output.mkdir(parents=True, exist_ok=True)

    profiles, area_distribution, cluster_sizes = build_outputs(
        features,
        assignments,
        feature_columns,
    )

    outputs = {
        "cluster_feature_profiles.csv": profiles,
        "cluster_area_distribution.csv": area_distribution,
        "cluster_coverage_quality.csv": cluster_sizes,
    }

    for filename, dataframe in outputs.items():
        path = args.output / filename
        dataframe.to_csv(path, index=False)
        print(f"[OUTPUT] {path}")

    print("\n[PASS] Cluster stability comparison completed.")
    print(f"[INFO] Raw feature count: {len(feature_columns)}")
    print(f"[INFO] Profile rows: {len(profiles)}")
    print(f"[INFO] Area distribution rows: {len(area_distribution)}")
    print(f"[INFO] Cluster summary rows: {len(cluster_sizes)}")


if __name__ == "__main__":
    main()
