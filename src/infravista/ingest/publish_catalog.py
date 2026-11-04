"""P2 publish: reproject normalized layers to EPSG:4326 GeoJSON and write a layer catalog.
Reads a normalize run (never modified); writes a new *_publish run folder."""
import datetime as dt
import hashlib
import json
import subprocess
from pathlib import Path

import geopandas as gpd

PROCESSED = Path("data/processed")
RUNS = Path("manifests/runs")
CATALOG_DIR = Path("manifests/catalog")

TITLES = {
    "roads": "Roads (OSM highway ways)",
    "road_nodes": "Tagged road-side points (street lamps, crossings, bus stops, signals)",
    "water_lines": "Water lines (OSM waterway)",
    "water_polygons": "Water polygons (OSM natural=water)",
    "facilities_points": "Facilities and public transport (points)",
    "facilities_polygons": "Facilities and public transport (polygons)",
}
GEOM = {"line": "LineString", "point": "Point", "polygon": "Polygon"}
COMMON_LIMITS = [
    "OpenStreetMap is volunteer mapped; completeness is unverified. A missing feature means unknown, not absent.",
    "Geometries are clipped to a 2.5 km circle; clipped_at_boundary marks features cut at the edge.",
    "No observation date captured; acquired_at is the download date.",
    "Rights not cleared: ODbL, review_required. Team use only, do not publish.",
]
EXTRA_LIMITS = {
    "roads": ["Includes construction, proposed, footway, path, steps and service ways; filter on highway. P3 decides which classes count."],
    "road_nodes": ["Tagged points along roads, not network intersections or vertices; not suitable for connectivity analysis."],
}
EXTRA_FLAGS = {
    "roads": ["includes_non_existing_status_classes"],
    "road_nodes": ["not_network_nodes"],
}
LICENSE_URL = "https://www.openstreetmap.org/copyright"
ATTRIBUTION = "\u00a9 OpenStreetMap contributors"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def git_info():
    try:
        rev = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True,
                             text=True, check=True).stdout.strip()
        dirty = bool(subprocess.run(["git", "status", "--porcelain"], capture_output=True,
                                    text=True, check=True).stdout.strip())
        return rev, dirty
    except Exception:
        return None, None


def main():
    started = dt.datetime.now(dt.timezone.utc)
    run_id = started.strftime("%Y%m%dT%H%M%SZ") + "_publish"
    src_path = sorted(RUNS.glob("*_normalize.json"))[-1]
    src = json.loads(src_path.read_text(encoding="utf-8"))
    out_dir = PROCESSED / run_id
    out_dir.mkdir(parents=True)
    CATALOG_DIR.mkdir(parents=True, exist_ok=True)
    rev, dirty = git_info()
    warnings, layers = [], []

    for o in src["outputs"]:
        if o["destination"] != "processed":
            continue
        zone = o["zone_id"]
        base = o["layer"][: -(len(zone) + 1)]
        gdf = gpd.read_file(o["file"])
        if sha256(o["file"]) != o["sha256"]:
            raise SystemExit(f"STOP: {o['file']} does not match the normalize run record")
        accessed = str(gdf["accessed_at"].iloc[0])[:10]
        for col in gdf.columns:
            if col != gdf.geometry.name and str(gdf[col].dtype).startswith("datetime"):
                gdf[col] = gdf[col].astype(str)
        gdf["accessed_at"] = gdf["accessed_at"].astype(str)
        g4326 = gdf.to_crs(4326)
        path = out_dir / f"{o['layer']}.geojson"
        g4326.to_file(path, driver="GeoJSON")

        back = gpd.read_file(path)
        minx, miny, maxx, maxy = [float(v) for v in g4326.total_bounds]
        checks = {
            "count_matches": len(back) == len(gdf),
            "crs": back.crs.to_string(),
            "invalid": int((~back.geometry.is_valid).sum()),
            "bbox_plausible": 77.0 < minx < 78.2 and 12.5 < miny < 13.5 and 77.0 < maxx < 78.2 and 12.5 < maxy < 13.5,
        }
        if not (checks["count_matches"] and checks["invalid"] == 0 and checks["bbox_plausible"]):
            warnings.append(f"{o['layer']}: check failed {checks}")

        layers.append({
            "layer_id": o["layer"],
            "title": f"{TITLES[base]} - {zone}",
            "zone_id": zone,
            "evidence_type": "observed",
            "geometry_type": GEOM[o["geometry_family"]],
            "feature_count": int(len(back)),
            "source_ids": [o["source_id"]],
            "acquired_at": accessed,
            "crs": "EPSG:4326",
            "processing_crs": src["processing_crs"],
            "processing_crs_status": src["crs_status"],
            "bbox_4326": [round(minx, 6), round(miny, 6), round(maxx, 6), round(maxy, 6)],
            "units": "meters in processing CRS; degrees in this file",
            "method_version": f"normalize.py@{src['code_revision']}",
            "license_url": LICENSE_URL,
            "attribution": ATTRIBUTION,
            "rights_status": "review_required",
            "quality_flags": ["osm_completeness_unverified", "clipped_at_boundary_possible"] + EXTRA_FLAGS.get(base, []),
            "limitations": COMMON_LIMITS + EXTRA_LIMITS.get(base, []),
            "boundary_version": src["boundary_version"],
            "run_id": run_id,
            "normalize_run_id": src["run_id"],
            "data_url": str(path).replace("\\", "/"),
            "sha256": sha256(path),
            "checks": checks,
            "note": "quality_flags inside the GeoJSON features is a semicolon-separated string; this catalog uses a list.",
        })

    catalog = {"run_id": run_id, "created_at": started.isoformat(), "layers": layers}
    (out_dir / "layer_catalog.json").write_text(json.dumps(catalog, indent=2), encoding="utf-8")
    (CATALOG_DIR / f"{run_id}_layer_catalog.json").write_text(json.dumps(catalog, indent=2), encoding="utf-8")

    completed = dt.datetime.now(dt.timezone.utc)
    if dirty:
        warnings.append("git working tree had uncommitted changes at run time")
    record = {
        "run_id": run_id, "started_at": started.isoformat(), "completed_at": completed.isoformat(),
        "code_revision": rev, "git_dirty": dirty, "input_run": src["run_id"],
        "method": "reproject normalized layers to EPSG:4326, write GeoJSON and layer catalog",
        "outputs": [{"file": l["data_url"], "sha256": l["sha256"], "feature_count": l["feature_count"]} for l in layers],
        "warnings": warnings, "rights_status": "review_required (ODbL; no legal review done)",
    }
    (RUNS / f"{run_id}.json").write_text(json.dumps(record, indent=2), encoding="utf-8")

    print(f"Run: {run_id}  input: {src['run_id']}  code_revision: {rev}  dirty: {dirty}")
    for l in layers:
        c = l["checks"]
        print(f"{l['layer_id']:32} {l['feature_count']:6} {c['crs']} invalid={c['invalid']} count_ok={c['count_matches']} bbox_ok={c['bbox_plausible']}")
    for w in warnings:
        print("WARNING:", w)
    print(f"Output -> {out_dir}")


if __name__ == "__main__":
    main()
