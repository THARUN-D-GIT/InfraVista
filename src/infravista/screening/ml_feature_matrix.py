
from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler


PACKAGE_DIR = Path(os.environ["TEMP"]) / "infravista_p4_audit"
INPUT_FILE = PACKAGE_DIR / "indicators_grid.geojson"

OUTPUT_DIR = Path("data/processed/p4_ml")

SELECTED_FEATURES = [
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

BOUNDED_FEATURES = {
    "water_area_share",
}


def load_data():
    with INPUT_FILE.open("r", encoding="utf-8") as file:
        geojson = json.load(file)

    rows = []

    for feature in geojson["features"]:
        p = feature["properties"]

        indicator = p["indicator_id"]
        feature_id = p["feature_id"]

        suffix = "_" + indicator

        if not feature_id.endswith(suffix):
            raise ValueError(f"Unexpected feature ID: {feature_id}")

        rows.append({
            "grid_id": feature_id[:-len(suffix)],
            "area_id": p["area_id"],
            "indicator_id": indicator,
            "value": p["value"],
            "coverage_fraction": p["coverage_fraction"],
            "quality_flags": p.get("quality_flags", ""),
        })

    return pd.DataFrame(rows)


def prepare_matrix(data):
    selected = data[
        data["indicator_id"].isin(SELECTED_FEATURES)
    ].copy()

    if selected.duplicated(
        ["grid_id", "indicator_id"]
    ).any():
        raise ValueError("Duplicate grid-indicator records found.")

    # Pivot indicator values into columns.
    raw = selected.pivot(
        index=["grid_id", "area_id"],
        columns="indicator_id",
        values="value",
    )

    raw = raw.reindex(columns=SELECTED_FEATURES)

    # Do not silently impute missing values.
    if raw.isna().any().any():
        missing = raw.columns[raw.isna().any()].tolist()
        raise ValueError(f"Missing selected indicators: {missing}")

    raw = raw.astype(float)

    if not np.isfinite(raw.to_numpy()).all():
        raise ValueError("Non-finite feature values detected.")

    if (raw < 0).any().any():
        raise ValueError("Negative values found in non-negative features.")

    # Apply log1p to counts and densities.
    transformed = raw.copy()

    for column in SELECTED_FEATURES:
        if column not in BOUNDED_FEATURES:
            transformed[column] = np.log1p(raw[column])

    # Standardize without using area_id as a model feature.
    scaler = StandardScaler()

    scaled_values = scaler.fit_transform(transformed)

    scaled = pd.DataFrame(
        scaled_values,
        index=transformed.index,
        columns=transformed.columns,
    )

    # Preserve grid-level coverage and quality metadata.
    metadata = (
        selected.groupby(["grid_id", "area_id"])
        .agg(
            minimum_indicator_coverage=("coverage_fraction", "min"),
            quality_flags=(
                "quality_flags",
                lambda values: ";".join(sorted({
                    flag.strip()
                    for value in values
                    if isinstance(value, str)
                    for flag in value.split(";")
                    if flag.strip()
                }))
            ),
        )
    )

    metadata["coverage_review"] = np.where(
        metadata["minimum_indicator_coverage"] < 0.50,
        "low_coverage_review",
        "coverage_at_least_0.50",
    )

    return raw, transformed, scaled, metadata


def main():
    if not INPUT_FILE.exists():
        raise FileNotFoundError(INPUT_FILE)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading P3 indicator dataset...")

    data = load_data()

    raw, transformed, scaled, metadata = prepare_matrix(data)

    # Save all three representations.
    raw.reset_index().to_csv(
        OUTPUT_DIR / "feature_matrix_raw.csv",
        index=False,
    )

    transformed.reset_index().to_csv(
        OUTPUT_DIR / "feature_matrix_log_transformed.csv",
        index=False,
    )

    scaled.reset_index().to_csv(
        OUTPUT_DIR / "feature_matrix_scaled.csv",
        index=False,
    )

    metadata.reset_index().to_csv(
        OUTPUT_DIR / "feature_matrix_metadata.csv",
        index=False,
    )

    summary = {
        "stage": "p4_ml_feature_preparation",
        "feature_count": len(SELECTED_FEATURES),
        "grid_cell_count": len(raw),
        "areas": sorted(raw.index.get_level_values("area_id").unique()),
        "selected_features": SELECTED_FEATURES,
        "bounded_features_not_log_transformed": sorted(
            BOUNDED_FEATURES
        ),
        "log_transform": "numpy.log1p",
        "scaling": "sklearn.StandardScaler",
        "missing_values_imputed": False,
        "area_id_used_as_model_feature": False,
        "coverage_threshold_for_review": 0.50,
    }

    with (OUTPUT_DIR / "feature_matrix_summary.json").open(
        "w", encoding="utf-8"
    ) as file:
        json.dump(summary, file, indent=4)

    print("\n===== FEATURE MATRIX PREPARATION: PASS =====")
    print(f"Grid cells: {len(raw)}")
    print(f"Features: {len(SELECTED_FEATURES)}")
    print(f"Areas: {summary['areas']}")

    print("\n===== OUTPUT FILES =====")

    for path in sorted(OUTPUT_DIR.iterdir()):
        print(path)

    print("\n===== SCALED MATRIX CHECK =====")
    print(f"Shape: {scaled.shape}")
    print(f"NaN values: {scaled.isna().sum().sum()}")
    print(f"Infinite values: {np.isinf(scaled.to_numpy()).sum()}")

    print("\nFeature matrix preparation completed.")


if __name__ == "__main__":
    main()
