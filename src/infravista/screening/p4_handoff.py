"""P4 handoff report: conservative, cross-checked aggregation of existing outputs.

This is a packaging/audit module, not a recommendation or forecasting engine.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

DEFAULT_INPUTS = {
    "screening": "reports/p4_screening/multi_sector_screening.json",
    "gaps": "reports/p4_screening/infrastructure_gap_analysis.json",
    "evidence": "reports/p4_screening/option_evidence_readiness.json",
    "scenarios": "reports/p4_screening/scenario_comparison.json",
    "demand": "reports/p4_screening/demand_readiness.json",
}


def _object(value, label):
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def _items(value, label):
    if not isinstance(value, list):
        raise ValueError(f"{label} must be a JSON list")
    return value


def _index_areas(report, label):
    output = {}
    for area in _items(report.get("study_areas"), f"{label}.study_areas"):
        _object(area, f"{label} area")
        key = area.get("area_id")
        if not isinstance(key, str) or not key or key in output:
            raise ValueError(f"{label} has invalid/duplicate area_id: {key!r}")
        output[key] = area
    return output


def _index_sectors(area, label):
    output = {}
    for sector in _items(area.get("sectors"), f"{label}.sectors"):
        _object(sector, f"{label} sector")
        key = sector.get("sector")
        if not isinstance(key, str) or not key or key in output:
            raise ValueError(f"{label} has invalid/duplicate sector: {key!r}")
        output[key] = sector
    return output


def _index_demand(report):
    output = {}
    for item in _items(report.get("assessments"), "demand.assessments"):
        _object(item, "demand assessment")
        key = (item.get("area_id"), item.get("sector"))
        if not all(isinstance(k, str) and k for k in key) or key in output:
            raise ValueError(f"Invalid/duplicate demand assessment: {key}")
        output[key] = item
    return output


def build_handoff(screening, gaps, evidence, scenarios, demand):
    """Validate linked area/sector/run provenance and output bounded handoff."""
    reports = {
        "screening": _object(screening, "screening"),
        "gaps": _object(gaps, "gaps"),
        "evidence": _object(evidence, "evidence"),
        "scenarios": _object(scenarios, "scenarios"),
        "demand": _object(demand, "demand"),
    }
    meta = {
        "screening": _object(screening.get("report_metadata"), "screening metadata"),
        "gaps": _object(gaps.get("report_metadata"), "gap metadata"),
        "evidence": _object(evidence.get("metadata"), "evidence metadata"),
        "scenarios": _object(scenarios.get("metadata"), "scenario metadata"),
        "demand": _object(demand.get("metadata"), "demand metadata"),
    }
    runs = {label: value.get("p3_run_id") for label, value in meta.items()}
    if any(not isinstance(run, str) or not run.strip() for run in runs.values()):
        raise ValueError(f"Missing P3 run IDs: {runs}")
    if len(set(runs.values())) != 1:
        raise ValueError(f"Mismatched P3 run IDs: {runs}")

    for name in ("evidence", "scenarios", "demand"):
        if meta[name].get("p1_approval_confirmed") is not False:
            raise ValueError(f"{name}: P1 approval must be explicitly unconfirmed")
    if meta["scenarios"].get("mode") != "hypothetical_only":
        raise ValueError("Scenario mode must be hypothetical_only")

    area_maps = {name: _index_areas(reports[name], name)
                 for name in ("screening", "gaps", "evidence")}
    areas = set(area_maps["screening"])
    if not areas or any(set(m) != areas for m in area_maps.values()):
        raise ValueError("Study-area IDs differ across source reports")

    demand_map = _index_demand(demand)
    output_areas = []
    expected_pairs = set()
    for area_id in sorted(areas):
        sector_maps = {
            label: _index_sectors(area_maps[label][area_id], f"{label}/{area_id}")
            for label in area_maps
        }
        sector_names = set(sector_maps["screening"])
        if not sector_names or any(set(sm) != sector_names for sm in sector_maps.values()):
            raise ValueError(f"Sector IDs differ for area {area_id}")
        sector_rows = []
        for sector_id in sorted(sector_names):
            key = (area_id, sector_id)
            expected_pairs.add(key)
            if key not in demand_map:
                raise ValueError(f"Missing demand assessment {key}")
            ev = sector_maps["evidence"][sector_id]
            da = demand_map[key]
            if ev.get("indicator_readiness") != da.get("indicator_readiness"):
                raise ValueError(f"Evidence/demand readiness mismatch: {key}")
            for field in ("available_indicator_ids", "missing_indicator_ids", "null_value_indicator_ids"):
                if ev.get(field) != da.get(field):
                    raise ValueError(f"Evidence/demand {field} mismatch: {key}")
            if (ev.get("candidate_recommendation_permitted") is not False
                    or ev.get("option_feasibility_established") is not False
                    or da.get("recommendation_permitted") is not False):
                raise ValueError(f"Unsafe candidate/feasibility declaration: {key}")
            if any(da.get(field) is not None for field in
                   ("demand_estimate", "infrastructure_shortage", "future_demand_forecast")):
                raise ValueError(f"Unsupported quantified conclusion: {key}")
            sector_rows.append({
                "sector": sector_id,
                "screening_evidence_status": sector_maps["screening"][sector_id].get("evidence_status"),
                "gap_evidence_status": sector_maps["gaps"][sector_id].get("evidence_gap_status"),
                "indicator_readiness": ev["indicator_readiness"],
                "available_indicator_count": len(ev["available_indicator_ids"]),
                "missing_indicator_ids": ev["missing_indicator_ids"],
                "null_value_indicator_ids": ev["null_value_indicator_ids"],
                "quality_review_required": ev.get("quality_review_required"),
                "additional_data_required": ev.get("additional_data_required", []),
                "demand_readiness_status": da.get("readiness_status"),
                "real_world_recommendation_permitted": False,
            })
        output_areas.append({"area_id": area_id, "sectors": sector_rows})

    if set(demand_map) != expected_pairs:
        raise ValueError("Demand assessment contains additional unknown area/sector")

    scenario_rows = []
    for scenario in _items(scenarios.get("scenarios"), "scenarios.scenarios"):
        _object(scenario, "scenario")
        key = (scenario.get("area_id"), scenario.get("sector"))
        if key not in expected_pairs:
            raise ValueError(f"Scenario references unknown area/sector: {key}")
        if (scenario.get("real_world_recommendation_permitted") is not False
                or scenario.get("predicted_benefit") is not None
                or scenario.get("investment_priority") is not None):
            raise ValueError(f"Unsupported recommendation/benefit: {scenario.get('scenario_id')}")
        scenario_rows.append({
            "scenario_id": scenario.get("scenario_id"),
            "area_id": key[0],
            "sector": key[1],
            "comparison_status": scenario.get("comparison_status"),
            "review_reasons": scenario.get("review_reasons", []),
            "real_world_recommendation_permitted": False,
        })

    declared = scenarios.get("summary", {}).get("scenario_count")
    if declared != len(scenario_rows):
        raise ValueError("Scenario summary count mismatch")
    dsum = _object(demand.get("summary"), "demand.summary")
    if (dsum.get("sector_assessment_count") != len(expected_pairs)
            or dsum.get("demand_estimates_produced") != 0
            or dsum.get("real_world_recommendations_produced") != 0):
        raise ValueError("Demand summary does not match safe handoff")

    assumptions = _items(demand.get("assumptions_register"), "assumptions_register")
    return {
        "metadata": {
            "module": "p4_consolidated_handoff",
            "version": "0.1.0",
            "p3_run_id": next(iter(runs.values())),
            "p1_approval_confirmed": False,
            "p3_validation_status": meta["evidence"].get("p3_validation_status"),
            "p3_rights_status": meta["evidence"].get("p3_rights_status"),
            "status": "prototype_handoff_pending_external_validation",
            "interpretation": "Cross-checked evidence/readiness handoff; not a forecast, feasibility approval, or investment recommendation.",
        },
        "summary": {
            "study_area_count": len(areas),
            "sector_assessment_count": len(expected_pairs),
            "hypothetical_scenario_count": len(scenario_rows),
            "assumption_count": len(assumptions),
            "demand_estimates_produced": 0,
            "real_world_recommendations_produced": 0,
        },
        "study_areas": output_areas,
        "hypothetical_scenarios": scenario_rows,
        "assumptions_register": assumptions,
        "validation_gates": [
            {"owner": "P1", "gate": "Bounded planning use case and approval", "status": "not_confirmed"},
            {"owner": "P3/P6", "gate": "Indicator data quality and independent validation", "status": "not_confirmed"},
            {"owner": "P2/team", "gate": "OSM/ODbL and data-rights review", "status": "not_confirmed"},
            {"owner": "P2/P6", "gate": "Dated-imagery historical change validation", "status": "not_confirmed"},
            {"owner": "P5", "gate": "Downstream API/UI integration", "status": "not_confirmed"},
        ],
        "source_reports": DEFAULT_INPUTS.copy(),
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    for label, path in DEFAULT_INPUTS.items():
        p.add_argument(f"--{label}", default=path)
    p.add_argument("--output", default="reports/p4_screening/p4_consolidated_handoff.json")
    args = p.parse_args(argv)
    try:
        inputs = {}
        for label in DEFAULT_INPUTS:
            with Path(getattr(args, label)).open(encoding="utf-8-sig") as handle:
                inputs[label] = json.load(handle)
        result = build_handoff(**inputs)
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print("P4 consolidated handoff: PASS")
        print(json.dumps(result["summary"], indent=2))
        print(f"Output: {out}")
        return 0
    except (ValueError, TypeError, KeyError, OSError) as exc:
        print(f"P4 consolidated handoff: FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
