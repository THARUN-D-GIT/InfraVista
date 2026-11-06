"""Shared helpers: study window, grid, canonical record builder. All metric work in a projected CRS."""
import math

import geopandas as gpd
import numpy as np
from shapely.geometry import Point, box, mapping

from . import METHOD_VERSION


def window_polygon(lat, lon, radius_m, metric_crs):
    pt = gpd.GeoSeries([Point(lon, lat)], crs="EPSG:4326").to_crs(metric_crs)
    return pt.buffer(radius_m).iloc[0]


def make_grid(window, cell_m, zone_id, metric_crs):
    """Fixed-origin square grid (origin at 0,0 of the metric CRS) clipped to the window.
    cell_id is derived from absolute cell coordinates, so it is stable across runs."""
    minx, miny, maxx, maxy = window.bounds
    ix0, iy0 = math.floor(minx / cell_m), math.floor(miny / cell_m)
    ix1, iy1 = math.ceil(maxx / cell_m), math.ceil(maxy / cell_m)
    rows = []
    for ix in range(ix0, ix1):
        for iy in range(iy0, iy1):
            cell = box(ix * cell_m, iy * cell_m, (ix + 1) * cell_m, (iy + 1) * cell_m)
            inter = cell.intersection(window)
            if inter.is_empty or inter.area == 0:
                continue
            rows.append({"cell_id": f"{zone_id}_g{cell_m}_{ix}_{iy}", "zone_id": zone_id,
                         "cell_area_m2": float(cell_m * cell_m),
                         "area_in_window_m2": float(inter.area), "geometry": inter})
    grid = gpd.GeoDataFrame(rows, geometry="geometry", crs=metric_crs)
    grid["coverage_fraction"] = grid["area_in_window_m2"] / grid["cell_area_m2"]
    return grid


def to_geojson_geom(geom_metric, metric_crs):
    g = gpd.GeoSeries([geom_metric], crs=metric_crs).to_crs("EPSG:4326").iloc[0]
    return mapping(g)


def make_record(*, feature_id, area_id, indicator_id, value, units, denominator, coverage_fraction,
                quality_flags, source_ids, acquired_at, run_id, geometry, evidence_type="derived"):
    """Canonical indicator feature record (handbook section 5). value=None means unknown."""
    return {
        "feature_id": feature_id, "area_id": area_id, "indicator_id": indicator_id,
        "value": None if value is None else float(value), "units": units,
        "denominator": None if denominator is None else float(denominator),
        "coverage_fraction": None if coverage_fraction is None else round(float(coverage_fraction), 4),
        "evidence_type": evidence_type, "quality_flags": sorted(set(quality_flags)),
        "source_ids": source_ids, "acquired_at": acquired_at,
        "method_version": METHOD_VERSION, "run_id": run_id, "geometry": geometry,
    }


BASE_FLAGS = ["osm_completeness_unverified"]
