
"""InfraVista P4: Explainable multi-sector infrastructure screening.

Converts P3 indicator records into sector-wise evidence summaries.
Does not infer infrastructure shortages or calculate arbitrary priority scores.
"""

from __future__ import annotations

import argparse
import json
import math
import sys

from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict:
    """Load JSON and ensure its root is an object."""
    try:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Could not load {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON object in {path}")

    return data


def normalize_flags(flags: Any) -> list[str]:
    """Normalize quality flags into a list of strings."""
    if flags is None:
        return []

    if isinstance(flags, str):
        return [item.strip() for item in flags.split(";") if item.strip()]

    if isinstance(flags, list):
        return [
            str(item).strip()
            for item in flags
            if item is not None and str(item).strip()
        ]

    return ["invalid_quality_flags_format"]


def is_valid_number(value: Any) -> bool:
    """Check for finite numeric values, excluding booleans."""
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def validate_rules(rules: dict) -> dict[str, dict]:
    """Validate sector configuration and return sector definitions."""
    sectors = rules.get("sectors")

    if not isinstance(sectors, dict) or not sectors:
        raise ValueError("Rules must contain a non-empty 'sectors' object.")

    all_indicators = []

    for sector_name, sector_config in sectors.items():
        if not isinstance(sector_config, dict):
            raise ValueError(f"Invalid configuration for sector: {sector_name}")

        indicators = sector_config.get("indicators")

        if not isinstance(indicators, list) or not indicators:
            raise ValueError(
                f"Sector '{sector_name}' must have a non-empty indicators list."
            )

        if not all(
            isinstance(item, str) and item.strip()
            for item in indicators
        ):
            raise ValueError(
                f"Sector '{sector_name}' contains an invalid indicator ID."
            )

        if len(indicators) != len(set(indicators)):
            raise ValueError(
                f"Duplicate indicator IDs inside sector '{sector_name}'."
            )

        all_indicators.extend(indicators)

    if len(all_indicators) != len(set(all_indicators)):
        raise ValueError(
            "An indicator is assigned to multiple sectors."
        )

    return sectors


def load_indicator_records(
    geojson_path: Path,
    expected_indicators: set[str],
) -> tuple[dict[str, dict[str, dict]], list[str]]:
    """Load and organize P3 records by study area and indicator."""
    geojson = load_json(geojson_path)

    if geojson.get("type") != "FeatureCollection":
        raise ValueError("Input GeoJSON must be a FeatureCollection.")

    features = geojson.get("features")

    if not isinstance(features, list):
        raise ValueError("GeoJSON 'features' must be a list.")

    records = defaultdict(dict)
    warnings = []

    for index, feature in enumerate(features):
        if not isinstance(feature, dict):
            raise ValueError(f"Feature at index {index} is not an object.")

        properties = feature.get("properties")

        if not isinstance(properties, dict):
            raise ValueError(
                f"Feature at index {index} has no properties object."
            )

        area_id = properties.get("area_id")
        indicator_id = properties.get("indicator_id")

        if not area_id or not indicator_id:
            raise ValueError(
                f"Feature at index {index} is missing area_id or indicator_id."
            )

        area_id = str(area_id)
        indicator_id = str(indicator_id)

        if indicator_id not in expected_indicators:
            warnings.append(
                f"Unknown indicator '{indicator_id}' found for area '{area_id}'."
            )
            continue

        if indicator_id in records[area_id]:
            raise ValueError(
                f"Duplicate record: area='{area_id}', indicator='{indicator_id}'."
            )

        value = properties.get("value")

        if value is not None and not is_valid_number(value):
            raise ValueError(
                f"Invalid numeric value for {area_id}/{indicator_id}: {value!r}"
            )

        coverage = properties.get("coverage_fraction")

        if coverage is not None:
            if not is_valid_number(coverage) or not 0 <= coverage <= 1:
                raise ValueError(
                    f"Invalid coverage_fraction for "
                    f"{area_id}/{indicator_id}: {coverage!r}"
                )

        records[area_id][indicator_id] = {
            "record_status": "null_value" if value is None else "available",
            "value": value,
            "units": properties.get("units"),
            "denominator": properties.get("denominator"),
            "coverage_fraction": coverage,
            "evidence_type": properties.get("evidence_type"),
            "quality_flags": normalize_flags(
                properties.get("quality_flags")
            ),
            "source_ids": properties.get("source_ids"),
            "acquired_at": properties.get("acquired_at"),
            "method_version": properties.get("method_version"),
            "run_id": properties.get("run_id"),
            "feature_id": properties.get("feature_id"),
        }

    return dict(records), warnings


def assess_indicator(
    indicator_id: str,
    record: dict | None,
    rules: dict,
) -> dict:
    """Classify one indicator without changing its value."""
    assessment_rules = rules["assessment"]

    if record is None:
        return {
            "indicator_id": indicator_id,
            "record_status": "missing_record",
            "assessment": assessment_rules["missing_record"],
            "value": None,
            "units": None,
            "coverage_fraction": None,
            "quality_flags": ["indicator_record_missing"],
        }

    result = {
        "indicator_id": indicator_id,
        **record,
    }

    if record["record_status"] == "null_value":
        result["assessment"] = assessment_rules["null_value"]
    else:
        result["assessment"] = assessment_rules["available_record"]

    return result


def assess_sector(
    sector_name: str,
    sector_config: dict,
    area_records: dict[str, dict],
    rules: dict,
) -> dict:
    """Build an evidence summary for one sector in one study area."""
    indicator_results = []

    review_flags = set(
        rules.get("quality_flags_requiring_review", [])
    )

    review_flags_found = set()

    # FIX: sector_config is a dictionary containing the indicator list.
    for indicator_id in sector_config["indicators"]:
        record = area_records.get(indicator_id)

        result = assess_indicator(indicator_id, record, rules)
        indicator_results.append(result)

        for flag in result.get("quality_flags", []):
            if flag in review_flags:
                review_flags_found.add(flag)

    available = sum(
        item["record_status"] == "available"
        for item in indicator_results
    )

    missing = sum(
        item["record_status"] == "missing_record"
        for item in indicator_results
    )

    null_values = sum(
        item["record_status"] == "null_value"
        for item in indicator_results
    )

    expected = len(indicator_results)
    assessment_rules = rules["assessment"]

    if available == 0 and missing == expected:
        evidence_status = assessment_rules["no_records"]
    elif available == 0 and null_values > 0:
        evidence_status = assessment_rules["null_value"]
    elif missing > 0 or null_values > 0:
        evidence_status = assessment_rules["missing_record"]
    else:
        evidence_status = assessment_rules["available_record"]

    return {
        "sector": sector_name,
        "description": sector_config.get("description"),
        "evidence_status": evidence_status,
        "quality_review_required": bool(review_flags_found),
        "quality_flags_requiring_review": sorted(review_flags_found),
        "summary": {
            "expected_indicator_count": expected,
            "available_indicator_count": available,
            "missing_record_count": missing,
            "null_value_count": null_values,
        },
        "indicators": indicator_results,
    }


def build_report(
    package_dir: Path,
    rules_path: Path,
) -> dict:
    """Build the complete multi-sector screening report."""
    manifest_path = package_dir / "manifest.json"
    geojson_path = package_dir / "indicators_window.geojson"

    if not manifest_path.is_file():
        raise ValueError(f"Manifest not found: {manifest_path}")

    if not geojson_path.is_file():
        raise ValueError(f"Window GeoJSON not found: {geojson_path}")

    manifest = load_json(manifest_path)
    rules = load_json(rules_path)

    sectors = validate_rules(rules)

    all_expected_indicators = {
        indicator
        for sector_config in sectors.values()
        for indicator in sector_config["indicators"]
    }

    records, warnings = load_indicator_records(
        geojson_path,
        all_expected_indicators,
    )

    study_areas = sorted(records.keys())

    if not study_areas:
        raise ValueError("No recognized indicator records were found.")

    area_results = []

    for area_id in study_areas:
        area_records = records[area_id]
        sector_results = []

        for sector_name, sector_config in sectors.items():
            sector_results.append(
                assess_sector(
                    sector_name,
                    sector_config,
                    area_records,
                    rules,
                )
            )

        available_total = sum(
            sector["summary"]["available_indicator_count"]
            for sector in sector_results
        )

        missing_total = sum(
            sector["summary"]["missing_record_count"]
            for sector in sector_results
        )

        null_total = sum(
            sector["summary"]["null_value_count"]
            for sector in sector_results
        )

        area_results.append({
            "area_id": area_id,
            "overall_evidence_status": (
                "evidence_available"
                if available_total > 0
                else "insufficient_evidence"
            ),
            "summary": {
                "sector_count": len(sector_results),
                "expected_indicator_count": len(all_expected_indicators),
                "available_indicator_count": available_total,
                "missing_record_count": missing_total,
                "null_value_count": null_total,
            },
            "sectors": sector_results,
        })

    return {
        "report_metadata": {
            "report_type": "multi_sector_infrastructure_screening",
            "screening_version": rules.get("screening_version"),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "method": rules.get("method"),
            "p3_run_id": manifest.get("run_id"),
            "p3_method_version": manifest.get("method_version"),
            "p3_validation_status": manifest.get("validation_status"),
            "p3_rights_status": manifest.get("rights_status"),
            "interpretation": (
                "Evidence screening only. Results do not establish "
                "infrastructure adequacy, shortage, or investment priority."
            ),
        },
        "principles": rules.get("principles", {}),
        "study_areas": area_results,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="InfraVista P4 multi-sector screening engine."
    )

    parser.add_argument(
        "--package-dir",
        required=True,
        help="Directory containing the P3 package.",
    )

    parser.add_argument(
        "--rules",
        default="config/screening_rules.json",
        help="Path to the screening rules JSON.",
    )

    parser.add_argument(
        "--output",
        default="reports/p4_screening/multi_sector_screening.json",
        help="Output report path.",
    )

    args = parser.parse_args()

    package_dir = Path(args.package_dir)
    rules_path = Path(args.rules)
    output_path = Path(args.output)

    try:
        report = build_report(package_dir, rules_path)

        output_path.parent.mkdir(parents=True, exist_ok=True)

        with output_path.open("w", encoding="utf-8") as file:
            json.dump(report, file, indent=2, ensure_ascii=False)

        print("InfraVista P4 screening: PASS")
        print(f"Study areas: {len(report['study_areas'])}")
        print(
            f"Sectors per area: "
            f"{len(report['study_areas'][0]['sectors'])}"
        )
        print(f"Output: {output_path.resolve()}")

        for area in report["study_areas"]:
            summary = area["summary"]

            print(f"\nArea: {area['area_id']}")
            print(
                f"Available: {summary['available_indicator_count']} | "
                f"Missing: {summary['missing_record_count']} | "
                f"Null: {summary['null_value_count']}"
            )

            for sector in area["sectors"]:
                sector_summary = sector["summary"]

                print(
                    f"  {sector['sector']}: "
                    f"{sector['evidence_status']} | "
                    f"{sector_summary['available_indicator_count']}/"
                    f"{sector_summary['expected_indicator_count']} available | "
                    f"quality review: "
                    f"{sector['quality_review_required']}"
                )

        if report["warnings"]:
            print("\nWarnings:")
            for warning in report["warnings"]:
                print(f"- {warning}")

        return 0

    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(f"Screening failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
