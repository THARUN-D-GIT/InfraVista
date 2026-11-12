
"""Tests for P4 option evidence integration."""

import copy
import unittest

from infravista.screening.option_evidence_adapter import (
    build_evidence_report,
)


def fixture():
    screening = {
        "report_metadata": {
            "p3_run_id": "test_run",
            "p3_method_version": "v1",
            "p3_validation_status": "pending",
            "p3_rights_status": "pending",
        },
        "study_areas": [{
            "area_id": "synthetic_area",
            "sectors": [{
                "sector": "healthcare",
                "quality_review_required": True,
                "quality_flags_requiring_review": [
                    "osm_completeness_unverified"
                ],
                "indicators": [{
                    "indicator_id": "facility_count_hospital",
                    "record_status": "available",
                    "value": 0,
                    "units": "count",
                    "source_ids": "synthetic_source",
                    "run_id": "test_run",
                    "quality_flags": [
                        "osm_completeness_unverified"
                    ],
                }],
            }],
        }],
    }

    gaps = {
        "report_metadata": copy.deepcopy(screening["report_metadata"]),
        "study_areas": [{
            "area_id": "synthetic_area",
            "sectors": [{
                "sector": "healthcare",
                "indicator_evidence": {
                    "available_indicator_ids": ["facility_count_hospital"],
                    "missing_indicator_ids": [],
                    "null_value_indicator_ids": [],
                },
                "data_quality": {
                    "review_required": True,
                    "quality_flags": [
                        "osm_completeness_unverified"
                    ],
                },
                "additional_data_required_for_gap_assessment": [
                    "population",
                    "facility_capacity",
                ],
            }],
        }],
    }
    return screening, gaps


class TestOptionEvidenceAdapter(unittest.TestCase):

    def test_preserves_actual_zero(self):
        screening, gaps = fixture()
        result = build_evidence_report(screening, gaps)
        indicator = result["study_areas"][0]["sectors"][0]["provenance"][0]
        self.assertEqual(indicator["value"], 0)

    def test_quality_review_required(self):
        screening, gaps = fixture()
        result = build_evidence_report(screening, gaps)
        sector = result["study_areas"][0]["sectors"][0]
        self.assertEqual(
            sector["indicator_readiness"],
            "quality_review_required",
        )

    def test_recommendation_not_permitted(self):
        screening, gaps = fixture()
        result = build_evidence_report(screening, gaps)
        sector = result["study_areas"][0]["sectors"][0]
        self.assertFalse(sector["candidate_recommendation_permitted"])

    def test_missing_indicator_is_preserved(self):
        screening, gaps = fixture()
        indicator = screening["study_areas"][0]["sectors"][0]["indicators"][0]
        indicator["record_status"] = "missing_record"
        indicator["value"] = None
        evidence = gaps["study_areas"][0]["sectors"][0]["indicator_evidence"]
        evidence["available_indicator_ids"] = []
        evidence["missing_indicator_ids"] = ["facility_count_hospital"]

        result = build_evidence_report(screening, gaps)
        sector = result["study_areas"][0]["sectors"][0]
        self.assertEqual(
            sector["indicator_readiness"],
            "incomplete_indicator_evidence",
        )

    def test_mismatched_run_id_rejected(self):
        screening, gaps = fixture()
        gaps["report_metadata"]["p3_run_id"] = "different_run"
        with self.assertRaises(ValueError):
            build_evidence_report(screening, gaps)

    def test_mismatched_study_areas_rejected(self):
        screening, gaps = fixture()
        gaps["study_areas"][0]["area_id"] = "another_area"
        with self.assertRaises(ValueError):
            build_evidence_report(screening, gaps)

    def test_inconsistent_indicator_evidence_rejected(self):
        screening, gaps = fixture()
        gaps["study_areas"][0]["sectors"][0]["indicator_evidence"][
            "available_indicator_ids"
        ] = []
        with self.assertRaises(ValueError):
            build_evidence_report(screening, gaps)

    def test_duplicate_sector_rejected(self):
        screening, gaps = fixture()
        sector = screening["study_areas"][0]["sectors"][0]
        screening["study_areas"][0]["sectors"].append(copy.deepcopy(sector))
        with self.assertRaises(ValueError):
            build_evidence_report(screening, gaps)


if __name__ == "__main__":
    unittest.main()
