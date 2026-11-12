
"""Evidence-based infrastructure gap analysis for InfraVista P4.

This module identifies:
- Missing or unavailable indicator evidence.
- Data-quality review requirements.
- Additional datasets required for a genuine infrastructure gap assessment.

It deliberately does not calculate infrastructure shortage scores,
sector rankings, or service adequacy.
"""

import argparse
import json
import sys

from datetime import datetime, timezone
from pathlib import Path


def load_json(path: Path) -> dict:
    """Load a JSON object from disk."""
    if not path.is_file():
        raise ValueError(f"File not found: {path}")

    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON object in: {path}")

    return data


def validate_inputs(report: dict, rules: dict) -> None:
    """Validate the screening report and gap-analysis requirements."""

    if not isinstance(report.get("report_metadata"), dict):
        raise ValueError("Screening report is missing report_metadata.")

    if not isinstance(report.get("study_areas"), list):
        raise ValueError("Screening report study_areas must be a list.")

    sectors = rules.get("sectors")
    requirements = rules.get("future_data_requirements")

    if not isinstance(sectors, dict) or not sectors:
        raise ValueError("Rules must contain sector definitions.")

    if not isinstance(requirements, dict):
        raise ValueError("Rules must contain future_data_requirements.")

    for sector_name, sector_config in sectors.items():
        if not isinstance(sector_config, dict):
            raise ValueError(f"Invalid configuration for sector: {sector_name}")

        if not isinstance(sector_config.get("indicators"), list):
            raise ValueError(
                f"Missing indicators list for sector: {sector_name}"
            )

        if not isinstance(requirements.get(sector_name), list):
            raise ValueError(
                f"Missing future data requirements for: {sector_name}"
            )


def analyze_indicator_evidence(indicators: list) -> dict:
    """Separate available, missing and null indicator evidence."""

    available = []
    missing = []
    null_values = []
    quality_flags = set()

    for indicator in indicators:
        if not isinstance(indicator, dict):
            raise ValueError("Invalid indicator entry in screening report.")

        indicator_id = indicator.get("indicator_id")
        status = indicator.get("record_status")

        if not indicator_id:
            raise ValueError("Indicator entry has no indicator_id.")

        if status == "available":
            available.append(indicator_id)
        elif status == "missing_record":
            missing.append(indicator_id)
        elif status == "null_value":
            null_values.append(indicator_id)
        else:
            raise ValueError(
                f"Unsupported record status '{status}' for {indicator_id}"
            )

        for flag in indicator.get("quality_flags", []):
            quality_flags.add(flag)

    return {
        "available_indicator_ids": sorted(available),
        "missing_indicator_ids": sorted(missing),
        "null_value_indicator_ids": sorted(null_values),
        "quality_flags_found": sorted(quality_flags),
        "summary": {
            "available_count": len(available),
            "missing_record_count": len(missing),
            "null_value_count": len(null_values),
            "total_indicator_count": len(indicators),
        },
    }


def analyze_sector(
    sector_result: dict,
    future_requirements: list,
) -> dict:
    """Identify evidence gaps and assessment readiness for one sector."""

    sector_name = sector_result.get("sector")

    if not sector_name:
        raise ValueError("Sector result is missing its sector name.")

    indicators = sector_result.get("indicators")

    if not isinstance(indicators, list):
        raise ValueError(
            f"Invalid indicator list for sector: {sector_name}"
        )

    evidence = analyze_indicator_evidence(indicators)

    missing = evidence["missing_indicator_ids"]
    null_values = evidence["null_value_indicator_ids"]
    quality_flags = evidence["quality_flags_found"]

    evidence_gap_exists = bool(missing or null_values)

    return {
        "sector": sector_name,
        "description": sector_result.get("description"),
        "evidence_status": sector_result.get("evidence_status"),
        "evidence_gap_exists": evidence_gap_exists,
        "evidence_gap_status": (
            "evidence_gap_identified"
            if evidence_gap_exists
            else "no_missing_indicator_records_detected"
        ),
        "indicator_evidence": evidence,
        "data_quality": {
            "review_required": bool(
                sector_result.get("quality_review_required")
                or quality_flags
            ),
            "quality_flags": quality_flags,
        },
        "additional_data_required_for_gap_assessment": list(
            future_requirements
        ),
        "assessment_limitation": (
            "Infrastructure adequacy or shortage cannot be established "
            "from the available indicators alone. Additional demand, "
            "capacity, accessibility or sector-specific evidence is "
            "required."
        ),
    }


def build_gap_analysis(
    screening_path: Path,
    rules_path: Path,
) -> dict:
    """Build the evidence-based infrastructure gap analysis."""

    report = load_json(screening_path)
    rules = load_json(rules_path)

    validate_inputs(report, rules)

    report_metadata = report["report_metadata"]
    sector_rules = rules["sectors"]
    future_requirements = rules["future_data_requirements"]

    area_results = []

    for area in report["study_areas"]:
        area_id = area.get("area_id")

        if not area_id:
            raise ValueError("Study area is missing area_id.")

        sector_results = area.get("sectors")

        if not isinstance(sector_results, list):
            raise ValueError(
                f"Invalid sectors list for study area: {area_id}"
            )

        results_by_name = {}

        for sector_result in sector_results:
            sector_name = sector_result.get("sector")

            if sector_name in results_by_name:
                raise ValueError(
                    f"Duplicate sector '{sector_name}' in area {area_id}"
                )

            if sector_name not in sector_rules:
                raise ValueError(
                    f"Unknown sector '{sector_name}' in area {area_id}"
                )

            results_by_name[sector_name] = sector_result

        expected_sectors = set(sector_rules)
        actual_sectors = set(results_by_name)

        if expected_sectors != actual_sectors:
            raise ValueError(
                f"Sector mismatch for {area_id}. "
                f"Missing: {sorted(expected_sectors - actual_sectors)}; "
                f"Unexpected: {sorted(actual_sectors - expected_sectors)}"
            )

        analyzed_sectors = []

        for sector_name in sector_rules:
            analyzed_sectors.append(
                analyze_sector(
                    results_by_name[sector_name],
                    future_requirements[sector_name],
                )
            )

        total_available = sum(
            item["indicator_evidence"]["summary"]["available_count"]
            for item in analyzed_sectors
        )

        total_missing = sum(
            item["indicator_evidence"]["summary"]["missing_record_count"]
            for item in analyzed_sectors
        )

        total_null = sum(
            item["indicator_evidence"]["summary"]["null_value_count"]
            for item in analyzed_sectors
        )

        sectors_with_gaps = [
            item["sector"]
            for item in analyzed_sectors
            if item["evidence_gap_exists"]
        ]

        sectors_requiring_review = [
            item["sector"]
            for item in analyzed_sectors
            if item["data_quality"]["review_required"]
        ]

        area_results.append({
            "area_id": area_id,
            "evidence_gap_summary": {
                "sectors_with_evidence_gaps": sectors_with_gaps,
                "sectors_requiring_data_quality_review": (
                    sectors_requiring_review
                ),
                "available_indicator_count": total_available,
                "missing_record_count": total_missing,
                "null_value_count": total_null,
            },
            "sectors": analyzed_sectors,
            "infrastructure_gap_assessment_status": (
                "not_established_additional_data_required"
            ),
        })

    return {
        "report_metadata": {
            "report_type": "evidence_based_infrastructure_gap_analysis",
            "analysis_version": "p4_gap_analysis_v0.1.0",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source_screening_version": (
                report_metadata.get("screening_version")
            ),
            "p3_run_id": report_metadata.get("p3_run_id"),
            "p3_method_version": report_metadata.get("p3_method_version"),
            "p3_validation_status": (
                report_metadata.get("p3_validation_status")
            ),
            "p3_rights_status": report_metadata.get("p3_rights_status"),
            "interpretation": (
                "This report identifies evidence gaps and data-quality "
                "limitations. It does not establish actual infrastructure "
                "shortages, service inadequacy, or investment priorities."
            ),
        },
        "methodology": {
            "approach": "evidence_based",
            "missing_values_are_not_zero": True,
            "null_values_are_distinct_from_missing_records": True,
            "arbitrary_sector_weights_used": False,
            "infrastructure_shortage_scores_calculated": False,
            "demand_or_service_adequacy_inferred": False,
        },
        "study_areas": area_results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="InfraVista P4 evidence-based gap analysis."
    )

    parser.add_argument(
        "--screening-report",
        default="reports/p4_screening/multi_sector_screening.json",
        help="Path to the existing P4 screening report.",
    )

    parser.add_argument(
        "--rules",
        default="config/screening_rules.json",
        help="Path to the screening rules JSON.",
    )

    parser.add_argument(
        "--output",
        default="reports/p4_screening/infrastructure_gap_analysis.json",
        help="Output gap-analysis JSON path.",
    )

    args = parser.parse_args()

    try:
        result = build_gap_analysis(
            Path(args.screening_report),
            Path(args.rules),
        )

        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with output_path.open("w", encoding="utf-8") as file:
            json.dump(result, file, indent=2, ensure_ascii=False)

        print("InfraVista P4 gap analysis: PASS")
        print(f"Study areas: {len(result['study_areas'])}")
        print(f"Output: {output_path.resolve()}")

        for area in result["study_areas"]:
            summary = area["evidence_gap_summary"]

            print(f"\nArea: {area['area_id']}")
            print(
                f"Available: {summary['available_indicator_count']} | "
                f"Missing: {summary['missing_record_count']} | "
                f"Null: {summary['null_value_count']}"
            )
            print(
                "Sectors with evidence gaps: "
                f"{summary['sectors_with_evidence_gaps']}"
            )
            print(
                "Sectors requiring quality review: "
                f"{summary['sectors_requiring_data_quality_review']}"
            )
            print(
                "Infrastructure shortage assessment: "
                f"{area['infrastructure_gap_assessment_status']}"
            )

        return 0

    except (ValueError, OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f"Gap analysis failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
