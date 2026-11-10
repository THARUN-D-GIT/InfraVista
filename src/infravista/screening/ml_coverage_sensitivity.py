
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


RANDOM_STATE = 42
N_INIT = 20
MAX_ITER = 300
TOLERANCE = 1e-5

THRESHOLDS = [0.0, 0.50, 0.75]
K_VALUES = [3, 4]

PROJECT_ROOT = Path(__file__).resolve().parents[3]

DEFAULT_FEATURES = (
    PROJECT_ROOT / "data/processed/p4_ml/feature_matrix_scaled.csv"
)
DEFAULT_METADATA = (
    PROJECT_ROOT / "data/processed/p4_ml/feature_matrix_metadata.csv"
)
DEFAULT_OUTPUT = PROJECT_ROOT / "reports/p4_clustering/coverage_sensitivity"


def calculate_distances(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Calculate Euclidean distances between two collections of rows."""
    return np.sqrt(
        np.maximum(
            np.sum(a * a, axis=1)[:, None]
            + np.sum(b * b, axis=1)[None, :]
            - 2 * np.dot(a, b.T),
            0.0,
        )
    )


def initialize_centroids(
    X: np.ndarray,
    k: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """K-Means++ centroid initialization."""
    n_samples = len(X)

    centroids = [X[rng.integers(n_samples)]]

    for _ in range(1, k):
        distances = calculate_distances(X, np.array(centroids))
        nearest_squared = np.min(distances ** 2, axis=1)

        total = nearest_squared.sum()

        if total <= 0:
            remaining = [
                i for i in range(n_samples)
                if not any(np.array_equal(X[i], c) for c in centroids)
            ]
            if not remaining:
                raise ValueError("Unable to initialize distinct centroids.")
            next_index = rng.choice(remaining)
        else:
            probabilities = nearest_squared / total
            next_index = rng.choice(n_samples, p=probabilities)

        centroids.append(X[next_index])

    return np.array(centroids, dtype=float)


def run_kmeans(
    X: np.ndarray,
    k: int,
    seed: int,
) -> tuple[np.ndarray, np.ndarray, float, int]:
    """Run one K-Means++ fit."""
    rng = np.random.default_rng(seed)
    centroids = initialize_centroids(X, k, rng)

    for iteration in range(1, MAX_ITER + 1):
        distances = calculate_distances(X, centroids)
        labels = np.argmin(distances, axis=1)

        new_centroids = centroids.copy()

        for cluster_id in range(k):
            members = X[labels == cluster_id]

            if len(members) == 0:
                nearest_distance = np.min(distances, axis=1)
                replacement_index = int(np.argmax(nearest_distance))
                new_centroids[cluster_id] = X[replacement_index]
            else:
                new_centroids[cluster_id] = members.mean(axis=0)

        movement = np.linalg.norm(new_centroids - centroids)
        centroids = new_centroids

        if movement <= TOLERANCE:
            break

    distances = calculate_distances(X, centroids)
    labels = np.argmin(distances, axis=1)

    inertia = float(
        np.sum((X - centroids[labels]) ** 2)
    )

    return labels, centroids, inertia, iteration


def fit_best_kmeans(
    X: np.ndarray,
    k: int,
    random_state: int = RANDOM_STATE,
) -> tuple[np.ndarray, np.ndarray, float, int]:
    """Select the best result across multiple initializations."""
    if len(X) <= k:
        raise ValueError(f"Need more than {k} samples; received {len(X)}.")

    best_result = None

    for init_number in range(N_INIT):
        seed = random_state + init_number

        result = run_kmeans(X, k, seed)
        labels, centroids, inertia, iterations = result

        if len(np.unique(labels)) != k:
            continue

        if best_result is None or inertia < best_result[2]:
            best_result = result

    if best_result is None:
        raise ValueError(f"K={k} did not produce {k} non-empty clusters.")

    return best_result


def silhouette_score(X: np.ndarray, labels: np.ndarray) -> float:
    """Calculate the mean silhouette coefficient."""
    distances = calculate_distances(X, X)
    unique_clusters = np.unique(labels)

    if len(unique_clusters) < 2 or len(unique_clusters) >= len(X):
        return float("nan")

    scores = []

    for i in range(len(X)):
        own_cluster = labels[i]
        own_indices = np.where(labels == own_cluster)[0]
        own_indices = own_indices[own_indices != i]

        if len(own_indices) == 0:
            scores.append(0.0)
            continue

        a = float(distances[i, own_indices].mean())

        other_means = []
        for cluster_id in unique_clusters:
            if cluster_id == own_cluster:
                continue

            other_indices = np.where(labels == cluster_id)[0]
            other_means.append(float(distances[i, other_indices].mean()))

        b = min(other_means)
        denominator = max(a, b)

        scores.append(
            0.0 if denominator == 0 else (b - a) / denominator
        )

    return float(np.mean(scores))


def davies_bouldin_score(
    X: np.ndarray,
    labels: np.ndarray,
    centroids: np.ndarray,
) -> float:
    """Calculate the Davies-Bouldin index."""
    k = len(centroids)
    scatter = np.zeros(k)

    for cluster_id in range(k):
        members = X[labels == cluster_id]

        if len(members) == 0:
            return float("nan")

        scatter[cluster_id] = np.mean(
            np.linalg.norm(members - centroids[cluster_id], axis=1)
        )

    centroid_distances = calculate_distances(centroids, centroids)
    ratios = np.zeros((k, k))

    for i in range(k):
        for j in range(k):
            if i == j:
                continue

            distance = centroid_distances[i, j]

            if distance == 0:
                ratios[i, j] = float("inf")
            else:
                ratios[i, j] = (
                    scatter[i] + scatter[j]
                ) / distance

    return float(np.mean(np.max(ratios, axis=1)))


def calinski_harabasz_score(
    X: np.ndarray,
    labels: np.ndarray,
    centroids: np.ndarray,
) -> float:
    """Calculate the Calinski-Harabasz index."""
    n_samples = len(X)
    k = len(centroids)

    if k < 2 or n_samples <= k:
        return float("nan")

    overall_mean = X.mean(axis=0)
    between = 0.0
    within = 0.0

    for cluster_id in range(k):
        members = X[labels == cluster_id]
        if len(members) == 0:
            return float("nan")

        between += len(members) * np.sum(
            (centroids[cluster_id] - overall_mean) ** 2
        )
        within += np.sum(
            (members - centroids[cluster_id]) ** 2
        )

    if within == 0:
        return float("nan")

    return float(
        (between / (k - 1))
        / (within / (n_samples - k))
    )


def adjusted_rand_index(
    labels_a: np.ndarray,
    labels_b: np.ndarray,
) -> float:
    """Calculate ARI without scikit-learn."""
    if len(labels_a) != len(labels_b):
        raise ValueError("ARI inputs must have equal lengths.")

    contingency = pd.crosstab(labels_a, labels_b).to_numpy()
    n = int(contingency.sum())

    if n < 2:
        return float("nan")

    def choose_two(values: np.ndarray) -> float:
        return float(np.sum(values * (values - 1) / 2))

    sum_cells = choose_two(contingency)
    sum_rows = choose_two(contingency.sum(axis=1))
    sum_cols = choose_two(contingency.sum(axis=0))
    total_pairs = n * (n - 1) / 2

    expected = (sum_rows * sum_cols) / total_pairs
    maximum = 0.5 * (sum_rows + sum_cols)

    denominator = maximum - expected

    if denominator == 0:
        return 1.0

    return float((sum_cells - expected) / denominator)


def load_data(
    features_path: Path,
    metadata_path: Path,
) -> tuple[pd.DataFrame, list[str]]:
    """Load and validate the scaled feature matrix and coverage metadata."""
    features = pd.read_csv(features_path)
    metadata = pd.read_csv(metadata_path)

    required_keys = {"grid_id", "area_id"}

    if not required_keys.issubset(features.columns):
        raise ValueError(
            "Feature matrix must contain grid_id and area_id."
        )

    if not required_keys.issubset(metadata.columns):
        raise ValueError(
            "Metadata must contain grid_id and area_id."
        )

    coverage_column = "minimum_indicator_coverage"

    if coverage_column not in metadata.columns:
        raise ValueError(
            f"Metadata is missing required column: {coverage_column}"
        )

    if features.duplicated(["grid_id", "area_id"]).any():
        raise ValueError("Duplicate grid_id/area_id in feature matrix.")

    if metadata.duplicated(["grid_id", "area_id"]).any():
        raise ValueError("Duplicate grid_id/area_id in metadata.")

    feature_columns = [
        column for column in features.columns
        if column not in {"grid_id", "area_id"}
    ]

    if not feature_columns:
        raise ValueError("No numeric feature columns found.")

    for column in feature_columns:
        features[column] = pd.to_numeric(
            features[column], errors="raise"
        )

    metadata[coverage_column] = pd.to_numeric(
        metadata[coverage_column], errors="raise"
    )

    merged = features.merge(
        metadata[
            ["grid_id", "area_id", coverage_column]
        ],
        on=["grid_id", "area_id"],
        how="inner",
        validate="one_to_one",
    )

    if len(merged) != len(features):
        raise ValueError(
            "Some feature rows could not be matched to metadata."
        )

    X = merged[feature_columns].to_numpy(dtype=float)

    if not np.isfinite(X).all():
        raise ValueError("Feature matrix contains NaN or infinite values.")

    coverage = merged[coverage_column].to_numpy(dtype=float)

    if not np.isfinite(coverage).all():
        raise ValueError("Coverage contains NaN or infinite values.")

    if np.any((coverage < 0) | (coverage > 1)):
        raise ValueError("Coverage values must be between 0 and 1.")

    return merged, feature_columns


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run coverage sensitivity analysis for K-Means."
    )

    parser.add_argument(
        "--features",
        type=Path,
        default=DEFAULT_FEATURES,
    )
    parser.add_argument(
        "--metadata",
        type=Path,
        default=DEFAULT_METADATA,
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
    )

    args = parser.parse_args()

    data, feature_columns = load_data(
        args.features,
        args.metadata,
    )

    args.output.mkdir(parents=True, exist_ok=True)

    metric_rows = []
    assignment_rows = []
    baseline_labels = {}

    print(f"[INFO] Total matched grid cells: {len(data)}")
    print(f"[INFO] Features: {len(feature_columns)}")
    print(f"[INFO] Thresholds: {THRESHOLDS}")
    print(f"[INFO] K values: {K_VALUES}")

    for threshold in THRESHOLDS:
        subset = data[
            data["minimum_indicator_coverage"] >= threshold
        ].copy().reset_index(drop=True)

        X = subset[feature_columns].to_numpy(dtype=float)

        print(
            f"\n[INFO] Coverage >= {threshold:.2f}: "
            f"{len(subset)} retained cells"
        )

        if len(subset) == 0:
            raise ValueError(
                f"No grid cells retained at threshold {threshold}."
            )

        for k in K_VALUES:
            labels, centroids, inertia, iterations = fit_best_kmeans(
                X,
                k,
                random_state=RANDOM_STATE,
            )

            actual_clusters = len(np.unique(labels))

            silhouette = silhouette_score(X, labels)
            db_index = davies_bouldin_score(
                X, labels, centroids
            )
            ch_index = calinski_harabasz_score(
                X, labels, centroids
            )

            cluster_sizes = pd.Series(labels).value_counts().sort_index()

            metric_rows.append({
                "coverage_threshold": threshold,
                "retained_cells": len(subset),
                "k": k,
                "inertia": inertia,
                "silhouette_score": silhouette,
                "davies_bouldin_score": db_index,
                "calinski_harabasz_score": ch_index,
                "actual_cluster_count": actual_clusters,
                "smallest_cluster_size": int(cluster_sizes.min()),
                "largest_cluster_size": int(cluster_sizes.max()),
                "iterations": iterations,
            })

            assignment = subset[
                ["grid_id", "area_id", "minimum_indicator_coverage"]
            ].copy()

            assignment["coverage_threshold"] = threshold
            assignment["k"] = k
            assignment["cluster"] = labels

            assignment_rows.append(assignment)

            if threshold == 0.0:
                baseline_labels[k] = pd.Series(
                    labels,
                    index=subset["grid_id"].astype(str),
                )
                ari = 1.0
            else:
                baseline = baseline_labels[k]

                current = pd.Series(
                    labels,
                    index=subset["grid_id"].astype(str),
                )

                common_ids = baseline.index.intersection(current.index)

                ari = adjusted_rand_index(
                    baseline.loc[common_ids].to_numpy(),
                    current.loc[common_ids].to_numpy(),
                )

            metric_rows[-1]["ari_vs_baseline"] = ari

            print(
                f"  K={k}: silhouette={silhouette:.4f}, "
                f"DB={db_index:.4f}, CH={ch_index:.4f}, "
                f"ARI={ari:.4f}"
            )

    metrics_df = pd.DataFrame(metric_rows)
    assignments_df = pd.concat(
        assignment_rows,
        ignore_index=True,
    )

    metrics_path = args.output / "coverage_sensitivity_metrics.csv"
    assignments_path = args.output / "coverage_sensitivity_assignments.csv"

    metrics_df.to_csv(metrics_path, index=False)
    assignments_df.to_csv(assignments_path, index=False)

    print("\n[PASS] Coverage sensitivity analysis completed.")
    print(f"[OUTPUT] {metrics_path}")
    print(f"[OUTPUT] {assignments_path}")

    print("\n[SUMMARY]")
    print(
        metrics_df[
            [
                "coverage_threshold",
                "retained_cells",
                "k",
                "silhouette_score",
                "davies_bouldin_score",
                "calinski_harabasz_score",
                "ari_vs_baseline",
            ]
        ].to_string(index=False)
    )


if __name__ == "__main__":
    main()
