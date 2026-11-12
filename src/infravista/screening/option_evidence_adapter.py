
"""Connect P4 screening and gap reports to option evidence readiness.

No candidate locations or investment priorities are generated.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def require_dict(value, label):
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return value


def require_list(value, label):
    if not isinstance(value, list):
        raise ValueError(f"{label} must be a list")
    return value


def unique_by(items, field, label):
    result = {}
    for item in require_list(items, label):
        require_dict(item, label + " item")
        key = item.get(field)
        if not isinstance(key, str) or not key.strip():
            raise ValueError(f"Missing {field} in {label}")
        if key in result:
            raise ValueError(f"Duplicate {field}: {key}")
        result[key] = item
    return result


def build_evidence_report(screening, gaps):
    """Produce traceable evidence readiness for every study-area sector."""

    require_dict(screening, "screening")
    require_dict(gaps, "gaps")

    sm = require_dict(screening.get("report_metadata"), "screening metadata")
    gm = require_dict(gaps.get("report_metadata"), "gap metadata")

    run_id = sm.get("p3_run_id")
    if not isinstance(run_id, str) or not run_id:
        raise ValueError("Screening P3 run ID is missing")
    if gm.get("p3_run_id") != run_id:
        raise ValueError("P3 run IDs do not match")

    for key in ("p3_method_version", "p3_validation_status", "p3_rights_status"):
        if sm.get(key) != gm.get(key):
            raise ValueError(f"Metadata mismatch: {key}")

    screening_areas = unique_by(
        screening.get("study_areas"), "area_id", "screening areas"
    )
    gap_areas = unique_by(
        gaps.get("study_areas"), "area_id", "gap areas"
    )

    if set(screening_areas) != set(gap_areas):
        raise ValueError("Study areas do not match")

    output_areas = []

    for area_id, screening_area in screening_areas.items():
        gap_area = gap_areas[area_id]

        screening_sectors = unique_by(
            screening_area.get("sectors"), "sector", "screening sectors"
        )
        gap_sectors = unique_by(
            gap_area.get("sectors"), "sector", "gap sectors"
        )

        if set(screening_sectors) != set(gap_sectors):
            raise ValueError(f"Sector mismatch in {area_id}")

        sector_results = []

        for sector_id, sector in screening_sectors.items():
            gap_sector = gap_sectors[sector_id]

            indicators = unique_by(
                sector.get("indicators"),
                "indicator_id",
                f"{area_id}/{sector_id} indicators",
            )

            available = []
            missing = []
            null_values = []
            quality_flags = set()
            provenance = []

            for indicator_id, indicator in indicators.items():
                status = indicator.get("record_status")

                if status == "available":
                    if indicator.get("value") is None:
                        raise ValueError(
                            f"{area_id}/{indicator_id}: available value is null"
                        )
                    available.append(indicator_id)
                elif status == "missing_record":
                    missing.append(indicator_id)
                elif status == "null_value":
                    null_values.append(indicator_id)
                else:
                    raise ValueError(
                        f"{area_id}/{indicator_id}: invalid status {status}"
                    )

                flags = indicator.get("quality_flags", [])
                if isinstance(flags, str):
                    flags = [f.strip() for f in flags.split(";") if f.strip()]
                if not isinstance(flags, list):
                    raise ValueError("Invalid quality_flags")

                quality_flags.update(flags)

                provenance.append({
                    "indicator_id": indicator_id,
                    "record_status": status,
                    "value": indicator.get("value"),
                    "units": indicator.get("units"),
                    "source_ids": indicator.get("source_ids"),
                    "acquired_at": indicator.get("acquired_at"),
                    "method_version": indicator.get("method_version"),
                    "run_id": indicator.get("run_id"),
                    "quality_flags": flags,
                })

            gap_evidence = require_dict(
                gap_sector.get("indicator_evidence"),
                "gap indicator evidence",
            )

            comparisons = (
                ("available_indicator_ids", available),
                ("missing_indicator_ids", missing),
                ("null_value_indicator_ids", null_values),
            )

            for key, expected in comparisons:
                actual = gap_evidence.get(key)
                if not isinstance(actual, list) or set(actual) != set(expected):
                    raise ValueError(
                        f"Evidence mismatch: {area_id}/{sector_id}/{key}"
                    )

            gap_quality = require_dict(
                gap_sector.get("data_quality"), "gap data quality"
            )

            quality_flags.update(gap_quality.get("quality_flags", []))
            quality_flags.update(
                sector.get("quality_flags_requiring_review", [])
            )

            additional = require_list(
                gap_sector.get("additional_data_required_for_gap_assessment"),
                "additional data requirements",
            )

            quality_review = bool(
                quality_flags
                or gap_quality.get("review_required")
                or sector.get("quality_review_required")
            )

            if missing or null_values:
                readiness = "incomplete_indicator_evidence"
            elif quality_review:
                readiness = "quality_review_required"
            else:
                readiness = "indicator_evidence_available"

            # Indicator evidence does not establish service adequacy,
            # future demand, site suitability, or option feasibility.
            sector_results.append({
                "sector": sector_id,
                "indicator_readiness": readiness,
                "available_indicator_ids": sorted(available),
                "missing_indicator_ids": sorted(missing),
                "null_value_indicator_ids": sorted(null_values),
                "quality_review_required": quality_review,
                "quality_flags": sorted(quality_flags),
                "additional_data_required": additional,
                "provenance": provenance,
                "option_feasibility_established": False,
                "candidate_recommendation_permitted": False,
            })

        output_areas.append({
            "area_id": area_id,
            "sectors": sector_results,
        })

    return {
        "metadata": {
            "module": "p4_option_evidence_adapter",
            "version": "0.1.0",
            "p3_run_id": run_id,
            "p3_method_version": sm.get("p3_method_version"),
            "p3_validation_status": sm.get("p3_validation_status"),
            "p3_rights_status": sm.get("p3_rights_status"),
            "p1_approval_confirmed": False,
            "interpretation": (
                "Indicator evidence readiness only. "
                "Not a demand forecast, feasibility determination, "
                "or infrastructure investment recommendation."
            ),
        },
        "study_areas": output_areas,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--screening",
        default="reports/p4_screening/multi_sector_screening.json",
    )
    parser.add_argument(
        "--gaps",
        default="reports/p4_screening/infrastructure_gap_analysis.json",
    )
    parser.add_argument(
        "--output",
        default="reports/p4_screening/option_evidence_readiness.json",
    )
    args = parser.parse_args()

    try:
        with open(args.screening, encoding="utf-8") as f:
            screening = json.load(f)
        with open(args.gaps, encoding="utf-8") as f:
            gaps = json.load(f)

        report = build_evidence_report(screening, gaps)

        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(report, indent=2),
            encoding="utf-8",
        )

        print(f"Evidence readiness written to: {output}")
        for area in report["study_areas"]:
            print(f"\n{area['area_id']}")
            for sector in area["sectors"]:
                print(
                    f"  {sector['sector']}: "
                    f"{sector['indicator_readiness']}"
                )
        return 0

    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(f"Evidence adapter failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
