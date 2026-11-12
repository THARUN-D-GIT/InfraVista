
"""Tests for evidence-aware hypothetical scenario comparisons."""

import copy
import unittest

from infravista.screening.scenario_engine import (
    build_scenario_report,
)


def fixtures():
    evidence = {
        "metadata": {
            "p3_run_id": "synthetic_run",
            "p3_validation_status": "pending",
            "p3_rights_status": "pending",
        },
        "study_areas": [{
            "area_id": "synthetic_area",
            "sectors": [{
                "sector": "transport",
                "indicator_readiness": "quality_review_required",
                "quality_flags": ["osm_completeness_unverified"],
                "additional_data_required": ["traffic_demand"],
                "missing_indicator_ids": [],
                "null_value_indicator_ids": [],
                "provenance": [{
                    "indicator_id": "synthetic_road_density",
                    "value": 0,
                    "source_ids": "synthetic_source",
                }],
                "option_feasibility_established": False,
                "candidate_recommendation_permitted": False,
            }],
        }],
    }

    scenario = {
        "scenario_id": "synthetic_scenario_001",
        "baseline": {
            "area_id": "synthetic_area",
            "sector": "transport",
            "description": "Existing hypothetical transport network",
        },
        "intervention": {
            "option_id": "synthetic_option_001",
            "area_id": "synthetic_area",
            "sector": "transport",
            "description": "Hypothetical pedestrian connection",
            "evidence": {
                "network_data_available": True,
            },
            "constraints": {
                "land_availability": "pass",
                "regulatory_permission": "pass",
                "technical_feasibility": "pass",
            },
            "side_effects": {
                "flood_hazard": "clear",
                "environment": "clear",
                "water": "clear",
                "terrain": "clear",
                "access_equity": "clear",
            },
        },
        "assumptions": [
            "Intervention is hypothetical",
        ],
        "proposed_effects": [
            "Potentially improved pedestrian connectivity",
        ],
    }

    return scenario, evidence


class TestScenarioEngine(unittest.TestCase):

    def test_scenario_report_generated(self):
        scenario, evidence = fixtures()
        result = build_scenario_report([scenario], evidence)
        self.assertEqual(result["summary"]["scenario_count"], 1)

    def test_p1_gate_remains_closed(self):
        scenario, evidence = fixtures()
        result = build_scenario_report([scenario], evidence)
        item = result["scenarios"][0]
        self.assertFalse(
            item["real_world_recommendation_permitted"]
        )

    def test_proposed_effect_is_unverified(self):
        scenario, evidence = fixtures()
        result = build_scenario_report([scenario], evidence)
        effect = result["scenarios"][0]["proposed_effects"][0]
        self.assertEqual(
            effect["verification_status"],
            "unverified_hypothesis",
        )

    def test_no_predicted_benefit_or_priority(self):
        scenario, evidence = fixtures()
        item = build_scenario_report(
            [scenario], evidence
        )["scenarios"][0]
        self.assertIsNone(item["predicted_benefit"])
        self.assertIsNone(item["investment_priority"])

    def test_provenance_preserves_zero(self):
        scenario, evidence = fixtures()
        item = build_scenario_report(
            [scenario], evidence
        )["scenarios"][0]
        self.assertEqual(
            item["evidence"]["provenance"][0]["value"], 0
        )

    def test_quality_flags_preserved(self):
        scenario, evidence = fixtures()
        item = build_scenario_report(
            [scenario], evidence
        )["scenarios"][0]
        self.assertIn(
            "osm_completeness_unverified",
            item["evidence"]["quality_flags"],
        )

    def test_failed_constraint_blocks(self):
        scenario, evidence = fixtures()
        scenario["intervention"]["constraints"][
            "land_availability"
        ] = "fail"
        item = build_scenario_report(
            [scenario], evidence
        )["scenarios"][0]
        self.assertEqual(
            item["comparison_status"], "constraint_blocked"
        )

    def test_missing_evidence_area_rejected(self):
        scenario, evidence = fixtures()
        scenario["intervention"]["area_id"] = "unknown_area"
        scenario["baseline"]["area_id"] = "unknown_area"
        with self.assertRaises(ValueError):
            build_scenario_report([scenario], evidence)

    def test_mismatched_baseline_rejected(self):
        scenario, evidence = fixtures()
        scenario["baseline"]["sector"] = "healthcare"
        with self.assertRaises(ValueError):
            build_scenario_report([scenario], evidence)

    def test_duplicate_scenarios_rejected(self):
        scenario, evidence = fixtures()
        with self.assertRaises(ValueError):
            build_scenario_report(
                [scenario, copy.deepcopy(scenario)],
                evidence,
            )

    def test_unknown_constraint_requires_review(self):
        scenario, evidence = fixtures()
        scenario["intervention"]["constraints"][
            "technical_feasibility"
        ] = "unknown"
        item = build_scenario_report(
            [scenario], evidence
        )["scenarios"][0]
        self.assertEqual(
            item["intervention"]["technical_status"],
            "needs_review",
        )

    def test_unexpected_recommendation_permission_rejected(self):
        scenario, evidence = fixtures()
        evidence["study_areas"][0]["sectors"][0][
            "candidate_recommendation_permitted"
        ] = True
        with self.assertRaises(ValueError):
            build_scenario_report([scenario], evidence)


if __name__ == "__main__":
    unittest.main()
