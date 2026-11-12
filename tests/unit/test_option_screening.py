
"""Unit tests for the P4 hypothetical option-screening engine."""

import copy
import unittest

from infravista.screening.option_screening import (
    assess_option,
    build_report,
)


def make_option():
    return {
        "option_id": "synthetic_option_001",
        "area_id": "synthetic_area",
        "sector": "transport",
        "description": "Hypothetical pedestrian connectivity improvement",
        "evidence": {
            "network_data_available": True,
            "accessibility_data_available": True,
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
    }


class TestOptionScreening(unittest.TestCase):

    def test_eligible_synthetic_option(self):
        result = assess_option(make_option(), approved=True)
        self.assertEqual(
            result["technical_status"],
            "eligible_for_further_assessment",
        )
        self.assertTrue(result["recommendation_permitted"])

    def test_p1_approval_gate(self):
        result = assess_option(make_option(), approved=False)
        self.assertEqual(
            result["authorization_status"],
            "pending_p1_approval",
        )
        self.assertFalse(result["recommendation_permitted"])

    def test_failed_hard_constraint_blocks(self):
        option = make_option()
        option["constraints"]["land_availability"] = "fail"
        result = assess_option(option, approved=True)
        self.assertEqual(result["technical_status"], "blocked")
        self.assertFalse(result["recommendation_permitted"])

    def test_unknown_constraint_needs_review(self):
        option = make_option()
        option["constraints"]["technical_feasibility"] = "unknown"
        result = assess_option(option, approved=True)
        self.assertEqual(result["technical_status"], "needs_review")
        self.assertFalse(result["recommendation_permitted"])

    def test_missing_evidence_needs_review(self):
        option = make_option()
        option["evidence"]["accessibility_data_available"] = False
        result = assess_option(option, approved=True)
        self.assertIn(
            "accessibility_data_available",
            result["missing_evidence"],
        )
        self.assertFalse(result["recommendation_permitted"])

    def test_environmental_concern_needs_review(self):
        option = make_option()
        option["side_effects"]["environment"] = "concern"
        result = assess_option(option, approved=True)
        self.assertIn("environment", result["side_effect_concerns"])
        self.assertFalse(result["recommendation_permitted"])

    def test_unknown_side_effect_needs_review(self):
        option = make_option()
        option["side_effects"]["flood_hazard"] = "unknown"
        result = assess_option(option, approved=True)
        self.assertEqual(result["technical_status"], "needs_review")

    def test_invalid_constraint_rejected(self):
        option = make_option()
        option["constraints"]["land_availability"] = "safe"
        with self.assertRaises(ValueError):
            assess_option(option)

    def test_duplicate_options_rejected(self):
        option = make_option()
        with self.assertRaises(ValueError):
            build_report([option, copy.deepcopy(option)])

    def test_report_summary(self):
        option_a = make_option()
        option_b = make_option()
        option_b["option_id"] = "synthetic_option_002"
        option_b["constraints"]["land_availability"] = "fail"

        report = build_report([option_a, option_b])

        self.assertEqual(report["summary"]["option_count"], 2)
        self.assertEqual(report["summary"]["blocked_count"], 1)
        self.assertEqual(
            report["summary"]["recommendation_permitted_count"],
            0,
        )

    def test_boolean_approval_required(self):
        with self.assertRaises(ValueError):
            build_report([make_option()], approved="yes")


if __name__ == "__main__":
    unittest.main()
