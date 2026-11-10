
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

RULES_PATH = ROOT / "config" / "historical_growth_rules.json"
METHODOLOGY_PATH = ROOT / "docs" / "historical_growth_methodology.md"


class TestHistoricalGrowthRules(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        with RULES_PATH.open("r", encoding="utf-8") as file:
            cls.rules = json.load(file)

        cls.methodology = METHODOLOGY_PATH.read_text(
            encoding="utf-8-sig"
        )

    def test_rules_file_is_valid_json(self):
        self.assertIsInstance(self.rules, dict)

    def test_project_and_module_metadata(self):
        self.assertEqual(self.rules["project"], "InfraVista")
        self.assertEqual(self.rules["module"], "P4")

    def test_proposed_status_is_preserved(self):
        self.assertEqual(
            self.rules["status"],
            "proposed_pending_methodology_and_data_approval",
        )

    def test_five_required_indicators_exist(self):
        indicator_ids = {
            item["id"] for item in self.rules["indicators"]
        }

        expected = {
            "built_up_area",
            "new_built_up_area",
            "built_up_area_loss",
            "net_built_up_change",
            "built_up_change_percentage",
        }

        self.assertEqual(indicator_ids, expected)

    def test_indicator_ids_are_unique(self):
        indicator_ids = [
            item["id"] for item in self.rules["indicators"]
        ]

        self.assertEqual(
            len(indicator_ids),
            len(set(indicator_ids)),
        )

    def test_percentage_change_requires_positive_baseline(self):
        percentage_indicator = next(
            item for item in self.rules["indicators"]
            if item["id"] == "built_up_change_percentage"
        )

        self.assertIn(
            "Earlier built-up area must be greater than zero.",
            percentage_indicator["validity_conditions"],
        )

    def test_two_observations_are_required(self):
        requirements = self.rules["comparison_requirements"]

        self.assertEqual(requirements["minimum_observations"], 2)
        self.assertTrue(requirements["chronological_order_required"])

    def test_raster_alignment_is_required(self):
        requirements = self.rules["comparison_requirements"]

        self.assertTrue(
            requirements["raster_alignment_verification_required"]
        )

    def test_cloud_and_nodata_masks_are_required(self):
        requirements = self.rules["comparison_requirements"]

        self.assertTrue(requirements["cloud_mask_required"])
        self.assertTrue(requirements["nodata_mask_required"])

    def test_rights_clearance_is_required(self):
        self.assertTrue(
            self.rules["comparison_requirements"]["rights_clearance_required"]
        )

    def test_no_growth_claim_without_raster_analysis(self):
        safeguards = self.rules["reporting_safeguards"]

        self.assertTrue(
            safeguards["no_growth_claim_without_valid_raster_analysis"]
        )

    def test_no_shortage_claim_without_demand_and_capacity(self):
        safeguards = self.rules["reporting_safeguards"]

        self.assertTrue(
            safeguards[
                "no_infrastructure_shortage_claim_without_demand_and_capacity_evidence"
            ]
        )

    def test_p6_validation_is_required(self):
        safeguards = self.rules["reporting_safeguards"]

        self.assertTrue(
            safeguards["p6_independent_validation_required_before_validation_claim"]
        )

    def test_methodology_documents_all_indicators(self):
        expected_terms = [
            "Built-up area",
            "New built-up area",
            "Built-up area loss",
            "Net built-up change",
            "Percentage change",
        ]

        for term in expected_terms:
            with self.subTest(indicator=term):
                self.assertIn(term, self.methodology)

    def test_methodology_preserves_growth_safeguard(self):
        self.assertIn(
            "Claim observed growth without valid raster analysis.",
            self.methodology,
        )

    def test_methodology_documents_implementation_status(self):
        self.assertIn("Historical imagery pair", self.methodology)
        self.assertIn("Not available", self.methodology)
        self.assertIn("Change detection", self.methodology)
        self.assertIn("Not implemented", self.methodology)


if __name__ == "__main__":
    unittest.main()
