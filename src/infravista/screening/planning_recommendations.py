
"""Evidence-based infrastructure planning recommendations for InfraVista P4.

Generates data collection, quality validation and planning-readiness actions.
Does not calculate shortage scores or rank investment priorities.
"""

import argparse
import json
import sys

from datetime import datetime, timezone
from pathlib import Path


QUALITY_ACTIONS = {
    "osm_completeness_unverified": (
        "Cross-check mapped infrastructure against authoritative "
        "government or local-body datasets and conduct field verification."
    ),
    "count_not_complete_inventory": (
        "Verify facility inventories using official department records "
        "before interpreting facility counts."
    ),
    "storm_drains_often_unmapped": (
        "Obtain municipal storm-water drain records and validate "
        "drainage coverage through field or geospatial checks."
    ),
    "centreline_length_not_lane_km": (
        "Validate road measurements against road-width and lane-level "
        "datasets before using them for transport capacity analysis."
    ),
    "point_polygon_dedupe_assumption": (
        "Review facility deduplication assumptions and compare mapped "
        "facilities against verified inventories."
    ),
    "indicator_record_missing": (
        "Investigate the missing indicator record and verify source "
        "coverage, extraction and preprocessing."
    ),
}


PLANNING_ACTIONS = {
    "healthcare": [
        "Map healthcare facility service areas.",
        "Estimate population access using validated travel-time networks.",
        "Compare facility capacity with population and healthcare demand.",
    ],
    "education": [
        "Map school and college accessibility.",
        "Compare enrolment and student population with verified capacity.",
        "Assess travel-time access to educational facilities.",
    ],
    "transport": [
        "Validate road connectivity and network completeness.",
        "Assess road condition and public transport accessibility.",
        "Compare travel times and traffic demand across the study area.",
    ],
    "water_infrastructure": [
        "Map drainage and waterway network completeness.",
        "Combine rainfall, elevation and historical flood observations.",
        "Assess water supply and sanitation coverage using verified records.",
    ],
}


def load_json(path: Path) -> dict:
    """Load a JSON object from disk."""

    if not path.is_file():
        raise ValueError(f"File not found: {path}")

    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON object: {path}")

    return data


def validate_gap_report(report: dict) -> None:
    """Validate the required gap-analysis report structure."""

    metadata = report.get("report_metadata")
    areas = report.get("study_areas")

    if not isinstance(metadata, dict):
        raise ValueError("Missing or invalid report_metadata.")

    if not isinstance(areas, list) or not areas:
        raise ValueError("Missing or empty study_areas.")

    for area in areas:
        if not isinstance(area, dict) or not area.get("area_id"):
            raise ValueError("Invalid study-area entry.")

        sectors = area.get("sectors")

        if not isinstance(sectors, list):
            raise ValueError(
                f"Invalid sectors list for {area['area_id']}."
            )


def build_sector_recommendations(
    sector: dict,
    future_requirements: list,
) -> dict:
    """Create recommendations for an individual sector."""

    sector_name = sector.get("sector")

    if sector_name not in PLANNING_ACTIONS:
        raise ValueError(f"Unsupported sector: {sector_name}")

    evidence = sector.get("indicator_evidence", {})
    quality = sector.get("data_quality", {})

    if not isinstance(evidence, dict) or not isinstance(quality, dict):
        raise ValueError(
            f"Invalid evidence or quality information: {sector_name}"
        )

    missing = evidence.get("missing_indicator_ids", [])
    null_values = evidence.get("null_value_indicator_ids", [])
    quality_flags = quality.get("quality_flags", [])

    if not isinstance(missing, list) or not isinstance(null_values, list):
        raise ValueError(f"Invalid indicator gaps: {sector_name}")

    if not isinstance(quality_flags, list):
        raise ValueError(f"Invalid quality flags: {sector_name}")

    quality_actions = []

    for flag in sorted(set(quality_flags)):
        action = QUALITY_ACTIONS.get(flag)

        if action:
            quality_actions.append({
                "quality_flag": flag,
                "recommended_action": action,
            })
        else:
            quality_actions.append({
                "quality_flag": flag,
                "recommended_action": (
                    "Review this quality flag and document its impact "
                    "before using the affected indicator."
                ),
            })

    data_collection_actions = []

    for dataset in future_requirements:
        data_collection_actions.append({
            "dataset": dataset,
            "purpose": (
                f"Required to support evidence-based {sector_name} "
                "infrastructure assessment."
            ),
            "status": "additional_data_required",
        })

    return {
        "sector": sector_name,
        "evidence_gap_status": sector.get("evidence_gap_status"),
        "missing_indicator_ids": missing,
        "null_value_indicator_ids": null_values,
        "data_collection_actions": data_collection_actions,
        "data_quality_actions": quality_actions,
        "planning_actions": PLANNING_ACTIONS[sector_name],
        "planning_readiness": (
            "additional_evidence_and_validation_required"
        ),
        "investment_priority_assessment": (
            "not_assessed_insufficient_evidence"
        ),
    }


def build_recommendations(
    gap_report: dict,
    rules: dict,
) -> dict:
    """Build recommendations for every study area and sector."""

    validate_gap_report(gap_report)

    requirements = rules.get("future_data_requirements")

    if not isinstance(requirements, dict):
        raise ValueError("Rules missing future_data_requirements.")

    expected_sectors = set(requirements)
    area_results = []

    for area in gap_report["study_areas"]:
        area_id = area["area_id"]
        sector_results = area["sectors"]

        actual_sectors = [
            sector.get("sector") for sector in sector_results
        ]

        if len(actual_sectors) != len(set(actual_sectors)):
            raise ValueError(f"Duplicate sector found in {area_id}.")

        if set(actual_sectors) != expected_sectors:
            raise ValueError(
                f"Sector mismatch for {area_id}. "
                f"Expected: {sorted(expected_sectors)}; "
                f"Found: {sorted(actual_sectors)}"
            )

        recommendations = []

        for sector in sector_results:
            sector_name = sector["sector"]

            recommendations.append(
                build_sector_recommendations(
                    sector,
                    requirements[sector_name],
                )
            )

        area_results.append({
            "area_id": area_id,
            "source_evidence_gap_summary": (
                area.get("evidence_gap_summary", {})
            ),
            "sector_recommendations": recommendations,
            "overall_planning_readiness": (
                "additional_evidence_and_validation_required"
            ),
            "investment_priority_assessment": (
                "not_assessed_insufficient_evidence"
            ),
        })

    metadata = gap_report["report_metadata"]

    return {
        "report_metadata": {
            "report_type": "infrastructure_planning_recommendations",
            "recommendation_version": "p4_planning_v0.1.0",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source_analysis_version": metadata.get("analysis_version"),
            "p3_run_id": metadata.get("p3_run_id"),
            "p3_method_version": metadata.get("p3_method_version"),
            "p3_validation_status": metadata.get("p3_validation_status"),
            "p3_rights_status": metadata.get("p3_rights_status"),
            "interpretation": (
                "Recommendations describe data collection, validation "
                "and planning actions. They do not represent confirmed "
                "infrastructure shortages or investment priorities."
            ),
        },
        "methodology": {
            "evidence_based_recommendations": True,
            "arbitrary_sector_weights_used": False,
            "infrastructure_shortage_scores_calculated": False,
            "investment_priorities_assigned": False,
            "source_validation_required": True,
        },
        "study_areas": area_results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="InfraVista P4 planning recommendations."
    )

    parser.add_argument(
        "--gap-report",
        default=(
            "reports/p4_screening/"
            "infrastructure_gap_analysis.json"
        ),
    )

    parser.add_argument(
        "--rules",
        default="config/screening_rules.json",
    )

    parser.add_argument(
        "--output",
        default=(
            "reports/p4_screening/"
            "infrastructure_planning_recommendations.json"
        ),
    )

    args = parser.parse_args()

    try:
        gap_report = load_json(Path(args.gap_report))
        rules = load_json(Path(args.rules))

        result = build_recommendations(gap_report, rules)

        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with output_path.open("w", encoding="utf-8") as file:
            json.dump(result, file, indent=2, ensure_ascii=False)

        print("InfraVista P4 planning recommendations: PASS")
        print(f"Study areas: {len(result['study_areas'])}")
        print(f"Output: {output_path.resolve()}")

        for area in result["study_areas"]:
            print(f"\nArea: {area['area_id']}")

            for sector in area["sector_recommendations"]:
                print(
                    f"  {sector['sector']}: "
                    f"{len(sector['data_collection_actions'])} "
                    "data requirements | "
                    f"{len(sector['data_quality_actions'])} "
                    "quality actions | "
                    f"{len(sector['planning_actions'])} "
                    "planning actions"
                )

            print(
                "  Investment priority: "
                f"{area['investment_priority_assessment']}"
            )

        return 0

    except (ValueError, OSError, KeyError, TypeError,
            json.JSONDecodeError) as exc:
        print(f"Planning recommendations failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
