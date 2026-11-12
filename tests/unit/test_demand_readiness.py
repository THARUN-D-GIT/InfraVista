
"""Tests for conservative P4 demand-readiness assessment."""

import copy
import unittest

from infravista.screening.demand_readiness import (
    build_demand_report,
)


def fixture():
    return {
        "metadata": {
            "p3_run_id": "synthetic_run",
            "p3_method_version": "v1",
            "p3_validation_status": "pending",
            "p3_rights_status": "pending",
            "p1_approval_confirmed": False,
        },
        "study_areas": [{
            "area_id": "synthetic_area",
            "sectors": [{
                "sector": "healthcare",
                "indicator_readiness": "quality_review_required",
                "available_indicator_ids": ["facility_count_hospital"],
                "missing_indicator_ids": [],
                "null_value_indicator_ids": [],
                "quality_review_required": True,
                "quality_flags": ["osm_completeness_unverified"],
                "additional_data_required": [
                    "population",
                    "facility_capacity",
                ],
                "provenance": [{
                    "indicator_id": "facility_count_hospital",
                    "record_status": "available",
                    "value": 0,
                    "run_id": "synthetic_run",
                }],
                "option_feasibility_established": False,
                "candidate_recommendation_permitted": False,
            }],
        }],
    }


class TestDemandReadiness(unittest.TestCase):

    def test_report_generated(self):
        result = build_demand_report(fixture())
        self.assertEqual(
            result["summary"]["sector_assessment_count"], 1
        )

    def test_no_demand_estimate(self):
        result = build_demand_report(fixture())
        assessment = result["assessments"][0]
        self.assertIsNone(assessment["demand_estimate"])
        self.assertIsNone(assessment["infrastructure_shortage"])
        self.assertIsNone(assessment["future_demand_forecast"])

    def test_actual_zero_preserved(self):
        result = build_demand_report(fixture())
        self.assertEqual(
            result["assessments"][0]["source_provenance"][0]["value"],
            0,
        )

    def test_requirements_are_unverified(self):
        result = build_demand_report(fixture())
        requirements = result["assessments"][0][
            "additional_data_requirements"
        ]
        self.assertEqual(
            requirements[0]["verification_status"],
            "not_verified",
        )

    def test_assumptions_register_exists(self):
        result = build_demand_report(fixture())
        self.assertEqual(len(result["assumptions_register"]), 1)

    def test_missing_indicators_preserved(self):
        data = fixture()
        sector = data["study_areas"][0]["sectors"][0]
        sector["indicator_readiness"] = "incomplete_indicator_evidence"
        sector["available_indicator_ids"] = []
        sector["missing_indicator_ids"] = ["facility_count_hospital"]
        result = build_demand_report(data)
        self.assertEqual(
            result["assessments"][0]["missing_indicator_ids"],
            ["facility_count_hospital"],
        )

    def test_duplicate_sector_rejected(self):
        data = fixture()
        sector = data["study_areas"][0]["sectors"][0]
        data["study_areas"][0]["sectors"].append(copy.deepcopy(sector))
        with self.assertRaises(ValueError):
            build_demand_report(data)

    def test_p1_approval_not_assumed(self):
        data = fixture()
        data["metadata"]["p1_approval_confirmed"] = True
        with self.assertRaises(ValueError):
            build_demand_report(data)

    def test_overlapping_indicator_status_rejected(self):
        data = fixture()
        sector = data["study_areas"][0]["sectors"][0]
        sector["missing_indicator_ids"] = ["facility_count_hospital"]
        sector["indicator_readiness"] = "incomplete_indicator_evidence"
        with self.assertRaises(ValueError):
            build_demand_report(data)


if __name__ == "__main__":
    unittest.main()
