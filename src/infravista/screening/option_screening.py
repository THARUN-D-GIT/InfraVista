
"""InfraVista P4 — Explainable infrastructure option screening.

Prototype-only screening of explicitly supplied hypothetical options.

No actual infrastructure locations are generated or recommended without
documented P1 approval. Unknown constraints never count as passed.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

SECTORS = {
    "healthcare",
    "education",
    "transport",
    "water_infrastructure",
}

CONSTRAINTS = (
    "land_availability",
    "regulatory_permission",
    "technical_feasibility",
)

SIDE_EFFECTS = (
    "flood_hazard",
    "environment",
    "water",
    "terrain",
    "access_equity",
)

VALID_CONSTRAINT_STATES = {"pass", "fail", "unknown"}
VALID_SIDE_EFFECT_STATES = {"clear", "concern", "unknown"}


def require_object(value, name):
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be a JSON object.")
    return value


def validate_option(option):
    """Validate a hypothetical option and its explicit evidence."""

    require_object(option, "option")

    required = (
        "option_id",
        "area_id",
        "sector",
        "description",
        "evidence",
        "constraints",
        "side_effects",
    )

    for field in required:
        if field not in option:
            raise ValueError(f"Option missing required field: {field}")

    for field in ("option_id", "area_id", "description"):
        if not isinstance(option[field], str) or not option[field].strip():
            raise ValueError(f"Invalid {field}.")

    if option["sector"] not in SECTORS:
        raise ValueError(f"Unsupported sector: {option['sector']}")

    evidence = require_object(option["evidence"], "evidence")
    constraints = require_object(option["constraints"], "constraints")
    side_effects = require_object(option["side_effects"], "side_effects")

    if not evidence:
        raise ValueError("At least one evidence requirement is needed.")

    for key, value in evidence.items():
        if not isinstance(key, str) or not key.strip():
            raise ValueError("Invalid evidence requirement name.")
        if type(value) is not bool:
            raise ValueError(f"Evidence '{key}' must be boolean.")

    if set(constraints) != set(CONSTRAINTS):
        raise ValueError(
            f"Constraints must contain exactly: {list(CONSTRAINTS)}"
        )

    for name, state in constraints.items():
        if state not in VALID_CONSTRAINT_STATES:
            raise ValueError(f"Invalid constraint state: {name}={state}")

    if set(side_effects) != set(SIDE_EFFECTS):
        raise ValueError(
            f"Side effects must contain exactly: {list(SIDE_EFFECTS)}"
        )

    for name, state in side_effects.items():
        if state not in VALID_SIDE_EFFECT_STATES:
            raise ValueError(f"Invalid side-effect state: {name}={state}")


def assess_option(option, approved=False):
    """Assess one explicitly supplied hypothetical option."""

    validate_option(option)

    missing_evidence = sorted(
        key for key, available in option["evidence"].items()
        if not available
    )

    failed_constraints = sorted(
        key for key, state in option["constraints"].items()
        if state == "fail"
    )

    unknown_constraints = sorted(
        key for key, state in option["constraints"].items()
        if state == "unknown"
    )

    side_effect_concerns = sorted(
        key for key, state in option["side_effects"].items()
        if state == "concern"
    )

    unknown_side_effects = sorted(
        key for key, state in option["side_effects"].items()
        if state == "unknown"
    )

    reasons = []

    if failed_constraints:
        reasons.append(
            "Hard constraints failed: " + ", ".join(failed_constraints)
        )

    if missing_evidence:
        reasons.append(
            "Evidence unavailable: " + ", ".join(missing_evidence)
        )

    if unknown_constraints:
        reasons.append(
            "Constraints not verified: " + ", ".join(unknown_constraints)
        )

    if side_effect_concerns:
        reasons.append(
            "Potential side effects: " + ", ".join(side_effect_concerns)
        )

    if unknown_side_effects:
        reasons.append(
            "Side effects not assessed: " + ", ".join(unknown_side_effects)
        )

    # Preliminary technical assessment, independent of P1 approval.
    if failed_constraints:
        technical_status = "blocked"
    elif (
        missing_evidence
        or unknown_constraints
        or side_effect_concerns
        or unknown_side_effects
    ):
        technical_status = "needs_review"
    else:
        technical_status = "eligible_for_further_assessment"

    # A separate authorization gate prevents real-world recommendations.
    if approved:
        authorization_status = "approved_use_case"
    else:
        authorization_status = "pending_p1_approval"
        reasons.append(
            "P1 approval has not been confirmed. "
            "Real-world candidate recommendations are disabled."
        )

    return {
        "option_id": option["option_id"],
        "area_id": option["area_id"],
        "sector": option["sector"],
        "description": option["description"],
        "technical_status": technical_status,
        "authorization_status": authorization_status,
        "missing_evidence": missing_evidence,
        "failed_constraints": failed_constraints,
        "unknown_constraints": unknown_constraints,
        "side_effect_concerns": side_effect_concerns,
        "unknown_side_effects": unknown_side_effects,
        "reasons": reasons,
        "recommendation_permitted": (
            approved
            and technical_status == "eligible_for_further_assessment"
        ),
    }


def build_report(options, approved=False):
    """Build a reproducible prototype screening report."""

    if not isinstance(options, list):
        raise ValueError("Options must be a list.")

    if type(approved) is not bool:
        raise ValueError("approved must be boolean.")

    seen_ids = set()
    results = []

    for option in options:
        result = assess_option(option, approved=approved)
        option_id = result["option_id"]

        if option_id in seen_ids:
            raise ValueError(f"Duplicate option_id: {option_id}")

        seen_ids.add(option_id)
        results.append(result)

    return {
        "metadata": {
            "module": "p4_option_screening",
            "version": "0.1.0",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "mode": "hypothetical_prototype",
            "p1_approval_confirmed": approved,
            "interpretation": (
                "Preliminary screening of supplied hypothetical options. "
                "Not an infrastructure forecast, site suitability "
                "certification, or investment recommendation."
            ),
        },
        "summary": {
            "option_count": len(results),
            "blocked_count": sum(
                r["technical_status"] == "blocked" for r in results
            ),
            "needs_review_count": sum(
                r["technical_status"] == "needs_review" for r in results
            ),
            "eligible_for_further_assessment_count": sum(
                r["technical_status"] == "eligible_for_further_assessment"
                for r in results
            ),
            "recommendation_permitted_count": sum(
                r["recommendation_permitted"] for r in results
            ),
        },
        "options": results,
    }


def main():
    parser = argparse.ArgumentParser(
        description="InfraVista P4 hypothetical option screening"
    )
    parser.add_argument("--input", required=True)
    parser.add_argument(
        "--output",
        default="reports/p4_screening/option_screening.json",
    )

    args = parser.parse_args()

    try:
        with Path(args.input).open("r", encoding="utf-8") as handle:
            data = json.load(handle)

        require_object(data, "input")

        # CLI deliberately remains approval-pending. Approval must later
        # be verified and scoped before enabling production candidates.
        report = build_report(
            data.get("options"),
            approved=False,
        )

        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(report, indent=2),
            encoding="utf-8",
        )

        print("P4 option screening: PASS")
        print(json.dumps(report["summary"], indent=2))
        print(f"Output: {output}")
        return 0

    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(f"Option screening failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
