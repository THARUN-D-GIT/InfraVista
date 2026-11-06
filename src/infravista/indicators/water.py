"""Waterway length and water-polygon area share. Inputs in the metric CRS."""
import geopandas as gpd


def waterway_length_by_type(lines_m):
    return lines_m.assign(length_m=lines_m.length).groupby("waterway")["length_m"].sum()


def waterway_length_by_cell(lines_m, grid):
    cut = gpd.overlay(lines_m[["feature_id", "geometry"]], grid[["cell_id", "geometry"]],
                      how="intersection", keep_geom_type=True)
    cut["length_m"] = cut.length
    return cut.groupby("cell_id")["length_m"].sum()


def water_union(polys_m):
    """Union first so overlapping polygons are not double counted."""
    return polys_m.geometry.union_all() if hasattr(polys_m.geometry, "union_all") else polys_m.unary_union


def water_area_by_cell(polys_m, grid):
    if len(polys_m) == 0:
        return grid.set_index("cell_id")["cell_area_m2"] * 0
    u = water_union(polys_m)
    return grid.set_index("cell_id").geometry.intersection(u).area
