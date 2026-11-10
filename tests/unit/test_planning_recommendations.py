
import unittest

from infravista.screening.planning_recommendations import (
    build_sector_recommendations,
    build_recommendations,
)


class TestPlanningRecommendations(unittest.TestCase):

    def test_healthcare_recommendations(self):
        sector = {
            "sector": "healthcare",
            "evidence_gap_status": (
                "no_missing_indicator_records_detected"
            ),
            "indicator_evidence": {
                "missing_indicator_ids": [],
                "null_value_indicator_ids": [],
            },
            "data_quality": {
                "review_required": True,
                "quality_flags": [
                    "osm_completeness_unverified",
                ],
            },
        }

        result = build_sector_recommendations(
            sector,
            ["population", "facility_capacity"],
        )

        self.assertEqual(result["sector"], "healthcare")
        self.assertEqual(len(result["data_collection_actions"]), 2)
        self.assertEqual(len(result["planning_actions"]), 3)
        self.assertEqual(len(result["data_quality_actions"]), 1)

    def test_missing_indicator_is_preserved(self):
        sector = {
            "sector": "water_infrastructure",
            "evidence_gap_status": "evidence_gap_identified",
            "indicator_evidence": {
                "missing_indicator_ids": [
                    "waterway_density_km_per_km2_river",
                ],
                "null_value_indicator_ids": [],
            },
            "data_quality": {
                "review_required": True,
                "quality_flags": [
                    "indicator_record_missing",
                ],
            },
        }

        result = build_sector_recommendations(
            sector,
            ["flood_history"],
        )

        self.assertEqual(
            result["missing_indicator_ids"],
            ["waterway_density_km_per_km2_river"],
        )

        self.assertEqual(
            result["data_collection_actions"][0]["dataset"],
            "flood_history",
        )

    def test_unknown_quality_flag_gets_review_action(self):
        sector = {
            "sector": "transport",
            "evidence_gap_status": "no_missing_indicator_records_detected",
            "indicator_evidence": {
                "missing_indicator_ids": [],
                "null_value_indicator_ids": [],
            },
            "data_quality": {
                "review_required": True,
                "quality_flags": ["new_unrecognized_flag"],
            },
        }

        result = build_sector_recommendations(
            sector,
            ["road_condition"],
        )

        self.assertEqual(
            result["data_quality_actions"][0]["quality_flag"],
            "new_unrecognized_flag",
        )

        self.assertIn(
            "Review this quality flag",
            result["data_quality_actions"][0]["recommended_action"],
        )

    def test_investment_priority_is_not_assigned(self):
        sector = {
            "sector": "education",
            "evidence_gap_status": "no_missing_indicator_records_detected",
            "indicator_evidence": {
                "missing_indicator_ids": [],
                "null_value_indicator_ids": [],
            },
            "data_quality": {
                "review_required": False,
                "quality_flags": [],
            },
        }

        result = build_sector_recommendations(
            sector,
            ["student_population"],
        )

        self.assertEqual(
            result["investment_priority_assessment"],
            "not_assessed_insufficient_evidence",
        )

    def test_complete_report_preserves_p3_metadata(self):
        gap_report = {
            "report_metadata": {
                "analysis_version": "p4_gap_analysis_v0.1.0",
                "p3_run_id": "test_run",
                "p3_method_version": "p3_test",
                "p3_validation_status": "pending",
                "p3_rights_status": "review_required",
            },
            "study_areas": [
                {
                    "area_id": "test_area",
                    "evidence_gap_summary": {
                        "missing_record_count": 0,
                    },
                    "sectors": [
                        {
                            "sector": "healthcare",
                            "evidence_gap_status": "no_missing_indicator_records_detected",
                            "indicator_evidence": {
                                "missing_indicator_ids": [],
                                "null_value_indicator_ids": [],
                            },
                            "data_quality": {
                                "review_required": False,
                                "quality_flags": [],
                            },
                        }
                    ],
                }
            ],
        }

        rules = {
            "future_data_requirements": {
                "healthcare": ["population"],
            }
        }

        result = build_recommendations(gap_report, rules)

        metadata = result["report_metadata"]

        self.assertEqual(metadata["p3_run_id"], "test_run")
        self.assertEqual(
            metadata["p3_validation_status"],
            "pending",
        )
        self.assertEqual(
            metadata["p3_rights_status"],
            "review_required",
        )

        self.assertEqual(len(result["study_areas"]), 1)

    def test_duplicate_sectors_are_rejected(self):
        gap_report = {
            "report_metadata": {},
            "study_areas": [
                {
                    "area_id": "test_area",
                    "sectors": [
                        {"sector": "healthcare"},
                        {"sector": "healthcare"},
                    ],
                }
            ],
        }

        with self.assertRaises(ValueError):
            build_recommendations(
                gap_report,
                {
                    "future_data_requirements": {
                        "healthcare": ["population"],
                    }
                },
            )


if __name__ == "__main__":
    unittest.main()
