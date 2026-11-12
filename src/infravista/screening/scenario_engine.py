
"""InfraVista P4: evidence-aware hypothetical scenario comparisons.

Compares a documented baseline against a proposed intervention.
Does not predict benefits, demand, costs, or real-world suitability.
P1 approval remains unconfirmed.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from infravista.screening.option_screening import assess_option


def require_object(value, label):
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def require_text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a nonempty string")
    return value


def require_text_list(value, label):
    if not isinstance(value, list):
        raise ValueError(f"{label} must be a list")
    for item in value:
        require_text(item, label + " item")
    return value


def evidence_lookup(report):
    """Index evidence readiness without losing source metadata."""
    require_object(report, "evidence report")
    metadata = require_object(report.get("metadata"), "evidence metadata")

    if not metadata.get("p3_run_id"):
        raise ValueError("Missing P3 run ID")

    areas = report.get("study_areas")
    if not isinstance(areas, list):
        raise ValueError("Evidence study_areas must be a list")

    lookup = {}

    for area in areas:
        require_object(area, "evidence area")
        area_id = require_text(area.get("area_id"), "area_id")

        sectors = area.get("sectors")
        if not isinstance(sectors, list):
            raise ValueError("Evidence sectors must be a list")

        for sector in sectors:
            require_object(sector, "evidence sector")
            sector_id = require_text(sector.get("sector"), "sector")
            key = (area_id, sector_id)

            if key in lookup:
                raise ValueError(f"Duplicate evidence sector: {key}")

            lookup[key] = sector

    return lookup, metadata


def compare_scenario(scenario, evidence_index, metadata):
    """Compare a hypothetical baseline and intervention."""

    require_object(scenario, "scenario")

    scenario_id = require_text(
        scenario.get("scenario_id"), "scenario_id"
    )

    baseline = require_object(
        scenario.get("baseline"), "baseline"
    )
    baseline_description = require_text(
        baseline.get("description"), "baseline description"
    )

    option = require_object(
        scenario.get("intervention"), "intervention"
    )

    # Explicitly supplied options only. Never generate locations.
    option_result = assess_option(option, approved=False)

    area_id = option_result["area_id"]
    sector = option_result["sector"]
    key = (area_id, sector)

    if key not in evidence_index:
        raise ValueError(
            f"No evidence found for area={area_id}, sector={sector}"
        )

    if baseline.get("area_id") != area_id:
        raise ValueError("Baseline and intervention area IDs differ")

    if baseline.get("sector") != sector:
        raise ValueError("Baseline and intervention sectors differ")

    assumptions = require_text_list(
        scenario.get("assumptions"), "assumptions"
    )
    proposed_effects = require_text_list(
        scenario.get("proposed_effects"), "proposed_effects"
    )

    evidence = evidence_index[key]

    readiness = evidence.get("indicator_readiness")
    allowed_readiness = {
        "indicator_evidence_available",
        "quality_review_required",
        "incomplete_indicator_evidence",
    }

    if readiness not in allowed_readiness:
        raise ValueError(f"Invalid evidence readiness: {readiness}")

    quality_flags = require_text_list(
        evidence.get("quality_flags"), "quality_flags"
    )
    additional_data = require_text_list(
        evidence.get("additional_data_required"),
        "additional_data_required",
    )

    missing = require_text_list(
        evidence.get("missing_indicator_ids"),
        "missing_indicator_ids",
    )
    null_values = require_text_list(
        evidence.get("null_value_indicator_ids"),
        "null_value_indicator_ids",
    )

    if evidence.get("option_feasibility_established") is not False:
        raise ValueError(
            "Expected unestablished feasibility in evidence adapter"
        )

    if evidence.get("candidate_recommendation_permitted") is not False:
        raise ValueError(
            "Unexpected recommendation permission in evidence adapter"
        )

    if not isinstance(evidence.get("provenance"), list):
        raise ValueError("Evidence provenance must be a list")

    review_reasons = list(option_result["reasons"])

    if readiness != "indicator_evidence_available":
        review_reasons.append(
            f"Sector evidence readiness: {readiness}"
        )

    if additional_data:
        review_reasons.append(
            "Additional demand/adequacy data required: "
            + ", ".join(additional_data)
        )

    if metadata.get("p3_validation_status") != "validated":
        review_reasons.append("P3 evidence validation not confirmed")

    if metadata.get("p3_rights_status") != "approved":
        review_reasons.append("P3 data rights approval not confirmed")

    # Scenario status is descriptive, not a suitability decision.
    if option_result["technical_status"] == "blocked":
        comparison_status = "constraint_blocked"
    else:
        comparison_status = "hypothetical_review_only"

    return {
        "scenario_id": scenario_id,
        "area_id": area_id,
        "sector": sector,
        "baseline": {
            "description": baseline_description,
            "measured_outcomes": None,
        },
        "intervention": {
            "option_id": option_result["option_id"],
            "description": option_result["description"],
            "technical_status": option_result["technical_status"],
            "authorization_status": (
                option_result["authorization_status"]
            ),
            "constraints": {
                "failed": option_result["failed_constraints"],
                "unknown": option_result["unknown_constraints"],
            },
            "side_effects": {
                "concerns": option_result["side_effect_concerns"],
                "unknown": option_result["unknown_side_effects"],
            },
        },
        "assumptions": assumptions,
        "proposed_effects": [
            {
                "description": effect,
                "verification_status": "unverified_hypothesis",
            }
            for effect in proposed_effects
        ],
        "evidence": {
            "indicator_readiness": readiness,
            "missing_indicator_ids": missing,
            "null_value_indicator_ids": null_values,
            "quality_flags": quality_flags,
            "additional_data_required": additional_data,
            "provenance": evidence["provenance"],
            "p3_run_id": metadata["p3_run_id"],
            "p3_validation_status": metadata.get(
                "p3_validation_status"
            ),
            "p3_rights_status": metadata.get("p3_rights_status"),
        },
        "comparison_status": comparison_status,
        "review_reasons": review_reasons,
        "predicted_benefit": None,
        "investment_priority": None,
        "real_world_recommendation_permitted": False,
    }


def build_scenario_report(scenarios, evidence_report):
    """Build a traceable report with the P1 approval gate closed."""

    if not isinstance(scenarios, list):
        raise ValueError("Scenarios must be a list")

    evidence_index, metadata = evidence_lookup(evidence_report)

    seen = set()
    results = []

    for scenario in scenarios:
        result = compare_scenario(
            scenario, evidence_index, metadata
        )

        scenario_id = result["scenario_id"]
        if scenario_id in seen:
            raise ValueError(
                f"Duplicate scenario_id: {scenario_id}"
            )

        seen.add(scenario_id)
        results.append(result)

    return {
        "metadata": {
            "module": "p4_scenario_engine",
            "version": "0.1.0",
            "mode": "hypothetical_only",
            "p1_approval_confirmed": False,
            "p3_run_id": metadata["p3_run_id"],
            "interpretation": (
                "Qualitative baseline/intervention comparison only. "
                "No validated demand, impact, forecast, "
                "or investment-priority estimates."
            ),
        },
        "summary": {
            "scenario_count": len(results),
            "constraint_blocked_count": sum(
                item["comparison_status"] == "constraint_blocked"
                for item in results
            ),
            "real_world_recommendation_count": 0,
        },
        "scenarios": results,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument(
        "--evidence",
        default="reports/p4_screening/option_evidence_readiness.json",
    )
    parser.add_argument(
        "--output",
        default="reports/p4_screening/scenario_comparison.json",
    )
    args = parser.parse_args()

    try:
        with Path(args.input).open(encoding="utf-8") as handle:
            data = json.load(handle)

        with Path(args.evidence).open(encoding="utf-8") as handle:
            evidence = json.load(handle)

        require_object(data, "scenario input")

        report = build_scenario_report(
            data.get("scenarios"), evidence
        )

        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(report, indent=2),
            encoding="utf-8",
        )

        print("P4 hypothetical scenario comparison: PASS")
        print(json.dumps(report["summary"], indent=2))
        print(f"Output: {output}")
        return 0

    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(f"Scenario comparison failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
