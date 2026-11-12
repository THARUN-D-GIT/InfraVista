
import json
import os
from pathlib import Path

import pandas as pd


def main():
    package_dir = (
        Path(os.environ["TEMP"]) / "infravista_p4_audit"
    )

    input_path = package_dir / "indicators_grid.geojson"

    with input_path.open("r", encoding="utf-8") as file:
        geojson = json.load(file)

    rows = []

    for feature in geojson["features"]:
        properties = feature["properties"]

        feature_id = properties["feature_id"]
        indicator_id = properties["indicator_id"]

        grid_id = feature_id.removesuffix(
            "_" + indicator_id
        )

        rows.append({
            "grid_id": grid_id,
            "area_id": properties["area_id"],
            "indicator_id": indicator_id,
            "value": properties["value"],
            "coverage_fraction": properties["coverage_fraction"],
            "quality_flags": properties.get("quality_flags", "")
        })

    long_df = pd.DataFrame(rows)

    print("\n===== LONG FORMAT =====")
    print("Rows:", len(long_df))
    print("Unique grid cells:", long_df["grid_id"].nunique())
    print("Unique indicators:", long_df["indicator_id"].nunique())

    print("\n===== DUPLICATE CHECK =====")
    duplicates = long_df.duplicated(
        subset=["grid_id", "indicator_id"]
    ).sum()

    print("Duplicate grid-indicator pairs:", duplicates)

    print("\n===== WIDE FORMAT =====")

    wide_df = long_df.pivot(
        index=["grid_id", "area_id"],
        columns="indicator_id",
        values="value"
    ).reset_index()

    print("Grid-cell rows:", len(wide_df))
    print("Indicator columns:", len(wide_df.columns) - 2)

    print("\n===== MISSING VALUE CHECK =====")
    print(wide_df.isna().sum().to_string())

    print("\n===== AREA DISTRIBUTION =====")
    print(wide_df["area_id"].value_counts().to_string())

    print("\n===== COVERAGE SUMMARY =====")
    print(long_df["coverage_fraction"].describe().to_string())

    print("\n===== RESULT =====")
    if duplicates == 0:
        print("PASS: No duplicate grid-indicator pairs.")
    else:
        print("REVIEW: Duplicate grid-indicator pairs detected.")

    if wide_df["grid_id"].nunique() == len(wide_df):
        print("PASS: Unique grid-cell identifiers.")
    else:
        print("FAIL: Grid-cell identifiers are not unique.")


if __name__ == "__main__":
    main()
