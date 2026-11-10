
import json
from pathlib import Path

import pytest

from infravista.screening.report_generator import (
    validate_reports,
    build_consolidated_report,
    build_markdown,
)


ROOT = Path(__file__).resolve().parents[2]

CLUSTER_PATH = (
    ROOT
    / "reports"
    / "p4_clustering"
    / "cluster_screening"
    / "cluster_screening_report.json"
)

GAP_PATH = (
    ROOT
    / "reports"
    / "p4_screening"
    / "infrastructure_gap_analysis.json"
)

PLANNING_PATH = (
    ROOT
    / "reports"
    / "p4_screening"
    / "infrastructure_planning_recommendations.json"
)


def load_json(path):
    """Load a JSON report from disk."""
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


@pytest.fixture
def source_reports():
    """Load all source reports required by the integrated report."""
    return (
        load_json(CLUSTER_PATH),
        load_json(GAP_PATH),
        load_json(PLANNING_PATH),
    )


@pytest.fixture
def consolidated_report(source_reports):
    """Build the consolidated report using actual source reports."""
    cluster, gap, planning = source_reports

    return build_consolidated_report(
        cluster,
        gap,
        planning,
    )


def test_source_reports_pass_validation(source_reports):
    cluster, gap, planning = source_reports

    validate_reports(cluster, gap, planning)


def test_report_has_correct_project_scope(consolidated_report):
    scope = consolidated_report["project_scope"]

    assert scope["study_area_count"] == 2
    assert scope["grid_cell_count"] == 201
    assert scope["feature_count"] == 11
    assert scope["cluster_count"] == 3

    assert set(scope["study_areas"]) == {
        "hsr",
        "whitefield",
    }


def test_machine_learning_clusters_are_preserved(
    consolidated_report,
):
    clusters = consolidated_report["machine_learning"]["clusters"]

    assert len(clusters) == 3

    total_cells = sum(
        cluster["grid_count"]
        for cluster in clusters
    )

    assert total_cells == 201


def test_both_study_areas_have_four_sector_assessments(
    consolidated_report,
):
    areas = consolidated_report["study_area_assessments"]

    assert len(areas) == 2

    for area in areas:
        assert len(area["sector_assessments"]) == 4


def test_missing_records_are_not_converted_to_zero(
    consolidated_report,
):
    for area in consolidated_report["study_area_assessments"]:
        summary = area["evidence_gap_summary"]

        assert summary["available_indicator_count"] == 18
        assert summary["missing_record_count"] == 2
        assert summary["null_value_count"] == 0


def test_water_infrastructure_gap_is_preserved(
    consolidated_report,
):
    for area in consolidated_report["study_area_assessments"]:
        water = next(
            sector
            for sector in area["sector_assessments"]
            if sector["sector"] == "water_infrastructure"
        )

        assert water["evidence_gap_status"] == (
            "evidence_gap_identified"
        )

        assert water["evidence_gap_exists"] is True


def test_grid_context_is_separate_from_area_evidence(
    consolidated_report,
):
    for area in consolidated_report["study_area_assessments"]:
        assert "grid_cluster_context" in area
        assert "evidence_gap_summary" in area

        assert area["grid_cluster_context"]["grid_count"] in {
            100,
            101,
        }


def test_investment_priority_is_not_assessed(
    consolidated_report,
):
    for area in consolidated_report["study_area_assessments"]:
        for sector in area["sector_assessments"]:
            assert sector["investment_priority_assessment"] == (
                "not_assessed_insufficient_evidence"
            )


def test_markdown_contains_required_sections(
    consolidated_report,
):
    markdown = build_markdown(consolidated_report)

    required_sections = [
        "Executive Summary",
        "Project Scope",
        "Machine Learning Results",
        "Study-Area Evidence Assessment",
        "Data Provenance and Governance",
        "Limitations",
        "Conclusion",
    ]

    for section in required_sections:
        assert section in markdown


def test_markdown_mentions_both_study_areas(
    consolidated_report,
):
    markdown = build_markdown(consolidated_report).lower()

    assert "hsr" in markdown
    assert "whitefield" in markdown


def test_markdown_preserves_cluster_interpretation(
    consolidated_report,
):
    markdown = build_markdown(consolidated_report).lower()

    # Clusters must be described as exploratory patterns,
    # not as infrastructure investment priorities.
    assert "descriptive clusters" in markdown
    assert "investment priorities" in markdown

    # The report must not claim that clusters are priority rankings.
    assert "not a priority ranking" not in markdown


def test_validation_rejects_mismatched_study_areas(
    source_reports,
):
    cluster, gap, planning = source_reports

    invalid_gap = json.loads(json.dumps(gap))

    invalid_gap["study_areas"][0]["area_id"] = "invalid_area"

    with pytest.raises((ValueError, AssertionError)):
        validate_reports(
            cluster,
            invalid_gap,
            planning,
        )
