
"""Dependency-free unit tests for the P4 screening engine."""

import copy
import json
import tempfile
import unittest
from pathlib import Path

from infravista.screening import screening_engine


class ScreeningEngineTests(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

        self.rules = {
            "schema_version": "1.0.0",
            "screening_version": "p4_rules_test",
            "method": "test_method",
            "principles": {},
            "quality_flags_requiring_review": [
                "osm_completeness_unverified"
            ],
            "assessment": {
                "available_record": "evidence_available",
                "missing_record": "insufficient_evidence",
                "null_value": "value_unavailable",
                "no_records": "no_evidence"
            },
            "sectors": {
                "healthcare": {
                    "description": "Healthcare evidence",
                    "indicators": ["hospital_count", "clinic_count"]
                },
                "transport": {
                    "description": "Transport evidence",
                    "indicators": ["road_density"]
                }
            }
        }

        self.manifest = {
            "run_id": "test_run",
            "method_version": "test_method",
            "validation_status": "not validated",
            "rights_status": "review_required"
        }

        self.geojson = {
            "type": "FeatureCollection",
            "features": [
                self.feature("hospital_count", 0),
                self.feature(
                    "clinic_count",
                    12,
                    ["osm_completeness_unverified"]
                ),
                self.feature("road_density", 4.5)
            ]
        }

        self.package_dir = self.root / "package"
        self.package_dir.mkdir()

        self.rules_path = self.root / "rules.json"

        self.write_json(
            self.package_dir / "manifest.json",
            self.manifest
        )
        self.write_json(
            self.package_dir / "indicators_window.geojson",
            self.geojson
        )
        self.write_json(self.rules_path, self.rules)

    def tearDown(self):
        self.temp_dir.cleanup()

    @staticmethod
    def write_json(path, data):
        path.write_text(
            json.dumps(data),
            encoding="utf-8"
        )

    @staticmethod
    def feature(indicator_id, value, quality_flags=None):
        return {
            "type": "Feature",
            "properties": {
                "area_id": "test_area",
                "indicator_id": indicator_id,
                "value": value,
                "units": "count",
                "coverage_fraction": 1.0,
                "quality_flags": quality_flags or []
            },
            "geometry": None
        }

    def build(self):
        return screening_engine.build_report(
            self.package_dir,
            self.rules_path
        )

    def test_valid_rules_are_accepted(self):
        result = screening_engine.validate_rules(self.rules)

        self.assertEqual(
            set(result),
            {"healthcare", "transport"}
        )

    def test_duplicate_indicator_assignment_is_rejected(self):
        rules = copy.deepcopy(self.rules)

        rules["sectors"]["transport"]["indicators"].append(
            "hospital_count"
        )

        with self.assertRaises(ValueError):
            screening_engine.validate_rules(rules)

    def test_actual_zero_is_preserved_as_available(self):
        report = self.build()

        healthcare = report["study_areas"][0]["sectors"][0]

        hospital = next(
            item for item in healthcare["indicators"]
            if item["indicator_id"] == "hospital_count"
        )

        self.assertEqual(hospital["value"], 0)
        self.assertEqual(hospital["record_status"], "available")

    def test_missing_record_is_not_treated_as_zero(self):
        data = copy.deepcopy(self.geojson)

        data["features"] = [
            feature for feature in data["features"]
            if feature["properties"]["indicator_id"] != "hospital_count"
        ]

        self.write_json(
            self.package_dir / "indicators_window.geojson",
            data
        )

        report = self.build()

        healthcare = report["study_areas"][0]["sectors"][0]

        hospital = next(
            item for item in healthcare["indicators"]
            if item["indicator_id"] == "hospital_count"
        )

        self.assertEqual(hospital["record_status"], "missing_record")
        self.assertIsNone(hospital["value"])

    def test_null_value_is_distinguished_from_missing_record(self):
        data = copy.deepcopy(self.geojson)

        data["features"][0]["properties"]["value"] = None

        self.write_json(
            self.package_dir / "indicators_window.geojson",
            data
        )

        report = self.build()

        healthcare = report["study_areas"][0]["sectors"][0]

        hospital = next(
            item for item in healthcare["indicators"]
            if item["indicator_id"] == "hospital_count"
        )

        self.assertEqual(hospital["record_status"], "null_value")
        self.assertIsNone(hospital["value"])

    def test_quality_flags_trigger_review(self):
        report = self.build()

        healthcare = report["study_areas"][0]["sectors"][0]

        self.assertTrue(healthcare["quality_review_required"])
        self.assertIn(
            "osm_completeness_unverified",
            healthcare["quality_flags_requiring_review"]
        )

    def test_sector_summary_counts_are_correct(self):
        report = self.build()

        healthcare = report["study_areas"][0]["sectors"][0]

        self.assertEqual(
            healthcare["summary"]["expected_indicator_count"], 2
        )
        self.assertEqual(
            healthcare["summary"]["available_indicator_count"], 2
        )
        self.assertEqual(
            healthcare["summary"]["missing_record_count"], 0
        )
        self.assertEqual(
            healthcare["summary"]["null_value_count"], 0
        )

    def test_report_preserves_p3_metadata(self):
        report = self.build()
        metadata = report["report_metadata"]

        self.assertEqual(metadata["p3_run_id"], "test_run")
        self.assertEqual(metadata["p3_method_version"], "test_method")
        self.assertEqual(
            metadata["p3_validation_status"], "not validated"
        )
        self.assertEqual(
            metadata["p3_rights_status"], "review_required"
        )


if __name__ == "__main__":
    unittest.main()
