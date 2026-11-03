"""Download OSM roads, water and facilities for the two InfraVista study zones.

Raw files are written once to data/raw/ and never overwritten.
A run record with checksums is written to manifests/runs/.
"""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import geopandas as gpd
import osmnx as ox
from shapely.geometry import Point

ROOT = Path(__file__).resolve().parents[3]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
RUNS = ROOT / "manifests" / "runs"
CACHE = ROOT / "data" / "interim" / "osmnx_cache"

PROJECTED_CRS = "EPSG:32643"
RADIUS_M = 2500
# zone_id: (latitude, longitude) approximate centers. Verify on openstreetmap.org
ZONES = {
    "hsr": (12.9116, 77.6389),
    "whitefield": (12.9698, 77.7500),
}
# source_id: OSM tags to request
LAYERS = {
    "osm_roads_2026_11": {"highway": True},
    "osm_water_2026_11": {"natural": "water", "waterway": True},
    "osm_facilities_2026_11": {
        "amenity": ["hospital", "clinic", "school", "college"],
        "public_transport": True,
    },
}


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def build_study_windows() -> gpd.GeoDataFrame:
    """2.5 km radius circles, buffered in a metric CRS (never in degrees)."""
    out = PROCESSED / "boundary_pilot_v1.gpkg"
    if out.exists():
        print(f"Study windows already exist, reusing: {out}")
        return gpd.read_file(out)
    rows = []
    for zone_id, (lat, lon) in ZONES.items():
        pt = gpd.GeoSeries([Point(lon, lat)], crs="EPSG:4326").to_crs(PROJECTED_CRS)
        circle = pt.buffer(RADIUS_M).iloc[0]
        rows.append({"zone_id": zone_id, "radius_m": RADIUS_M,
                     "boundary_version": "boundary_pilot_v1", "geometry": circle})
    gdf = gpd.GeoDataFrame(rows, crs=PROJECTED_CRS)
    gdf["area_m2"] = gdf.geometry.area
    gdf.to_file(out, driver="GPKG", layer="study_windows")
    print(f"Created study windows: {out}")
    return gdf


def flatten_columns(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """GeoPackage cannot store list values; convert them to text."""
    for col in gdf.columns:
        if col == gdf.geometry.name:
            continue
        if gdf[col].dtype == object:
            gdf[col] = gdf[col].apply(
                lambda v: v if v is None or isinstance(v, (str, int, float)) else str(v)
            )
    return gdf


def main() -> None:
    for d in (RAW, PROCESSED, RUNS, CACHE):
        d.mkdir(parents=True, exist_ok=True)
    ox.settings.use_cache = True
    ox.settings.cache_folder = str(CACHE)
    ox.settings.requests_timeout = 180

    started = datetime.now(timezone.utc)
    windows = build_study_windows()
    windows_4326 = windows.to_crs("EPSG:4326")
    records, warnings = [], []

    for _, w in windows_4326.iterrows():
        zone_id = w["zone_id"]
        for source_id, tags in LAYERS.items():
            out = RAW / f"{source_id}_{zone_id}.gpkg"
            if out.exists():
                print(f"SKIP (raw is immutable, already exists): {out.name}")
                warnings.append(f"{out.name} already existed; not overwritten")
                continue
            print(f"Downloading {source_id} for {zone_id} ...")
            accessed_at = datetime.now(timezone.utc).isoformat()
            try:
                gdf = ox.features_from_polygon(w.geometry, tags)
            except Exception as e:  # no features or network problem
                msg = f"{source_id}/{zone_id}: no data saved ({type(e).__name__}: {e})"
                print("WARNING:", msg)
                warnings.append(msg)
                continue
            gdf = flatten_columns(gdf.reset_index())
            gdf.to_file(out, driver="GPKG", layer=source_id)
            records.append({
                "source_id": source_id,
                "zone_id": zone_id,
                "file": str(out.relative_to(ROOT)),
                "accessed_at": accessed_at,
                "feature_count": int(len(gdf)),
                "geometry_types": gdf.geometry.geom_type.value_counts().to_dict(),
                "crs": str(gdf.crs),
                "checksum_sha256": sha256_of(out),
                "osm_tags_requested": tags,
            })
            print(f"  saved {len(gdf)} features -> {out.name}")

    run_id = started.strftime("%Y%m%dT%H%M%SZ") + "_download"
    manifest = {
        "run_id": run_id,
        "started_at": started.isoformat(),
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "osmnx_version": ox.__version__,
        "processing_crs": PROJECTED_CRS,
        "boundary_version": "boundary_pilot_v1",
        "boundary_checksum_sha256": sha256_of(PROCESSED / "boundary_pilot_v1.gpkg"),
        "outputs": records,
        "warnings": warnings,
    }
    with open(RUNS / f"{run_id}.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    print(f"\nRun record written: manifests/runs/{run_id}.json")


if __name__ == "__main__":
    main()