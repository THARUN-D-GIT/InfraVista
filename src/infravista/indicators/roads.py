"""Road length by configurable class group. Inputs must already be in the metric CRS."""
import geopandas as gpd
import pandas as pd

OTHER = "other_unmapped_class"


def classify(highway, groups):
    for name, values in groups.items():
        if highway in values:
            return name
    return OTHER


def prepare_roads(roads_m, groups):
    r = roads_m[roads_m.geom_type.isin(["LineString", "MultiLineString"])].copy()
    r["road_group"] = r["highway"].apply(lambda h: classify(h, groups))
    return r[["feature_id", "highway", "road_group", "geometry"]]


def length_by_group(roads_m, groups):
    r = prepare_roads(roads_m, groups)
    out = r.assign(length_m=r.length).groupby("road_group")["length_m"].sum()
    return out.reindex(list(groups) + [OTHER]).fillna(0.0)


def length_by_cell(roads_m, grid, groups):
    """Return DataFrame indexed by (cell_id, road_group) with length_m (only non-empty pairs)."""
    r = prepare_roads(roads_m, groups)
    cut = gpd.overlay(r, grid[["cell_id", "geometry"]], how="intersection", keep_geom_type=True)
    cut["length_m"] = cut.length
    return cut.groupby(["cell_id", "road_group"])["length_m"].sum()
