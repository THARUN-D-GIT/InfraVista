
import json
import os
from pathlib import Path

import pandas as pd


def main():
    package_dir = Path(os.environ["TEMP"]) / "infravista_p4_audit"
    input_path = package_dir / "indicators_grid.geojson"

    with input_path.open("r", encoding="utf-8") as file:
        geojson = json.load(file)

    rows = []

    for feature in geojson["features"]:
        p = feature["properties"]

        indicator_id = p["indicator_id"]
        feature_id = p["feature_id"]

        grid_id = feature_id.removesuffix(
            "_" + indicator_id
        )

        rows.append({
            "grid_id": grid_id,
            "area_id": p["area_id"],
            "indicator_id": indicator_id,
            "coverage_fraction": p["coverage_fraction"],
        })

    df = pd.DataFrame(rows)

    coverage = (
        df.groupby(["grid_id", "area_id"])["coverage_fraction"]
        .min()
        .reset_index(name="minimum_indicator_coverage")
    )

    print("\n===== GRID COVERAGE DISTRIBUTION =====")
    print(
        coverage["minimum_indicator_coverage"]
        .describe()
        .to_string()
    )

    print("\n===== COVERAGE GROUPS =====")

    thresholds = [0.25, 0.50, 0.75, 0.90]

    for threshold in thresholds:
        count = (
            coverage["minimum_indicator_coverage"] < threshold
        ).sum()

        print(
            f"Below {threshold:.2f}: "
            f"{count} grid cells"
        )

    print("\n===== COVERAGE BY AREA =====")

    for area, group in coverage.groupby("area_id"):
        print(
            f"{area}: "
            f"{len(group)} cells, "
            f"minimum coverage = "
            f"{group['minimum_indicator_coverage'].min():.6f}, "
            f"median = "
            f"{group['minimum_indicator_coverage'].median():.4f}"
        )


if __name__ == "__main__":
    main()
