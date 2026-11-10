"""
P4 - P3 Data Audit
Reads and validates the latest P3 indicator package.
Uses Python standard library only.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path


REQUIRED_PROPERTIES = [
    "feature_id",
    "area_id",
    "indicator_id",
    "value",
    "units",
    "denominator",
    "coverage_fraction",
    "evidence_type",
    "quality_flags",
    "source_ids",
    "acquired_at",
    "method_version",
    "run_id",
]

GEOJSON_FILES = [
    "indicators_grid.geojson",
    "indicators_window.geojson",
]


def load_json(path):
    """Load a JSON file and return its contents."""
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def sha256_file(path):
    """Calculate SHA-256 checksum of a file."""
    digest = hashlib.sha256()

    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def add_issue(report, level, message):
    report[level].append(message)


def validate_feature_collection(name, data, manifest, report):
    """Validate one GeoJSON FeatureCollection."""

    if not isinstance(data, dict):
        add_issue(report, "errors", f"{name}: root must be an object")
        return []

    if data.get("type") != "FeatureCollection":
        add_issue(report, "errors", f"{name}: not a FeatureCollection")

    features = data.get("features")

    if not isinstance(features, list):
        add_issue(report, "errors", f"{name}: features must be a list")
        return []

    seen_ids = set()
    indicator_counts = {}
    area_counts = {}

    for index, feature in enumerate(features):
        location = f"{name}, feature {index}"

        if not isinstance(feature, dict):
            add_issue(report, "errors", f"{location}: feature must be an object")
            continue

        if feature.get("type") != "Feature":
            add_issue(report, "errors", f"{location}: invalid feature type")

        properties = feature.get("properties")

        if not isinstance(properties, dict):
            add_issue(report, "errors", f"{location}: properties missing")
            continue

        # Required property checks
        for field in REQUIRED_PROPERTIES:
            if field not in properties:
                add_issue(
                    report,
                    "errors",
                    f"{location}: missing property '{field}'"
                )

        feature_id = properties.get("feature_id")

        if not isinstance(feature_id, str) or not feature_id.strip():
            add_issue(report, "errors", f"{location}: invalid feature_id")
        elif feature_id in seen_ids:
            add_issue(
                report,
                "errors",
                f"{location}: duplicate feature_id '{feature_id}'"
            )
        else:
            seen_ids.add(feature_id)

        # Numeric value validation
        value = properties.get("value")

        if value is not None:
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
            ):
                add_issue(report, "errors", f"{location}: invalid numeric value")
        else:
            add_issue(report, "warnings", f"{location}: value is null")

        # Coverage validation
        coverage = properties.get("coverage_fraction")

        if coverage is not None:
            if (
                isinstance(coverage, bool)
                or not isinstance(coverage, (int, float))
                or not math.isfinite(coverage)
                or not 0 <= coverage <= 1
            ):
                add_issue(
                    report,
                    "errors",
                    f"{location}: invalid coverage_fraction"
                )

        # Provenance consistency
        if properties.get("run_id") != manifest.get("run_id"):
            add_issue(report, "errors", f"{location}: run_id mismatch")

        if properties.get("method_version") != manifest.get("method_version"):
            add_issue(report, "errors", f"{location}: method_version mismatch")

        # Geometry structure checks (not full topological validation)
        geometry = feature.get("geometry")

        if not isinstance(geometry, dict):
            add_issue(report, "errors", f"{location}: geometry missing")
        else:
            geometry_type = geometry.get("type")
            coordinates = geometry.get("coordinates")

            if geometry_type not in ("Polygon", "MultiPolygon"):
                add_issue(
                    report,
                    "warnings",
                    f"{location}: unexpected geometry type '{geometry_type}'"
                )

            if not isinstance(coordinates, list) or not coordinates:
                add_issue(
                    report,
                    "errors",
                    f"{location}: empty or invalid coordinates"
                )

        area_id = properties.get("area_id")
        indicator_id = properties.get("indicator_id")

        if isinstance(area_id, str):
            area_counts[area_id] = area_counts.get(area_id, 0) + 1

        if isinstance(indicator_id, str):
            indicator_counts[indicator_id] = (
                indicator_counts.get(indicator_id, 0) + 1
            )

    return {
        "feature_count": len(features),
        "unique_feature_ids": len(seen_ids),
        "area_counts": area_counts,
        "indicator_counts": indicator_counts,
    }


def audit_package(package_dir):
    """Load and audit the P3 package."""

    package_dir = Path(package_dir)

    report = {
        "status": "PASS",
        "errors": [],
        "warnings": [],
        "files": {},
    }

    manifest_path = package_dir / "manifest.json"

    if not manifest_path.is_file():
        report["errors"].append("manifest.json not found")
        report["status"] = "FAIL"
        return report

    try:
        manifest = load_json(manifest_path)
    except (json.JSONDecodeError, OSError) as error:
        report["errors"].append(f"Cannot read manifest: {error}")
        report["status"] = "FAIL"
        return report

    report["run_id"] = manifest.get("run_id")
    report["method_version"] = manifest.get("method_version")
    report["manifest_validation_status"] = manifest.get("validation_status")
    report["manifest_rights_status"] = manifest.get("rights_status")

    expected_hashes = manifest.get("outputs", {})

    for filename in GEOJSON_FILES:
        path = package_dir / filename

        if not path.is_file():
            report["errors"].append(f"{filename} not found")
            continue

        actual_hash = sha256_file(path)
        expected_hash = expected_hashes.get(filename)

        checksum_status = "not listed"

        if expected_hash:
            checksum_status = (
                "MATCH" if actual_hash == expected_hash else "MISMATCH"
            )

            if checksum_status == "MISMATCH":
                report["errors"].append(
                    f"{filename}: SHA-256 checksum mismatch"
                )

        try:
            data = load_json(path)
        except (json.JSONDecodeError, OSError) as error:
            report["errors"].append(f"{filename}: cannot read JSON: {error}")
            continue

        details = validate_feature_collection(
            filename, data, manifest, report
        )

        report["files"][filename] = {
            "sha256": actual_hash,
            "checksum": checksum_status,
            "details": details,
        }

    # Report missing indicator records in each study window.
    window_info = report["files"].get("indicators_window.geojson", {})
    details = window_info.get("details")

    if details:
        expected_indicators = set(manifest.get("indicator_ids", []))

        for area_id in details["area_counts"]:
            present = {
                feature.get("properties", {}).get("indicator_id")
                for feature in load_json(
                    package_dir / "indicators_window.geojson"
                ).get("features", [])
                if feature.get("properties", {}).get("area_id") == area_id
            }

            missing = sorted(expected_indicators - present)

            if missing:
                report["warnings"].append(
                    f"{area_id}: missing indicator records: {missing}"
                )

    if report["errors"]:
        report["status"] = "FAIL"

    return report


def main():
    parser = argparse.ArgumentParser(
        description="Audit an InfraVista P3 indicator package."
    )

    parser.add_argument(
        "--package-dir",
        required=True,
        help="Directory containing manifest.json and GeoJSON files",
    )

    args = parser.parse_args()
    report = audit_package(args.package_dir)

    print(json.dumps(report, indent=2))

    if report["status"] == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()