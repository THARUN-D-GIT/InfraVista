
"""InfraVista P4: conservative infrastructure demand readiness.

This module does not estimate population, demand, shortage, or future growth.
Additional data requirements remain unverified until independently evidenced.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


VALID_READINESS = {
    "indicator_evidence_available",
    "quality_review_required",
    "incomplete_indicator_evidence",
}


def require_dict(value, label):
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return value


def require_list(value, label):
    if not isinstance(value, list):
        raise ValueError(f"{label} must be a list")
    return value


def string_list(value, label):
    require_list(value, label)
    if any(not isinstance(x, str) or not x.strip() for x in value):
        raise ValueError(f"{label} must contain nonempty strings")
    if len(set(value)) != len(value):
        raise ValueError(f"{label} contains duplicates")
    return value


def build_demand_report(evidence_report):
    """Build demand-readiness and assumptions-register outputs."""

    require_dict(evidence_report, "evidence report")
    metadata = require_dict(
        evidence_report.get("metadata"), "evidence metadata"
    )

    run_id = metadata.get("p3_run_id")
    if not isinstance(run_id, str) or not run_id.strip():
        raise ValueError("Missing P3 run ID")

    if metadata.get("p1_approval_confirmed") is not False:
        raise ValueError("P1 approval must remain unconfirmed")

    results = []
    assumptions = []
    seen_areas = set()

    for area in require_list(
        evidence_report.get("study_areas"), "study_areas"
    ):
        require_dict(area, "study area")
        area_id = area.get("area_id")

        if not isinstance(area_id, str) or not area_id.strip():
            raise ValueError("Invalid area_id")
        if area_id in seen_areas:
            raise ValueError(f"Duplicate area_id: {area_id}")
        seen_areas.add(area_id)

        seen_sectors = set()

        for sector in require_list(area.get("sectors"), "sectors"):
            require_dict(sector, "sector")
            sector_id = sector.get("sector")

            if not isinstance(sector_id, str) or not sector_id.strip():
                raise ValueError("Invalid sector")
            if sector_id in seen_sectors:
                raise ValueError(f"Duplicate sector: {area_id}/{sector_id}")
            seen_sectors.add(sector_id)

            readiness = sector.get("indicator_readiness")
            if readiness not in VALID_READINESS:
                raise ValueError(f"Invalid readiness: {readiness}")

            available = string_list(
                sector.get("available_indicator_ids"),
                "available_indicator_ids",
            )
            missing = string_list(
                sector.get("missing_indicator_ids"),
                "missing_indicator_ids",
            )
            null_values = string_list(
                sector.get("null_value_indicator_ids"),
                "null_value_indicator_ids",
            )
            flags = string_list(
                sector.get("quality_flags"), "quality_flags"
            )
            required = string_list(
                sector.get("additional_data_required"),
                "additional_data_required",
            )

            if (
                set(available) & set(missing)
                or set(available) & set(null_values)
                or set(missing) & set(null_values)
            ):
                raise ValueError("Indicator status lists overlap")

            if (missing or null_values) and (
                readiness != "incomplete_indicator_evidence"
            ):
                raise ValueError(
                    "Missing/null indicators require incomplete readiness"
                )

            if sector.get("option_feasibility_established") is not False:
                raise ValueError("Option feasibility must be unestablished")

            if sector.get("candidate_recommendation_permitted") is not False:
                raise ValueError("Candidate recommendations must be disabled")

            provenance = require_list(
                sector.get("provenance"), "provenance"
            )

            quality_review = sector.get("quality_review_required")
            if type(quality_review) is not bool:
                raise ValueError("quality_review_required must be boolean")

            reasons = []

            if missing:
                reasons.append("Missing indicator records")
            if null_values:
                reasons.append("Null-valued indicator records")
            if quality_review or flags:
                reasons.append("Indicator quality review required")
            if required:
                reasons.append(
                    "Demand/capacity inputs not independently verified"
                )

            if metadata.get("p3_validation_status") != "validated":
                reasons.append("P3 validation not confirmed")
            if metadata.get("p3_rights_status") != "approved":
                reasons.append("P3 rights approval not confirmed")

            reasons.append("P1 planning scope approval not confirmed")

            assessment_id = f"{area_id}:{sector_id}"

            results.append({
                "assessment_id": assessment_id,
                "area_id": area_id,
                "sector": sector_id,
                "indicator_readiness": readiness,
                "available_indicator_ids": available,
                "missing_indicator_ids": missing,
                "null_value_indicator_ids": null_values,
                "quality_flags": flags,
                "additional_data_requirements": [
                    {
                        "name": name,
                        "verification_status": "not_verified",
                    }
                    for name in required
                ],
                "source_provenance": provenance,
                "readiness_status": "insufficient_for_demand_estimate",
                "demand_estimate": None,
                "infrastructure_shortage": None,
                "future_demand_forecast": None,
                "recommendation_permitted": False,
                "review_reasons": reasons,
            })

            assumptions.append({
                "assumption_id": f"{assessment_id}:evidence_limits",
                "area_id": area_id,
                "sector": sector_id,
                "statement": (
                    "Mapped infrastructure indicators do not by themselves "
                    "establish service adequacy, unmet demand, or shortage."
                ),
                "status": "methodological_safeguard",
                "source_p3_run_id": run_id,
                "validation_required": [
                    "Verify data completeness and quality",
                    "Obtain sector-specific demand and capacity evidence",
                    "Confirm approved planning scope",
                ],
            })

    return {
        "metadata": {
            "module": "p4_demand_readiness",
            "version": "0.1.0",
            "p3_run_id": run_id,
            "p3_method_version": metadata.get("p3_method_version"),
            "p3_validation_status": metadata.get("p3_validation_status"),
            "p3_rights_status": metadata.get("p3_rights_status"),
            "p1_approval_confirmed": False,
            "interpretation": (
                "Demand evidence-readiness assessment only. "
                "No measured demand, shortage, or forecast is produced."
            ),
        },
        "summary": {
            "area_count": len(seen_areas),
            "sector_assessment_count": len(results),
            "demand_estimates_produced": 0,
            "real_world_recommendations_produced": 0,
        },
        "assessments": results,
        "assumptions_register": assumptions,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        default="reports/p4_screening/option_evidence_readiness.json",
    )
    parser.add_argument(
        "--output",
        default="reports/p4_screening/demand_readiness.json",
    )
    args = parser.parse_args()

    try:
        with Path(args.input).open(encoding="utf-8-sig") as handle:
            evidence = json.load(handle)

        report = build_demand_report(evidence)

        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(report, indent=2),
            encoding="utf-8",
        )

        print("P4 demand readiness: PASS")
        print(json.dumps(report["summary"], indent=2))
        print(f"Output: {output}")
        return 0

    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(f"Demand readiness failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
