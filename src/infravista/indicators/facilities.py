"""Facility counts by category with a transparent point/polygon de-duplication rule."""
import geopandas as gpd
import pandas as pd


def categorize(gdf, categories):
    """First matching (key, value) in config order wins; others get None."""
    def one(row):
        for cat, (key, val) in categories.items():
            if row.get(key) == val:
                return cat
        return None
    g = gdf.copy()
    g["category"] = g.apply(one, axis=1)
    return g[g["category"].notna()]


def dedupe(points_m, polys_m, cfg):
    """A polygon absorbs same-category POINTS within tolerance_m of it (counted once, as the polygon).
    Returns (representatives GeoDataFrame, stats dict). ASSUMPTION: needs P1/P6 approval."""
    cats = set(cfg["categories"])
    tol = float(cfg["tolerance_m"])
    pts, polys = points_m.copy(), polys_m.copy()
    drop_ids = set()
    pp = polys[polys["category"].isin(cats)][["feature_id", "category", "geometry"]].copy()
    if len(pp) and len(pts):
        pp["geometry"] = pp.geometry.buffer(tol)
        j = gpd.sjoin(pts[pts["category"].isin(cats)][["feature_id", "category", "geometry"]],
                      pp, predicate="within", how="inner", lsuffix="pt", rsuffix="poly")
        j = j[j["category_pt"] == j["category_poly"]]
        drop_ids = set(j["feature_id_pt"])
    kept_pts = pts[~pts["feature_id"].isin(drop_ids)][["feature_id", "category", "geometry"]]
    polys_rep = polys[["feature_id", "category"]].copy()
    polys_rep["geometry"] = polys.geometry.representative_point()
    parts = [d for d in (kept_pts, polys_rep) if len(d)]
    if parts:
        reps = gpd.GeoDataFrame(pd.concat(parts, ignore_index=True), geometry="geometry",
                                crs=points_m.crs)
    else:
        reps = gpd.GeoDataFrame({"feature_id": [], "category": []}, geometry=[], crs=points_m.crs)
    stats = {"raw_points": int(len(pts)), "raw_polygons": int(len(polys)),
             "points_absorbed_by_polygon": int(len(drop_ids)),
             "deduplicated_total": int(len(reps))}
    return reps, stats


def counts_by_category(reps, categories):
    return reps.groupby("category").size().reindex(list(categories)).fillna(0).astype(int)


def counts_by_cell(reps, grid):
    points = reps[["category", "geometry"]].reset_index(drop=True).copy()
    points["_rep_id"] = range(len(points))

    joined = gpd.sjoin(
        points,
        grid[["cell_id", "geometry"]],
        predicate="intersects",
        how="left",
    )

    # Keep only points that intersect a grid cell.
    if joined["cell_id"].isna().any():
        raise ValueError("Some facility representatives do not intersect any grid cell.")

    # A point can intersect multiple cells on a boundary.
    # Assign it to the cell with the smallest cell_id.
    joined = (
        joined.sort_values(["_rep_id", "cell_id"], kind="stable")
        .drop_duplicates(subset="_rep_id", keep="first")
    )

    return joined.groupby(["cell_id", "category"]).size()