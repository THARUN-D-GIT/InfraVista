
import json

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import box

from infravista.screening.spatial_visualization import (
    build_spatial_layer,
    build_spatial_summary,
    recover_grid_ids,
    validate_assignments,
    validate_geometry_records,
)


def make_geometry_data():
    return gpd.GeoDataFrame(
        {
            "feature_id": [
                "hsr_g1_facility_count_hospital",
                "hsr_g2_facility_count_hospital",
                "whitefield_g3_facility_count_hospital",
            ],
            "indicator_id": [
                "facility_count_hospital",
                "facility_count_hospital",
                "facility_count_hospital",
            ],
            "area_id": ["hsr", "hsr", "whitefield"],
        },
        geometry=[
            box(77.0, 12.0, 77.1, 12.1),
            box(77.1, 12.0, 77.2, 12.1),
            box(77.2, 12.0, 77.3, 12.1),
        ],
        crs="EPSG:4326",
    )


def make_assignments():
    return pd.DataFrame(
        {
            "grid_id": ["hsr_g1", "hsr_g2", "whitefield_g3"],
            "area_id": ["hsr", "hsr", "whitefield"],
            "cluster": [0, 1, 2],
            "minimum_indicator_coverage": [0.2, 0.8, 1.0],
            "quality_flags": ["review", "", ""],
            "coverage_review": [
                "low_coverage_review",
                "coverage_at_least_0.50",
                "coverage_at_least_0.50",
            ],
            "quality_review_required": [True, False, False],
            "cluster_description": ["A", "B", "C"],
            "screening_interpretation": [
                "Descriptive profile A",
                "Descriptive profile B",
                "Descriptive profile C",
            ],
        }
    )


def test_recover_grid_ids_from_explicit_indicator_suffix():
    gdf = make_geometry_data()

    result = recover_grid_ids(gdf)

    assert result["grid_id"].tolist() == [
        "hsr_g1",
        "hsr_g2",
        "whitefield_g3",
    ]


def test_recover_grid_ids_rejects_wrong_suffix():
    gdf = make_geometry_data()
    gdf.loc[0, "feature_id"] = "incorrect_feature_id"

    with pytest.raises(ValueError, match="Cannot recover grid ID"):
        recover_grid_ids(gdf)


def test_validate_assignments_rejects_duplicate_grid_ids():
    df = make_assignments()
    df.loc[1, "grid_id"] = "hsr_g1"

    with pytest.raises(ValueError, match="duplicate grid IDs"):
        validate_assignments(df)


def test_validate_assignments_rejects_invalid_coverage():
    df = make_assignments()
    df.loc[0, "minimum_indicator_coverage"] = 1.5

    with pytest.raises(ValueError, match=r"\[0, 1\]"):
        validate_assignments(df)


def test_geometry_validation_returns_one_polygon_per_grid():
    gdf = make_geometry_data()
    gdf = recover_grid_ids(gdf)

    result = validate_geometry_records(gdf)

    assert len(result) == 3
    assert result["grid_id"].nunique() == 3
    assert result.crs.to_epsg() == 4326


def test_build_spatial_layer_performs_exact_join(tmp_path):
    geometry_path = tmp_path / "geometry.geojson"
    assignments_path = tmp_path / "assignments.csv"

    make_geometry_data().to_file(
        geometry_path,
        driver="GeoJSON",
    )
    make_assignments().to_csv(assignments_path, index=False)

    result = build_spatial_layer(
        geometry_path,
        assignments_path,
    )

    assert len(result) == 3
    assert result["grid_id"].nunique() == 3
    assert set(result["cluster"]) == {0, 1, 2}
    assert result.geometry.is_valid.all()


def test_build_spatial_layer_rejects_unmatched_grid_ids(tmp_path):
    geometry_path = tmp_path / "geometry.geojson"
    assignments_path = tmp_path / "assignments.csv"

    make_geometry_data().to_file(
        geometry_path,
        driver="GeoJSON",
    )

    assignments = make_assignments()
    assignments.loc[0, "grid_id"] = "missing_grid"
    assignments.to_csv(assignments_path, index=False)

    with pytest.raises(ValueError, match="do not match exactly"):
        build_spatial_layer(
            geometry_path,
            assignments_path,
        )


def test_spatial_summary_reports_descriptive_counts():
    gdf = make_geometry_data()
    gdf = recover_grid_ids(gdf)

    assignments = make_assignments()
    result = gdf.merge(
        assignments,
        on=["grid_id", "area_id"],
        validate="one_to_one",
    )
    result = gpd.GeoDataFrame(
        result,
        geometry="geometry",
        crs=gdf.crs,
    )

    summary = build_spatial_summary(result)

    assert summary["grid_cell_count"] == 3
    assert summary["area_count"] == 2
    assert summary["cluster_count"] == 3

    hsr = next(
        area for area in summary["areas"]
        if area["area_id"] == "hsr"
    )

    assert hsr["grid_count"] == 2
    assert hsr["cells_below_50_percent_coverage"] == 1

    assert "shortages" in summary["interpretation"]
