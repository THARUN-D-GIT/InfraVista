
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]

CLUSTER_REPORT = (
    ROOT / "reports/p4_clustering/cluster_screening/"
    "cluster_screening_report.json"
)

GAP_REPORT = (
    ROOT / "reports/p4_screening/"
    "infrastructure_gap_analysis.json"
)

PLANNING_REPORT = (
    ROOT / "reports/p4_screening/"
    "infrastructure_planning_recommendations.json"
)

OUTPUT_DIR = ROOT / "reports/p4_reporting"


def load_json(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Required report not found: {path}")

    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON object in {path}")

    return data


def validate_reports(cluster, gap, planning):
    required_cluster = {
        "status", "screening_version", "clusters",
        "area_context", "limitations", "decision",
    }

    missing = required_cluster - set(cluster)
    if missing:
        raise ValueError(
            f"Cluster report missing fields: {sorted(missing)}"
        )

    for name, report in [
        ("Gap analysis", gap),
        ("Planning recommendations", planning),
    ]:
        for field in ["report_metadata", "methodology", "study_areas"]:
            if field not in report:
                raise ValueError(
                    f"{name} report missing field: {field}"
                )

    if cluster["status"] != "PASS":
        raise ValueError("Cluster screening report is not PASS.")

    cluster_areas = {
        item["area_id"] for item in cluster["area_context"]
    }
    gap_areas = {
        item["area_id"] for item in gap["study_areas"]
    }
    planning_areas = {
        item["area_id"] for item in planning["study_areas"]
    }

    if not (cluster_areas == gap_areas == planning_areas):
        raise ValueError(
            "Study-area IDs do not match across the three reports."
        )

    return sorted(cluster_areas)


def build_consolidated_report(cluster, gap, planning):
    areas = validate_reports(cluster, gap, planning)

    gap_by_area = {
        item["area_id"]: item
        for item in gap["study_areas"]
    }

    planning_by_area = {
        item["area_id"]: item
        for item in planning["study_areas"]
    }

    cluster_by_area = {
        item["area_id"]: item
        for item in cluster["area_context"]
    }

    area_sections = []

    for area_id in areas:
        gap_area = gap_by_area[area_id]
        planning_area = planning_by_area[area_id]
        cluster_area = cluster_by_area[area_id]

        gap_summary = gap_area.get(
            "evidence_gap_summary", {}
        )

        source_summary = planning_area.get(
            "source_evidence_gap_summary", {}
        )

        if gap_summary != source_summary:
            raise ValueError(
                f"Evidence gap summaries differ for {area_id}."
            )

        recommendations = {
            item["sector"]: item
            for item in planning_area.get(
                "sector_recommendations", []
            )
        }

        sectors = []

        for sector in gap_area.get("sectors", []):
            sector_name = sector["sector"]
            recommendation = recommendations.get(sector_name)

            if recommendation is None:
                raise ValueError(
                    f"Missing planning recommendation for "
                    f"{area_id}/{sector_name}"
                )

            sectors.append({
                "sector": sector_name,
                "description": sector.get("description"),
                "evidence_status": sector.get("evidence_status"),
                "evidence_gap_exists": sector.get(
                    "evidence_gap_exists"
                ),
                "evidence_gap_status": sector.get(
                    "evidence_gap_status"
                ),
                "indicator_evidence": sector.get(
                    "indicator_evidence", {}
                ),
                "data_quality": sector.get("data_quality", {}),
                "additional_data_required": sector.get(
                    "additional_data_required_for_gap_assessment",
                    [],
                ),
                "assessment_limitation": sector.get(
                    "assessment_limitation"
                ),
                "data_collection_actions": recommendation.get(
                    "data_collection_actions", []
                ),
                "data_quality_actions": recommendation.get(
                    "data_quality_actions", []
                ),
                "planning_actions": recommendation.get(
                    "planning_actions", []
                ),
                "planning_readiness": recommendation.get(
                    "planning_readiness"
                ),
                "investment_priority_assessment": recommendation.get(
                    "investment_priority_assessment"
                ),
            })

        area_sections.append({
            "area_id": area_id,
            "grid_cluster_context": cluster_area,
            "evidence_gap_summary": gap_summary,
            "sector_assessments": sectors,
        })

    return {
        "report_title": "InfraVista - Multi-Sector Infrastructure Screening",
        "report_version": "p4_integrated_report_v0.1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "project_scope": {
            "study_areas": areas,
            "study_area_count": len(areas),
            "grid_cell_count": cluster["grid_cell_count"],
            "feature_count": cluster["feature_count"],
            "cluster_count": cluster["cluster_count"],
            "sectors": [
                "healthcare",
                "education",
                "transport",
                "water_infrastructure",
            ],
        },
        "machine_learning": {
            "method": cluster["method"],
            "screening_version": cluster["screening_version"],
            "decision": cluster["decision"],
            "clusters": cluster["clusters"],
            "limitations": cluster["limitations"],
        },
        "data_provenance": {
            "gap_analysis_metadata": gap["report_metadata"],
            "planning_report_metadata": planning["report_metadata"],
            "gap_analysis_methodology": gap["methodology"],
            "planning_methodology": planning["methodology"],
        },
        "study_area_assessments": area_sections,
        "overall_limitations": [
            "Results describe mapped infrastructure indicators, not verified complete inventories.",
            "Missing records and numeric zero values are not interchangeable.",
            "Infrastructure shortage and service adequacy are not established.",
            "Investment priorities are not assigned.",
            "Only the two pilot study areas are represented.",
            "Independent P6 validation remains pending.",
            "OSM/ODbL rights review remains pending; current status is team use only.",
        ],
    }


def markdown_list(items):
    if not items:
        return "- None recorded.\n"

    return "".join(f"- {item}\n" for item in items)


def build_markdown(report):
    scope = report["project_scope"]
    ml = report["machine_learning"]
    provenance = report["data_provenance"]

    lines = [
        "# InfraVista",
        "## Multi-Sector Infrastructure Screening Report",
        "",
        f"**Report version:** {report['report_version']}",
        f"**Generated:** {report['generated_at']}",
        "",
        "## 1. Executive Summary",
        "",
        (
            f"This prototype analyses {scope['grid_cell_count']} "
            f"grid cells across {scope['study_area_count']} pilot "
            f"study areas using {scope['feature_count']} selected "
            f"infrastructure indicators."
        ),
        "",
        (
            f"The exploratory ML workflow uses "
            f"`{ml['method']}` with {scope['cluster_count']} "
            f"descriptive clusters."
        ),
        "",
        "The results support exploratory infrastructure screening "
        "and evidence-gap identification. They do not establish "
        "infrastructure shortages, service adequacy or investment priorities.",
        "",
        "## 2. Project Scope",
        "",
        f"- Study areas: {', '.join(scope['study_areas'])}",
        f"- Grid cells: {scope['grid_cell_count']}",
        f"- Selected features: {scope['feature_count']}",
        f"- Clusters: {scope['cluster_count']}",
        f"- Sectors: {', '.join(scope['sectors'])}",
        "",
        "## 3. Machine Learning Results",
        "",
        f"**Method:** `{ml['method']}`",
        "",
        f"**Configuration:** {ml['decision'].get('primary_configuration')}",
        "",
        "### Cluster Profiles",
        "",
    ]

    for item in ml["clusters"]:
        lines.extend([
            f"#### Cluster {item['cluster']}",
            "",
            f"- Grid cells: {item['grid_count']}",
            f"- Description: {item['cluster_description']}",
            f"- Area distribution: "
            f"{json.dumps(item['area_distribution'])}",
            f"- Mean minimum indicator coverage: "
            f"{item['mean_minimum_indicator_coverage']:.4f}",
            f"- Cells below 50% coverage: "
            f"{item['cells_below_50_percent_coverage']}",
            f"- Quality-review cells: {item['quality_review_cells']}",
            "",
            "**Mean raw indicator values:**",
            "",
        ])

        for feature, value in item[
            "mean_raw_indicator_values"
        ].items():
            lines.append(f"- `{feature}`: {value}")

        lines.append("")

    lines.extend([
        "## 4. Study-Area Evidence Assessment",
        "",
        "The following assessments are study-area-level findings. "
        "They are not individual grid-cell shortage assessments.",
        "",
    ])

    for area in report["study_area_assessments"]:
        summary = area["evidence_gap_summary"]

        lines.extend([
            f"### {area['area_id'].upper()}",
            "",
            f"- Available indicators: "
            f"{summary.get('available_indicator_count')}",
            f"- Missing records: "
            f"{summary.get('missing_record_count')}",
            f"- Null values: "
            f"{summary.get('null_value_count')}",
            "",
            "**Cluster distribution:**",
            "",
            f"`{json.dumps(area['grid_cluster_context']['cluster_distribution'])}`",
            "",
            "**Sector assessments:**",
            "",
        ])

        for sector in area["sector_assessments"]:
            lines.extend([
                f"#### {sector['sector'].replace('_', ' ').title()}",
                "",
                f"- Evidence status: {sector['evidence_status']}",
                f"- Evidence gap: {sector['evidence_gap_status']}",
                f"- Quality review required: "
                f"{sector.get('data_quality', {}).get('review_required')}",
                f"- Planning readiness: {sector.get('planning_readiness')}",
                "",
                "**Missing indicators:**",
                "",
            ])

            evidence = sector.get("indicator_evidence", {})

            lines.append(
                markdown_list(
                    evidence.get("missing_indicator_ids", [])
                )
            )

            lines.extend([
                "**Additional data required:**",
                "",
                markdown_list(sector["additional_data_required"]),
                "**Data collection actions:**",
                "",
            ])

            for action in sector["data_collection_actions"]:
                lines.append(
                    f"- **{action.get('dataset')}**: "
                    f"{action.get('purpose')} "
                    f"(Status: {action.get('status')})"
                )

            lines.extend([
                "",
                "**Data quality actions:**",
                "",
            ])

            for action in sector["data_quality_actions"]:
                lines.append(
                    f"- **{action.get('quality_flag')}**: "
                    f"{action.get('recommended_action')}"
                )

            lines.extend([
                "",
                "**Planning actions:**",
                "",
                markdown_list(sector["planning_actions"]),
                "**Assessment limitation:**",
                "",
                f"{sector.get('assessment_limitation')}",
                "",
            ])

    lines.extend([
        "## 5. Data Provenance and Governance",
        "",
        f"- P3 run ID: "
        f"`{provenance['gap_analysis_metadata'].get('p3_run_id')}`",
        f"- P3 method: "
        f"`{provenance['gap_analysis_metadata'].get('p3_method_version')}`",
        f"- P3 validation status: "
        f"{provenance['gap_analysis_metadata'].get('p3_validation_status')}",
        f"- P3 rights status: "
        f"{provenance['gap_analysis_metadata'].get('p3_rights_status')}",
        "",
        "## 6. Limitations",
        "",
        markdown_list(report["overall_limitations"]),
        "## 7. Conclusion",
        "",
        "InfraVista demonstrates an evidence-based prototype workflow "
        "for multi-sector infrastructure screening. It combines "
        "mapped infrastructure indicators, exploratory clustering, "
        "data-quality review, evidence-gap analysis and planning-data "
        "recommendations.",
        "",
        "Further authoritative datasets, source validation, independent "
        "review and local verification are required before using the "
        "results for actual infrastructure investment or policy decisions.",
        "",
    ])

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Generate the integrated InfraVista screening report."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=OUTPUT_DIR,
    )
    args = parser.parse_args()

    cluster = load_json(CLUSTER_REPORT)
    gap = load_json(GAP_REPORT)
    planning = load_json(PLANNING_REPORT)

    report = build_consolidated_report(
        cluster, gap, planning
    )

    markdown = build_markdown(report)

    args.output_dir.mkdir(parents=True, exist_ok=True)

    json_path = args.output_dir / "infravista_screening_report.json"
    markdown_path = args.output_dir / "infravista_screening_report.md"

    with json_path.open("w", encoding="utf-8") as file:
        json.dump(report, file, indent=2, ensure_ascii=False)

    markdown_path.write_text(markdown, encoding="utf-8")

    print("\nINFRAVISTA INTEGRATED REPORT")
    print("=" * 45)
    print("Status: PASS")
    print("Study areas:", report["project_scope"]["study_area_count"])
    print("Grid cells:", report["project_scope"]["grid_cell_count"])
    print("Clusters:", report["project_scope"]["cluster_count"])
    print(
        "Sector assessments:",
        sum(
            len(area["sector_assessments"])
            for area in report["study_area_assessments"]
        ),
    )
    print("\nGenerated files:")
    print(json_path)
    print(markdown_path)


if __name__ == "__main__":
    main()
