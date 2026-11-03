"""P2 preflight: read-only inspection of raw GeoPackages in data/raw."""
import json
import datetime as dt
from pathlib import Path

import geopandas as gpd

RAW = Path("data/raw")
OUT = Path("manifests/preflight")
# Rough Bengaluru plausibility box (lon/lat). Adjust if your zones differ.
BBOX = (77.3, 12.7, 77.9, 13.3)
# PROPOSAL only, not an approved pilot CRS (P1/P3/P4 must confirm).
PROPOSED_CRS = 32643  # WGS 84 / UTM zone 43N, meters


def inspect(path: Path) -> dict:
    r = {"file": path.name, "checks": {}, "warnings": []}
    try:
        gdf = gpd.read_file(path)
    except Exception as e:
        r["status"] = "NO-GO"
        r["warnings"].append(f"unreadable: {type(e).__name__}: {e}")
        return r

    n = len(gdf)
    r["checks"]["feature_count"] = n
    if n == 0:
        r["status"] = "NO-GO"
        r["warnings"].append("zero features: unknown, not confirmed absent")
        return r

    if gdf.crs is None:
        r["status"] = "NO-GO"
        r["warnings"].append("CRS missing")
        return r
    r["checks"]["crs"] = gdf.crs.to_string()

    geom = gdf.geometry
    r["checks"]["geometry_types"] = geom.geom_type.value_counts().to_dict()
    n_empty = int(geom.isna().sum() + geom.is_empty.sum())
    n_invalid = int((~geom.is_valid).sum())
    r["checks"]["empty_or_null_geometry"] = n_empty
    r["checks"]["invalid_geometry"] = n_invalid

    g4326 = gdf.to_crs(4326)
    minx, miny, maxx, maxy = g4326.total_bounds
    r["checks"]["bounds_4326"] = [round(float(v), 5) for v in (minx, miny, maxx, maxy)]
    outside = not (BBOX[0] <= minx and BBOX[1] <= miny and maxx <= BBOX[2] and maxy <= BBOX[3])
    r["checks"]["bounds_outside_plausible_box"] = bool(outside)

    id_cols = [c for c in ("element", "element_type", "id", "osmid") if c in gdf.columns]
    r["checks"]["id_columns_found"] = id_cols
    if id_cols:
        dup_ids = int(gdf.duplicated(subset=id_cols).sum())
    else:
        dup_ids = None
        r["warnings"].append("no OSM id column found; duplicate ID check skipped")
    r["checks"]["duplicate_ids"] = dup_ids
    r["checks"]["duplicate_geometries"] = int(geom.to_wkb().duplicated().sum())

    attrs = gdf.drop(columns=gdf.geometry.name)
    nulls = attrs.isna().mean().sort_values(ascending=False).head(8).round(3)
    r["checks"]["top_null_fractions"] = nulls.to_dict()
    r["checks"]["column_count"] = int(attrs.shape[1])

    proj = gdf.to_crs(PROPOSED_CRS)
    if proj.geom_type.isin(["LineString", "MultiLineString"]).all():
        r["checks"]["total_length_km"] = round(float(proj.length.sum()) / 1000, 2)
    if proj.geom_type.isin(["Polygon", "MultiPolygon"]).all():
        r["checks"]["total_area_km2"] = round(float(proj.area.sum()) / 1e6, 3)

    status = "PASS WITH LIMITATIONS"  # OSM completeness is never proven
    r["warnings"].append("OSM completeness unverified: absence of a feature is not absence on the ground")
    if n_invalid / n > 0.05 or (dup_ids or 0) > 0 or outside or n_empty > 0:
        status = "REVISE"
    r["status"] = status
    return r


def main():
    files = sorted(RAW.glob("*.gpkg"))
    if not files:
        raise SystemExit("No .gpkg files in data/raw")
    results = []
    for f in files:
        res = inspect(f)
        results.append(res)
        print(f"\n== {res['file']} -> {res['status']}")
        for k, v in res["checks"].items():
            print(f"  {k}: {v}")
        for w in res["warnings"]:
            print(f"  WARNING: {w}")

    OUT.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report = {
        "created_at": stamp,
        "proposed_crs_not_approved": PROPOSED_CRS,
        "rights_status": "review_required (ODbL; no legal review done)",
        "results": results,
    }
    p = OUT / f"preflight_{stamp}.json"
    p.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(f"\nReport written: {p}")


if __name__ == "__main__":
    main()
