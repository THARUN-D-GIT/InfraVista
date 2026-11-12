"""Focused handoff integration tests using synthetic evidence."""
import copy
import pytest
from infravista.screening.p4_handoff import build_handoff


def sample():
    m = {"p3_run_id": "synthetic_run", "p3_validation_status": "pending", "p3_rights_status": "pending"}
    sector = "transport"
    base = {"area_id": "synthetic_area", "sectors": [{"sector": sector}]}
    ev_sector = {
        "sector": sector, "indicator_readiness": "quality_review_required",
        "available_indicator_ids": ["road_density"], "missing_indicator_ids": [],
        "null_value_indicator_ids": [], "additional_data_required": ["population"],
        "quality_review_required": True, "candidate_recommendation_permitted": False,
        "option_feasibility_established": False,
    }
    return {
        "screening": {"report_metadata": m, "study_areas": [copy.deepcopy(base)]},
        "gaps": {"report_metadata": m, "study_areas": [copy.deepcopy(base)]},
        "evidence": {"metadata": {**m, "p1_approval_confirmed": False},
                     "study_areas": [{"area_id": "synthetic_area", "sectors": [ev_sector]}]},
        "scenarios": {"metadata": {**m, "p1_approval_confirmed": False, "mode": "hypothetical_only"},
                      "summary": {"scenario_count": 1}, "scenarios": [{
                          "scenario_id": "demo", "area_id": "synthetic_area", "sector": sector,
                          "real_world_recommendation_permitted": False,
                          "predicted_benefit": None, "investment_priority": None,
                          "comparison_status": "hypothetical_review_only"}]},
        "demand": {"metadata": {**m, "p1_approval_confirmed": False},
                   "summary": {"sector_assessment_count": 1, "demand_estimates_produced": 0,
                               "real_world_recommendations_produced": 0},
                   "assessments": [{
                       "area_id": "synthetic_area", "sector": sector,
                       "indicator_readiness": "quality_review_required",
                       "available_indicator_ids": ["road_density"], "missing_indicator_ids": [],
                       "null_value_indicator_ids": [], "recommendation_permitted": False,
                       "demand_estimate": None, "infrastructure_shortage": None,
                       "future_demand_forecast": None,
                       "readiness_status": "insufficient_for_demand_estimate"}],
                   "assumptions_register": [{"assumption_id": "synthetic_area:transport:evidence_limits"}]},
    }


def test_valid_handoff():
    result = build_handoff(**sample())
    assert result["summary"]["sector_assessment_count"] == 1
    assert result["summary"]["real_world_recommendations_produced"] == 0


def test_run_mismatch_rejected():
    d = sample(); d["gaps"]["report_metadata"]["p3_run_id"] = "other"
    with pytest.raises(ValueError, match="run IDs"):
        build_handoff(**d)


def test_missing_demand_sector_rejected():
    d = sample(); d["demand"]["assessments"] = []
    with pytest.raises(ValueError, match="Missing demand"):
        build_handoff(**d)


def test_mismatched_indicators_rejected():
    d = sample(); d["demand"]["assessments"][0]["available_indicator_ids"] = []
    with pytest.raises(ValueError, match="mismatch"):
        build_handoff(**d)


def test_recommendation_rejected():
    d = sample(); d["scenarios"]["scenarios"][0]["real_world_recommendation_permitted"] = True
    with pytest.raises(ValueError, match="Unsupported"):
        build_handoff(**d)


def test_quantified_demand_rejected():
    d = sample(); d["demand"]["assessments"][0]["demand_estimate"] = 100
    with pytest.raises(ValueError, match="Unsupported"):
        build_handoff(**d)


def test_p1_approval_not_assumed():
    d = sample(); d["evidence"]["metadata"]["p1_approval_confirmed"] = True
    with pytest.raises(ValueError, match="P1 approval"):
        build_handoff(**d)


def test_scenario_count_mismatch_rejected():
    d = sample(); d["scenarios"]["summary"]["scenario_count"] = 2
    with pytest.raises(ValueError, match="Scenario summary"):
        build_handoff(**d)
