
import unittest

from infravista.screening.cluster_screening_output import (
    FEATURE_COLUMNS,
    CLUSTER_DESCRIPTIONS,
    load_inputs,
    prepare_screening_data,
    build_cluster_summary,
    build_area_context,
)


class TestClusterScreeningOutput(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        features, metadata, assignments = load_inputs()
        cls.data = prepare_screening_data(
            features, metadata, assignments
        )

    def test_all_grid_cells_are_retained(self):
        self.assertEqual(len(self.data), 201)

    def test_grid_area_pairs_are_unique(self):
        self.assertFalse(
            self.data.duplicated(["grid_id", "area_id"]).any()
        )

    def test_all_three_clusters_are_present(self):
        self.assertEqual(
            set(self.data["cluster"].unique()),
            {0, 1, 2},
        )

    def test_cluster_sizes_match_baseline(self):
        sizes = self.data["cluster"].value_counts().to_dict()

        self.assertEqual(
            sizes,
            {2: 102, 0: 52, 1: 47},
        )

    def test_all_eleven_features_are_present(self):
        for column in FEATURE_COLUMNS:
            self.assertIn(column, self.data.columns)

    def test_feature_values_are_finite(self):
        for column in FEATURE_COLUMNS:
            self.assertTrue(
                self.data[column].map(
                    lambda value: __import__("math").isfinite(value)
                ).all(),
                msg=f"Non-finite values in {column}",
            )

    def test_coverage_is_valid(self):
        coverage = self.data["minimum_indicator_coverage"]

        self.assertTrue(coverage.between(0, 1).all())

    def test_cluster_descriptions_are_present(self):
        for cluster_id, description in CLUSTER_DESCRIPTIONS.items():
            rows = self.data[
                self.data["cluster"] == cluster_id
            ]

            self.assertTrue(
                rows["cluster_description"].eq(description).all()
            )

    def test_quality_review_flag_is_boolean(self):
        self.assertTrue(
            self.data["quality_review_required"].isin(
                [True, False]
            ).all()
        )

    def test_cluster_summary_counts(self):
        summary = build_cluster_summary(self.data)

        self.assertEqual(len(summary), 3)

        sizes = {
            item["cluster"]: item["grid_count"]
            for item in summary
        }

        self.assertEqual(
            sizes,
            {0: 52, 1: 47, 2: 102},
        )

    def test_area_context_contains_both_areas(self):
        context = build_area_context(self.data)

        area_ids = {
            item["area_id"]
            for item in context
        }

        self.assertEqual(
            area_ids,
            {"hsr", "whitefield"},
        )

    def test_no_priority_ranking_is_created(self):
        self.assertTrue(
            self.data["screening_interpretation"]
            .str.contains("not an infrastructure shortage assessment")
            .all()
        )


if __name__ == "__main__":
    unittest.main()
