
from __future__ import annotations

import json
import math
import tempfile
from pathlib import Path

import pandas as pd


PACKAGE_DIR = Path(tempfile.gettempdir()) / "infravista_p4_audit"
INPUT_FILE = PACKAGE_DIR / "indicators_grid.geojson"


def load_indicator_data() -> pd.DataFrame:
    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"Input file not found: {INPUT_FILE}")

    with INPUT_FILE.open("r", encoding="utf-8") as file:
        geojson = json.load(file)

    rows = []

    for feature in geojson.get("features", []):
        properties = feature.get("properties", {})

        indicator_id = properties.get("indicator_id")
        feature_id = properties.get("feature_id")
        area_id = properties.get("area_id")
        value = properties.get("value")

        if not indicator_id or not feature_id or not area_id:
            raise ValueError("A feature is missing required identifiers.")

        suffix = "_" + indicator_id

        if not feature_id.endswith(suffix):
            raise ValueError(
                f"Unexpected feature_id format: {feature_id}"
            )

        grid_id = feature_id[:-len(suffix)]

        if value is not None:
            value = float(value)
            if not math.isfinite(value):
                raise ValueError(
                    f"Non-finite value in {feature_id}: {value}"
                )

        rows.append({
            "grid_id": grid_id,
            "area_id": area_id,
            "indicator_id": indicator_id,
            "value": value,
        })

    data = pd.DataFrame(rows)

    if data.empty:
        raise ValueError("No indicator records found.")

    if data.duplicated(["grid_id", "indicator_id"]).any():
        raise ValueError("Duplicate grid-indicator records detected.")

    return data


def analyze_distribution(data: pd.DataFrame) -> pd.DataFrame:
    results = []

    for indicator, group in data.groupby("indicator_id"):
        values = group["value"].dropna()

        if values.empty:
            continue

        q1 = values.quantile(0.25)
        median = values.quantile(0.50)
        q3 = values.quantile(0.75)
        iqr = q3 - q1

        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr

        outliers = (
            (values < lower_bound) |
            (values > upper_bound)
        ).sum()

        results.append({
            "indicator_id": indicator,
            "records": len(group),
            "available_values": len(values),
            "missing_values": group["value"].isna().sum(),
            "unique_values": values.nunique(),
            "zero_count": int((values == 0).sum()),
            "zero_percent": round((values == 0).mean() * 100, 2),
            "minimum": values.min(),
            "q1": q1,
            "median": median,
            "mean": values.mean(),
            "q3": q3,
            "maximum": values.max(),
            "std_dev": values.std(),
            "skewness": values.skew(),
            "iqr_outlier_count": int(outliers),
        })

    return pd.DataFrame(results).sort_values(
        "indicator_id"
    ).reset_index(drop=True)


def main() -> None:
    print("Loading P3 grid indicators...")
    data = load_indicator_data()

    print(f"Input file: {INPUT_FILE}")
    print(f"Total indicator records: {len(data)}")
    print(f"Unique grid cells: {data['grid_id'].nunique()}")
    print(f"Unique indicators: {data['indicator_id'].nunique()}")

    print("\n===== FEATURE DISTRIBUTION ANALYSIS =====")

    report = analyze_distribution(data)

    with pd.option_context(
        "display.max_rows", None,
        "display.max_columns", None,
        "display.width", 240,
        "display.max_colwidth", 55,
        "display.float_format", lambda x: f"{x:.4f}",
    ):
        print(report.to_string(index=False))

    print("\n===== AREA-WISE ZERO VALUE ANALYSIS =====")

    area_zeros = (
        data.assign(is_zero=data["value"].eq(0))
        .groupby(["area_id", "indicator_id"])
        .agg(
            available_values=("value", "count"),
            zero_count=("is_zero", "sum"),
        )
        .reset_index()
    )

    area_zeros["zero_percent"] = (
        area_zeros["zero_count"] /
        area_zeros["available_values"] * 100
    ).round(2)

    with pd.option_context(
        "display.max_rows", None,
        "display.max_columns", None,
        "display.width", 180,
    ):
        print(area_zeros.to_string(index=False))

    print("\n===== ANALYSIS COMPLETE =====")
    print("No values were imputed or modified.")
    print("No cells were removed.")
    print("This stage is descriptive analysis only.")


if __name__ == "__main__":
    main()
