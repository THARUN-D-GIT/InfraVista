
import json
import tempfile
import unittest

from pathlib import Path

from infravista.screening.gap_analysis import (
    analyze_indicator_evidence,
    analyze_sector,
    build_gap_analysis,
)


class TestGapAnalysis(unittest.TestCase):

    def test_missing_and_null_are_separate(self):
        indicators = [
            {"indicator_id": "hospital", "record_status": "available"},
            {"indicator_id": "clinic", "record_status": "missing_record"},
            {"indicator_id": "school", "record_status": "null_value"},
        ]

        result = analyze_indicator_evidence(indicators)

        self.assertEqual(result["summary"]["available_count"], 1)
        self.assertEqual(result["summary"]["missing_record_count"], 1)
        self.assertEqual(result["summary"]["null_value_count"], 1)

    def test_actual_zero_remains_available(self):
        indicators = [
            {
                "indicator_id": "road_density",
                "record_status": "available",
                "value": 0.0,
            }
        ]

        result = analyze_indicator_evidence(indicators)

        self.assertEqual(
            result["available_indicator_ids"],
            ["road_density"],
        )
        self.assertEqual(result["summary"]["available_count"], 1)
        self.assertEqual(result["summary"]["missing_record_count"], 0)

    def test_quality_flags_are_preserved(self):
        indicators = [
            {
                "indicator_id": "hospital",
                "record_status": "available",
                "quality_flags": ["osm_completeness_unverified"],
            }
        ]

        result = analyze_indicator_evidence(indicators)

        self.assertIn(
            "osm_completeness_unverified",
            result["quality_flags_found"],
        )

    def test_sector_identifies_evidence_gap(self):
        sector = {
            "sector": "water_infrastructure",
            "description": "Water infrastructure evidence",
            "evidence_status": "insufficient_evidence",
            "quality_review_required": True,
            "indicators": [
                {
                    "indicator_id": "water_area_share",
                    "record_status": "available",
                    "quality_flags": [],
                },
                {
                    "indicator_id": "river_density",
                    "record_status": "missing_record",
                    "quality_flags": [],
                },
            ],
        }

        result = analyze_sector(
            sector,
            ["flood_history", "rainfall"],
        )

        self.assertTrue(result["evidence_gap_exists"])
        self.assertEqual(
            result["evidence_gap_status"],
            "evidence_gap_identified",
        )
        self.assertEqual(
            result["indicator_evidence"]["missing_indicator_ids"],
            ["river_density"],
        )
        self.assertTrue(result["data_quality"]["review_required"])

    def test_future_data_requirements_are_retained(self):
        sector = {
            "sector": "healthcare",
            "description": "Healthcare evidence",
            "evidence_status": "evidence_available",
            "quality_review_required": False,
            "indicators": [
                {
                    "indicator_id": "hospital",
                    "record_status": "available",
                    "quality_flags": [],
                }
            ],
        }

        requirements = [
            "population",
            "facility_capacity",
            "travel_time",
        ]

        result = analyze_sector(sector, requirements)

        self.assertEqual(
            result["additional_data_required_for_gap_assessment"],
            requirements,
        )

    def test_complete_report_preserves_p3_metadata(self):
        rules = {
            "screening_version": "p4_rules_v0.1.0",
            "sectors": {
                "healthcare": {
                    "description": "Healthcare evidence",
                    "indicators": ["hospital"],
                }
            },
            "future_data_requirements": {
                "healthcare": ["population", "facility_capacity"]
            },
        }

        screening_report = {
            "report_metadata": {
                "screening_version": "p4_rules_v0.1.0",
                "p3_run_id": "test_run_001",
                "p3_method_version": "p3_test_v0.1.0",
                "p3_validation_status": "pending",
                "p3_rights_status": "review_required",
            },
            "study_areas": [
                {
                    "area_id": "test_area",
                    "sectors": [
                        {
                            "sector": "healthcare",
                            "description": "Healthcare evidence",
                            "evidence_status": "evidence_available",
                            "quality_review_required": False,
                            "indicators": [
                                {
                                    "indicator_id": "hospital",
                                    "record_status": "available",
                                    "value": 0.0,
                                    "quality_flags": [],
                                }
                            ],
                        }
                    ],
                }
            ],
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            screening_path = temp_path / "screening.json"
            rules_path = temp_path / "rules.json"

            screening_path.write_text(
                json.dumps(screening_report),
                encoding="utf-8",
            )

            rules_path.write_text(
                json.dumps(rules),
                encoding="utf-8",
            )

            result = build_gap_analysis(
                screening_path,
                rules_path,
            )

        metadata = result["report_metadata"]

        self.assertEqual(metadata["p3_run_id"], "test_run_001")
        self.assertEqual(
            metadata["p3_validation_status"],
            "pending",
        )
        self.assertEqual(
            metadata["p3_rights_status"],
            "review_required",
        )

        area = result["study_areas"][0]

        self.assertEqual(
            area["evidence_gap_summary"]["available_indicator_count"],
            1,
        )
        self.assertEqual(
            area["evidence_gap_summary"]["missing_record_count"],
            0,
        )

        self.assertEqual(
            area["infrastructure_gap_assessment_status"],
            "not_established_additional_data_required",
        )

    def test_unknown_record_status_is_rejected(self):
        indicators = [
            {
                "indicator_id": "hospital",
                "record_status": "unknown",
            }
        ]

        with self.assertRaises(ValueError):
            analyze_indicator_evidence(indicators)


if __name__ == "__main__":
    unittest.main()
