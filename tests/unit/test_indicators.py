"""Known-answer tests on tiny synthetic data in a metric CRS (no OSM data, no licence issue)."""
import math

import geopandas as gpd
import pytest
from shapely.geometry import LineString, Point, Polygon, box

from infravista.indicators import facilities, roads, water
from infravista.indicators.common import make_grid, make_record, window_polygon

CRS = "EPSG:32643"


def test_window_area_is_circle():
    w = window_polygon(12.9116, 77.6389, 2500, CRS)
    assert abs(w.area - math.pi * 2500**2) / (math.pi * 2500**2) < 0.005


def test_grid_areas_sum_to_window():
    w = window_polygon(12.9116, 77.6389, 2500, CRS)
    g = make_grid(w, 500, "t", CRS)
    assert abs(g["area_in_window_m2"].sum() - w.area) < 1.0          # no double count, no gap
    assert g["coverage_fraction"].between(0, 1.0000001).all()
    assert g["cell_id"].is_unique


def _square_window():
    return box(0, 0, 1000, 1000)


def test_road_length_split_across_cells():
    grid = make_grid(_square_window(), 500, "t", CRS)                # 4 cells
    line = gpd.GeoDataFrame({"feature_id": ["w/1"], "highway": ["residential"]},
                            geometry=[LineString([(0, 250), (1000, 250)])], crs=CRS)
    groups = {"motorised_network": ["residential"]}
    by_cell = roads.length_by_cell(line, grid, groups)
    assert by_cell.sum() == pytest.approx(1000.0)
    assert len(by_cell) == 2 and all(v == pytest.approx(500.0) for v in by_cell)


def test_unknown_highway_class_is_reported_not_dropped():
    line = gpd.GeoDataFrame({"feature_id": ["w/1"], "highway": ["bridleway"]},
                            geometry=[LineString([(0, 0), (100, 0)])], crs=CRS)
    out = roads.length_by_group(line, {"motorised_network": ["residential"]})
    assert out[roads.OTHER] == pytest.approx(100.0)


def test_not_existing_roads_kept_in_their_own_group():
    line = gpd.GeoDataFrame({"feature_id": ["w/1"], "highway": ["proposed"]},
                            geometry=[LineString([(0, 0), (100, 0)])], crs=CRS)
    out = roads.length_by_group(line, {"motorised_network": ["residential"], "not_existing": ["proposed"]})
    assert out["not_existing"] == pytest.approx(100.0) and out["motorised_network"] == 0


def test_facility_polygon_absorbs_nearby_point():
    cats = {"school": ("amenity", "school")}
    pts = gpd.GeoDataFrame({"feature_id": ["n/1", "n/2"], "amenity": ["school", "school"]},
                           geometry=[Point(50, 50), Point(900, 900)], crs=CRS)
    polys = gpd.GeoDataFrame({"feature_id": ["w/9"], "amenity": ["school"]},
                             geometry=[Polygon([(0, 0), (100, 0), (100, 100), (0, 100)])], crs=CRS)
    pts, polys = facilities.categorize(pts, cats), facilities.categorize(polys, cats)
    reps, st = facilities.dedupe(pts, polys, {"categories": ["school"], "tolerance_m": 25})
    assert st["points_absorbed_by_polygon"] == 1 and st["deduplicated_total"] == 2


def test_overlapping_water_polygons_not_double_counted():
    a = Polygon([(0, 0), (100, 0), (100, 100), (0, 100)])
    b = Polygon([(50, 0), (150, 0), (150, 100), (50, 100)])
    wp = gpd.GeoDataFrame({"feature_id": ["a", "b"]}, geometry=[a, b], crs=CRS)
    assert water.water_union(wp).area == pytest.approx(15000.0)




def test_waterway_length_by_type_is_preserved_in_grid():
    grid = make_grid(_square_window(), 500, "t", CRS)
    line = gpd.GeoDataFrame(
        {"feature_id": ["w/1"], "waterway": ["drain"]},
        geometry=[LineString([(0, 250), (1000, 250)])],
        crs=CRS,
    )
    by_cell = water.waterway_length_by_type_by_cell(line, grid)
    assert by_cell.loc[("t_g500_0_0", "drain")] == pytest.approx(500.0)
    assert by_cell.loc[("t_g500_1_0", "drain")] == pytest.approx(500.0)
    assert by_cell.sum() == pytest.approx(1000.0)

def test_unknown_stays_null_in_record():
    r = make_record(feature_id="x", area_id="z", indicator_id="i", value=None, units="count",
                    denominator=None, coverage_fraction=None, quality_flags=["a"], source_ids=["s"],
                    acquired_at="2026-11-03", run_id="r", geometry=None)
    assert r["value"] is None and r["denominator"] is None     # never coerced to 0

def test_total_waterway_length_is_sum_of_all_types():
    lines = gpd.GeoDataFrame(
        {
            "feature_id": ["w/1", "w/2"],
            "waterway": ["drain", "stream"],
        },
        geometry=[
            LineString([(0, 250), (500, 250)]),
            LineString([(0, 750), (500, 750)]),
        ],
        crs=CRS,
    )

    by_type = water.waterway_length_by_type(lines)
    total_length_m = water.waterway_total_length(lines)

    assert total_length_m == pytest.approx(1000.0)
    assert total_length_m == pytest.approx(by_type.sum())
