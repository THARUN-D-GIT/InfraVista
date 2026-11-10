
import unittest

from infravista.screening.historical_growth import (
    validate_observation_pair,
)


def make_observation(
    observation_date,
    study_area="HSR",
    season="dry",
    crs="EPSG:32643",
    resolution_m=10,
    cloud_mask_documented=True,
    nodata_mask_documented=True,
    rights_status="approved_internal",
):
    return {
        "observation_date": observation_date,
        "study_area": study_area,
        "season": season,
        "crs": crs,
        "resolution_m": resolution_m,
        "cloud_mask_documented": cloud_mask_documented,
        "nodata_mask_documented": nodata_mask_documented,
        "source": "test_satellite_source",
        "rights_status": rights_status,
    }


class TestHistoricalGrowthReadiness(unittest.TestCase):

    def setUp(self):
        self.valid_pair = [
            make_observation("2020-01-15"),
            make_observation("2025-01-15"),
        ]

    def test_valid_pair_is_ready_for_raster_analysis(self):
        result = validate_observation_pair(self.valid_pair)

        self.assertEqual(
            result["status"],
            "ready_for_raster_analysis",
        )
        self.assertTrue(result["ready_for_raster_analysis"])
        self.assertEqual(result["analysis_status"], "not_performed")
        self.assertEqual(result["growth_status"], "not_assessed")

    def test_missing_observation_pair_is_not_available(self):
        result = validate_observation_pair([])

        self.assertEqual(result["status"], "not_available")
        self.assertFalse(result["ready_for_raster_analysis"])

    def test_single_observation_is_not_enough(self):
        result = validate_observation_pair([self.valid_pair[0]])

        self.assertEqual(result["status"], "not_available")

    def test_invalid_observation_date_is_rejected(self):
        pair = [
            make_observation("2020-13-40"),
            self.valid_pair[1],
        ]

        result = validate_observation_pair(pair)

        self.assertFalse(result["ready_for_raster_analysis"])
        self.assertTrue(
            any("invalid observation_date" in error
                for error in result["errors"])
        )

    def test_non_chronological_dates_are_rejected(self):
        pair = [
            make_observation("2025-01-15"),
            make_observation("2020-01-15"),
        ]

        result = validate_observation_pair(pair)

        self.assertFalse(result["ready_for_raster_analysis"])

    def test_different_crs_is_rejected(self):
        pair = [
            self.valid_pair[0],
            make_observation("2025-01-15", crs="EPSG:4326"),
        ]

        result = validate_observation_pair(pair)

        self.assertFalse(result["ready_for_raster_analysis"])
        self.assertTrue(
            any("crs" in error for error in result["errors"])
        )

    def test_different_resolution_is_rejected(self):
        pair = [
            self.valid_pair[0],
            make_observation("2025-01-15", resolution_m=30),
        ]

        result = validate_observation_pair(pair)

        self.assertFalse(result["ready_for_raster_analysis"])

    def test_different_study_areas_are_rejected(self):
        pair = [
            self.valid_pair[0],
            make_observation("2025-01-15", study_area="Whitefield"),
        ]

        result = validate_observation_pair(pair)

        self.assertFalse(result["ready_for_raster_analysis"])

    def test_different_seasons_are_rejected(self):
        pair = [
            self.valid_pair[0],
            make_observation("2025-01-15", season="monsoon"),
        ]

        result = validate_observation_pair(pair)

        self.assertFalse(result["ready_for_raster_analysis"])

    def test_missing_cloud_mask_documentation_is_rejected(self):
        pair = [
            self.valid_pair[0],
            make_observation(
                "2025-01-15",
                cloud_mask_documented=False,
            ),
        ]

        result = validate_observation_pair(pair)

        self.assertFalse(result["ready_for_raster_analysis"])

    def test_missing_nodata_mask_documentation_is_rejected(self):
        pair = [
            self.valid_pair[0],
            make_observation(
                "2025-01-15",
                nodata_mask_documented=False,
            ),
        ]

        result = validate_observation_pair(pair)

        self.assertFalse(result["ready_for_raster_analysis"])

    def test_unapproved_rights_are_rejected(self):
        pair = [
            self.valid_pair[0],
            make_observation(
                "2025-01-15",
                rights_status="review_required",
            ),
        ]

        result = validate_observation_pair(pair)

        self.assertFalse(result["ready_for_raster_analysis"])

    def test_zero_or_negative_resolution_is_rejected(self):
        for resolution in (0, -10):
            with self.subTest(resolution=resolution):
                pair = [
                    self.valid_pair[0],
                    make_observation(
                        "2025-01-15",
                        resolution_m=resolution,
                    ),
                ]

                result = validate_observation_pair(pair)

                self.assertFalse(
                    result["ready_for_raster_analysis"]
                )

    def test_growth_is_never_assessed_by_readiness_validator(self):
        result = validate_observation_pair(self.valid_pair)

        self.assertEqual(result["growth_status"], "not_assessed")
        self.assertEqual(result["analysis_status"], "not_performed")

    def test_missing_metadata_is_rejected(self):
        incomplete = dict(self.valid_pair[1])
        del incomplete["source"]

        result = validate_observation_pair([
            self.valid_pair[0],
            incomplete,
        ])

        self.assertFalse(result["ready_for_raster_analysis"])
        self.assertTrue(
            any("source" in error for error in result["errors"])
        )


if __name__ == "__main__":
    unittest.main()
