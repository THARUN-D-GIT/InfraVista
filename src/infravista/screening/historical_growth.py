
"""Historical imagery readiness checks for InfraVista P4.

This module validates metadata for a pair of historical observations.
It does not inspect raster pixels or calculate observed urban growth.

A successful result means the imagery pair is ready for raster analysis,
not that growth or land-cover change has been detected.
"""

import argparse
import json
import sys

from datetime import date, datetime, timezone
from pathlib import Path


REQUIRED_OBSERVATION_FIELDS = (
    "observation_date",
    "study_area",
    "season",
    "crs",
    "resolution_m",
    "cloud_mask_documented",
    "nodata_mask_documented",
    "source",
    "rights_status",
)

ACCEPTED_RIGHTS_STATUSES = {
    "approved_internal",
    "approved_public",
}


def load_json(path: Path) -> dict:
    """Load a JSON object from disk."""
    if not path.is_file():
        raise ValueError(f"File not found: {path}")

    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON object in: {path}")

    return data


def validate_observation(observation: dict, index: int) -> list:
    """Validate required metadata for one observation."""
    errors = []

    if not isinstance(observation, dict):
        return [f"Observation {index} must be a JSON object."]

    for field in REQUIRED_OBSERVATION_FIELDS:
        if field not in observation:
            errors.append(
                f"Observation {index} is missing required field: {field}"
            )

    if errors:
        return errors

    try:
        parsed_date = date.fromisoformat(
            observation["observation_date"]
        )
        if parsed_date.isoformat() != observation["observation_date"]:
            errors.append(
                f"Observation {index} has a non-canonical date."
            )
    except (TypeError, ValueError):
        errors.append(
            f"Observation {index} has an invalid observation_date."
        )

    for field in ("study_area", "season", "crs", "source"):
        value = observation.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append(
                f"Observation {index} has an invalid {field}."
            )

    resolution = observation.get("resolution_m")
    if (
        isinstance(resolution, bool)
        or not isinstance(resolution, (int, float))
        or resolution <= 0
    ):
        errors.append(
            f"Observation {index} resolution_m must be a positive number."
        )

    for field in ("cloud_mask_documented", "nodata_mask_documented"):
        if observation.get(field) is not True:
            errors.append(
                f"Observation {index} must document {field}."
            )

    rights_status = observation.get("rights_status")
    if rights_status not in ACCEPTED_RIGHTS_STATUSES:
        errors.append(
            f"Observation {index} rights_status is not cleared "
            "for the requested use."
        )

    return errors


def validate_observation_pair(observations: list) -> dict:
    """Check whether two observations are comparable and rights-cleared."""

    errors = []

    if not isinstance(observations, list) or len(observations) != 2:
        return {
            "status": "not_available",
            "ready_for_raster_analysis": False,
            "errors": [
                "Exactly two historical observations are required."
            ],
            "warnings": [],
            "observations": [],
        }

    for index, observation in enumerate(observations, start=1):
        errors.extend(validate_observation(observation, index))

    # Avoid comparing incomplete or invalid records.
    if errors:
        return {
            "status": "not_available",
            "ready_for_raster_analysis": False,
            "errors": errors,
            "warnings": [],
            "observations": observations,
        }

    first, second = observations

    first_date = date.fromisoformat(first["observation_date"])
    second_date = date.fromisoformat(second["observation_date"])

    if first_date >= second_date:
        errors.append(
            "Observation dates must be chronological and distinct."
        )

    for field in ("study_area", "season", "crs", "resolution_m"):
        if first[field] != second[field]:
            errors.append(
                f"Observations have incompatible {field} values."
            )

    return {
        "status": (
            "ready_for_raster_analysis"
            if not errors
            else "not_available"
        ),
        "ready_for_raster_analysis": not errors,
        "errors": errors,
        "warnings": [
            "Metadata validation does not establish actual raster "
            "alignment, image quality, classification accuracy, "
            "or observed urban growth.",
            "Raster-level checks must verify dimensions, transforms, "
            "pixel alignment, valid-data masks and cloud contamination."
        ],
        "observations": [
            {
                "observation_date": first["observation_date"],
                "study_area": first["study_area"],
            },
            {
                "observation_date": second["observation_date"],
                "study_area": second["study_area"],
            },
        ],
        "analysis_status": "not_performed",
        "growth_status": "not_assessed",
    }


def build_historical_growth_readiness(input_path: Path) -> dict:
    """Build the historical imagery readiness report."""
    manifest = load_json(input_path)

    observations = manifest.get("observations")

    result = validate_observation_pair(observations)

    return {
        "report_metadata": {
            "module": "infravista.screening.historical_growth",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "input_manifest": str(input_path),
            "analysis_type": "historical_imagery_readiness",
        },
        "historical_growth_readiness": result,
        "interpretation": (
            "No historical growth conclusion is made by this module. "
            "A valid observation pair only permits subsequent "
            "raster-level analysis."
        ),
    }


def main() -> int:
    """Run the historical imagery readiness validator."""
    parser = argparse.ArgumentParser(
        description="Validate historical imagery metadata for InfraVista."
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Path to the historical imagery JSON manifest.",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Path for the readiness JSON report.",
    )

    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    try:
        report = build_historical_growth_readiness(input_path)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as file:
            json.dump(report, file, indent=2)

        print(
            "Historical imagery readiness: "
            f"{report['historical_growth_readiness']['status']}"
        )
        print(f"Report saved: {output_path}")

        for error in report["historical_growth_readiness"]["errors"]:
            print(f"ERROR: {error}")

        return 0

    except (ValueError, json.JSONDecodeError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
