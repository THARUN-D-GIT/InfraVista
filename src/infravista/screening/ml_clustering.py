
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


BASE_DIR = Path("data/processed/p4_ml")
FEATURE_FILE = BASE_DIR / "feature_matrix_scaled.csv"

OUTPUT_DIR = Path("reports/p4_clustering")

K_VALUES = range(2, 7)
RANDOM_STATE = 42
N_INIT = 20
MAX_ITER = 300
TOLERANCE = 1e-5


def load_features():
    if not FEATURE_FILE.exists():
        raise FileNotFoundError(FEATURE_FILE)

    data = pd.read_csv(FEATURE_FILE)

    if not {"grid_id", "area_id"}.issubset(data.columns):
        raise ValueError("Missing grid_id or area_id.")

    if data["grid_id"].duplicated().any():
        raise ValueError("Duplicate grid IDs detected.")

    identifiers = data[["grid_id", "area_id"]].copy()
    X = data.drop(columns=["grid_id", "area_id"])

    if X.empty:
        raise ValueError("No feature columns found.")

    if not all(pd.api.types.is_numeric_dtype(X[c]) for c in X):
        raise ValueError("Non-numeric features detected.")

    X = X.to_numpy(dtype=float)

    if not np.isfinite(X).all():
        raise ValueError("NaN or infinite feature values detected.")

    return identifiers, X


def initialize_centroids(X, k, rng):
    """K-Means++ centroid initialization."""

    n_samples = len(X)
    centroids = [X[rng.integers(n_samples)]]

    for _ in range(1, k):
        distances = np.min(
            np.stack([
                np.sum((X - center) ** 2, axis=1)
                for center in centroids
            ]),
            axis=0,
        )

        total = distances.sum()

        if total == 0:
            remaining = [
                i for i in range(n_samples)
                if not any(
                    np.array_equal(X[i], center)
                    for center in centroids
                )
            ]

            if not remaining:
                raise ValueError("Unable to initialize distinct centroids.")

            next_index = rng.choice(remaining)
        else:
            probabilities = distances / total
            next_index = rng.choice(
                n_samples,
                p=probabilities,
            )

        centroids.append(X[next_index])

    return np.array(centroids, dtype=float)


def run_single_kmeans(X, k, seed):
    rng = np.random.default_rng(seed)
    centroids = initialize_centroids(X, k, rng)

    for iteration in range(MAX_ITER):
        distances = np.sum(
            (X[:, None, :] - centroids[None, :, :]) ** 2,
            axis=2,
        )

        labels = np.argmin(distances, axis=1)

        new_centroids = np.empty_like(centroids)

        for cluster in range(k):
            members = X[labels == cluster]

            if len(members) == 0:
                # Reassign an empty cluster to the point
                # currently farthest from its assigned centroid.
                nearest_distances = distances[
                    np.arange(len(X)), labels
                ]

                farthest_index = np.argmax(nearest_distances)
                new_centroids[cluster] = X[farthest_index]
            else:
                new_centroids[cluster] = members.mean(axis=0)

        shift = np.linalg.norm(new_centroids - centroids)
        centroids = new_centroids

        if shift < TOLERANCE:
            break

    final_distances = np.sum(
        (X[:, None, :] - centroids[None, :, :]) ** 2,
        axis=2,
    )

    labels = np.argmin(final_distances, axis=1)

    inertia = float(
        np.sum(
            (X - centroids[labels]) ** 2
        )
    )

    return labels, centroids, inertia, iteration + 1


def run_kmeans(X, k):
    best_result = None

    for restart in range(N_INIT):
        seed = RANDOM_STATE + restart

        result = run_single_kmeans(X, k, seed)

        labels, centroids, inertia, iterations = result

        if len(np.unique(labels)) != k:
            continue

        if best_result is None or inertia < best_result[2]:
            best_result = result

    if best_result is None:
        raise ValueError(f"Could not obtain {k} non-empty clusters.")

    return best_result


def pairwise_distances(X):
    squared = np.sum(X ** 2, axis=1)

    distances_squared = (
        squared[:, None]
        + squared[None, :]
        - 2 * X @ X.T
    )

    return np.sqrt(np.maximum(distances_squared, 0.0))


def silhouette_score_numpy(X, labels):
    distances = pairwise_distances(X)
    unique_labels = np.unique(labels)

    scores = []

    for i in range(len(X)):
        own_cluster = labels[i]

        own_indices = np.where(labels == own_cluster)[0]
        own_indices = own_indices[own_indices != i]

        if len(own_indices) == 0:
            scores.append(0.0)
            continue

        a = distances[i, own_indices].mean()

        other_means = []

        for cluster in unique_labels:
            if cluster == own_cluster:
                continue

            other_indices = np.where(labels == cluster)[0]
            other_means.append(
                distances[i, other_indices].mean()
            )

        b = min(other_means)

        denominator = max(a, b)

        scores.append(
            0.0 if denominator == 0
            else (b - a) / denominator
        )

    return float(np.mean(scores))


def davies_bouldin_score_numpy(X, labels, centroids):
    clusters = np.unique(labels)
    k = len(clusters)

    scatter = np.zeros(k)

    for cluster in clusters:
        members = X[labels == cluster]

        scatter[cluster] = np.linalg.norm(
            members - centroids[cluster],
            axis=1,
        ).mean()

    centroid_distances = pairwise_distances(centroids)

    ratios = np.zeros((k, k))

    for i in range(k):
        for j in range(k):
            if i == j:
                continue

            distance = centroid_distances[i, j]

            if distance == 0:
                ratios[i, j] = np.inf
            else:
                ratios[i, j] = (
                    scatter[i] + scatter[j]
                ) / distance

    return float(np.mean(np.max(ratios, axis=1)))


def calinski_harabasz_score_numpy(X, labels, centroids):
    n_samples = len(X)
    k = len(centroids)

    overall_mean = X.mean(axis=0)

    between_dispersion = 0.0
    within_dispersion = 0.0

    for cluster in range(k):
        members = X[labels == cluster]
        center = centroids[cluster]

        between_dispersion += (
            len(members)
            * np.sum((center - overall_mean) ** 2)
        )

        within_dispersion += np.sum(
            (members - center) ** 2
        )

    if within_dispersion == 0:
        return float("inf")

    return float(
        (between_dispersion / (k - 1))
        / (within_dispersion / (n_samples - k))
    )


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("===== INFRAVISTA NUMPY K-MEANS EXPERIMENT =====")

    identifiers, X = load_features()

    print(f"Grid cells: {len(X)}")
    print(f"Features: {X.shape[1]}")
    print(f"Candidate K values: {list(K_VALUES)}")
    print(f"Random initializations per K: {N_INIT}")

    results = []
    all_assignments = []

    for k in K_VALUES:
        print(f"\nEvaluating K={k}...")

        labels, centroids, inertia, iterations = run_kmeans(X, k)

        silhouette = silhouette_score_numpy(X, labels)

        davies_bouldin = davies_bouldin_score_numpy(
            X, labels, centroids
        )

        calinski_harabasz = calinski_harabasz_score_numpy(
            X, labels, centroids
        )

        results.append({
            "k": k,
            "inertia": inertia,
            "silhouette_score": silhouette,
            "davies_bouldin_score": davies_bouldin,
            "calinski_harabasz_score": calinski_harabasz,
            "cluster_count": len(np.unique(labels)),
            "iterations": iterations,
        })

        for index, label in enumerate(labels):
            all_assignments.append({
                "k": k,
                "grid_id": identifiers.iloc[index]["grid_id"],
                "area_id": identifiers.iloc[index]["area_id"],
                "cluster": int(label),
            })

    results_df = pd.DataFrame(results)
    assignments_df = pd.DataFrame(all_assignments)

    results_df.to_csv(
        OUTPUT_DIR / "kmeans_evaluation.csv",
        index=False,
    )

    assignments_df.to_csv(
        OUTPUT_DIR / "kmeans_cluster_assignments.csv",
        index=False,
    )

    print("\n===== CLUSTER EVALUATION RESULTS =====")

    with pd.option_context(
        "display.max_columns", None,
        "display.width", 200,
        "display.float_format", lambda x: f"{x:.4f}",
    ):
        print(results_df.to_string(index=False))

    print("\n===== CLUSTER DISTRIBUTION BY AREA =====")

    for k in K_VALUES:
        subset = assignments_df[assignments_df["k"] == k]

        distribution = pd.crosstab(
            subset["area_id"],
            subset["cluster"],
        )

        print(f"\nK={k}")
        print(distribution.to_string())

    print("\n===== OUTPUT FILES =====")
    print(OUTPUT_DIR / "kmeans_evaluation.csv")
    print(OUTPUT_DIR / "kmeans_cluster_assignments.csv")

    print("\nK-Means experiment completed.")
    print("No optimal K selected automatically.")
    print("Cluster IDs are arbitrary, not infrastructure rankings.")


if __name__ == "__main__":
    main()
