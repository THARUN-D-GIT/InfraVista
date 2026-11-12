
"""
InfraVista P4 - P3 Indicator Loader

Loads the P3 study-window indicators and organizes them
by study area while preserving missing-data information.

Python standard library only.
"""

import argparse
import json
from pathlib import Path


def load_json(path):
    """Load a JSON file."""
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def parse_quality_flags(flags):
    """Normalize quality flags without discarding information."""
    if flags is None:
        return []

    if isinstance(flags, list):
        return [str(flag).strip() for flag in flags if str(flag).strip()]

    if isinstance(flags, str):
        return [flag.strip() for flag in flags.split(";") if flag.strip()]

    return [str(flags)]


def load_p3_window(package_dir):
    """Load and organize P3 window indicators by study area."""

    package_dir = Path(package_dir)

    manifest_path = package_dir / "manifest.json"
    window_path = package_dir / "indicators_window.geojson"

    if not manifest_path.is_file():
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")

    if not window_path.is_file():
        raise FileNotFoundError(f"Window GeoJSON not found: {window_path}")

    manifest = load_json(manifest_path)
    geojson = load_json(window_path)

    if geojson.get("type") != "FeatureCollection":
        raise ValueError("Window data is not a GeoJSON FeatureCollection.")

    features = geojson.get("features")

    if not isinstance(features, list):
        raise ValueError("GeoJSON features must be a list.")

    expected_indicators = manifest.get("indicator_ids", [])

    if not isinstance(expected_indicators, list):
        raise ValueError("Manifest indicator_ids must be a list.")

    areas = {}
    errors = []

    for index, feature in enumerate(features):
        if not isinstance(feature, dict):
            errors.append(f"Feature {index}: invalid feature object")
            continue

        properties = feature.get("properties")

        if not isinstance(properties, dict):
            errors.append(f"Feature {index}: properties missing")
            continue

        area_id = properties.get("area_id")
        indicator_id = properties.get("indicator_id")

        if not area_id or not indicator_id:
            errors.append(
                f"Feature {index}: area_id or indicator_id missing"
            )
            continue

        if area_id not in areas:
            areas[area_id] = {}

        if indicator_id in areas[area_id]:
            errors.append(
                f"Duplicate indicator '{indicator_id}' in area '{area_id}'"
            )
            continue

        value = properties.get("value")

        if value is not None and (
            isinstance(value, bool) or not isinstance(value, (int, float))
        ):
            errors.append(
                f"Invalid value for '{indicator_id}' in '{area_id}'"
            )
            continue

        areas[area_id][indicator_id] = {
            "record_status": (
                "null_value" if value is None else "available"
            ),
            "value": value,
            "units": properties.get("units"),
            "denominator": properties.get("denominator"),
            "coverage_fraction": properties.get("coverage_fraction"),
            "evidence_type": properties.get("evidence_type"),
            "quality_flags": parse_quality_flags(
                properties.get("quality_flags")
            ),
            "source_ids": properties.get("source_ids"),
            "acquired_at": properties.get("acquired_at"),
            "method_version": properties.get("method_version"),
            "run_id": properties.get("run_id"),
        }

    if errors:
        raise ValueError(
            "P3 window loading failed:\n- " + "\n- ".join(errors)
        )

    # Explicitly represent absent records.
    # An absent record is NOT a measured zero.
    for area_id, indicators in areas.items():
        for indicator_id in expected_indicators:
            if indicator_id not in indicators:
                indicators[indicator_id] = {
                    "record_status": "missing_record",
                    "value": None,
                    "units": None,
                    "denominator": None,
                    "coverage_fraction": None,
                    "evidence_type": None,
                    "quality_flags": ["indicator_record_missing"],
                    "source_ids": None,
                    "acquired_at": None,
                    "method_version": None,
                    "run_id": None,
                }

    return {
        "metadata": {
            "run_id": manifest.get("run_id"),
            "method_version": manifest.get("method_version"),
            "validation_status": manifest.get("validation_status"),
            "rights_status": manifest.get("rights_status"),
            "expected_indicator_count": len(expected_indicators),
            "study_area_count": len(areas),
        },
        "areas": areas,
    }


def build_summary(dataset):
    """Create a compact availability summary."""

    summary = {}

    for area_id, indicators in dataset["areas"].items():
        counts = {
            "available": 0,
            "null_value": 0,
            "missing_record": 0,
        }

        for record in indicators.values():
            status = record["record_status"]
            counts[status] = counts.get(status, 0) + 1

        summary[area_id] = {
            "indicator_count": len(indicators),
            "available_count": counts["available"],
            "null_value_count": counts["null_value"],
            "missing_record_count": counts["missing_record"],
        }

    return summary


def main():
    parser = argparse.ArgumentParser(
        description="Load and inspect InfraVista P3 window indicators."
    )

    parser.add_argument(
        "--package-dir",
        required=True,
        help="Directory containing manifest.json and indicators_window.geojson",
    )

    args = parser.parse_args()

    try:
        dataset = load_p3_window(args.package_dir)

        report = {
            "status": "PASS",
            "metadata": dataset["metadata"],
            "summary": build_summary(dataset),
            "areas": dataset["areas"],
        }

        print(json.dumps(report, indent=2))

    except (OSError, json.JSONDecodeError, ValueError) as error:
        report = {
            "status": "FAIL",
            "error": str(error),
        }

        print(json.dumps(report, indent=2))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
