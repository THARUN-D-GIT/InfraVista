"""P2 normalization: clip raw OSM layers to zone circles, split by geometry
family, add provenance. Reads data/raw (never modified); writes a new run folder."""
import datetime as dt
import hashlib
import json
import subprocess
from pathlib import Path

import geopandas as gpd
from shapely.geometry import MultiLineString, MultiPoint, MultiPolygon

RAW = Path("data/raw")
PROCESSED = Path("data/processed")
INTERIM = Path("data/interim")
BOUNDARY = PROCESSED / "boundary_pilot_v1.gpkg"
RUNS = Path("manifests/runs")
PROCESSING_CRS = "EPSG:32643"  # PROPOSAL, not approved by P1/P3/P4

# Where each geometry family goes. None = quarantine (not released downstream).
LAYERS = {
    "osm_roads_2026_11": {"line": "roads", "point": "road_nodes", "polygon": None},
    "osm_water_2026_11": {"line": "water_lines", "polygon": "water_polygons", "point": None},
    "osm_facilities_2026_11": {"point": "facilities_points", "polygon": "facilities_polygons", "line": None},
}

# Candidate tag columns; only those present in a file are kept.
KEEP_COLUMNS = [
    "name", "highway", "railway", "public_transport", "amenity", "healthcare",
    "leisure", "natural", "waterway", "water", "landuse", "building", "office",
    "shop", "operator", "surface", "lanes", "oneway", "bridge", "tunnel",
    "maxspeed", "access",
]

BASE = {"LineString": "line", "Point": "point", "Polygon": "polygon"}
MULTI = {"line": MultiLineString, "point": MultiPoint, "polygon": MultiPolygon}


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def family_of(geom_type):
    return BASE.get(geom_type.replace("Multi", ""))


def to_family(geom, family):
    """Keep only parts of the wanted family (clipping can yield stray points/lines)."""
    if geom is None or geom.is_empty:
        return None
    if geom.geom_type == "GeometryCollection":
        flat = []
        for part in geom.geoms:
            if family_of(part.geom_type) == family:
                flat.extend(part.geoms if part.geom_type.startswith("Multi") else [part])
        if not flat:
            return None
        return flat[0] if len(flat) == 1 else MULTI[family](flat)
    return geom if family_of(geom.geom_type) == family else None


def measure(gdf, family):
    m = {"count": int(len(gdf))}
    if family == "line":
        m["length_km"] = round(float(gdf.length.sum()) / 1000, 3)
    elif family == "polygon":
        m["area_km2"] = round(float(gdf.area.sum()) / 1e6, 4)
    return m


def load_raw_index():
    idx, boundary_hash = {}, None
    for r in sorted(RUNS.glob("*_download.json")):
        data = json.loads(r.read_text(encoding="utf-8"))
        boundary_hash = data.get("boundary_checksum_sha256", boundary_hash)
        for o in data.get("outputs", []):
            name = Path(o["file"].replace("\\", "/")).name
            idx[name] = {"run_id": data["run_id"], "accessed_at": o["accessed_at"],
                         "checksum_sha256": o["checksum_sha256"].lower()}
    return idx, boundary_hash


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
    run_id = started.strftime("%Y%m%dT%H%M%SZ") + "_normalize"
    out_dir = PROCESSED / run_id
    q_dir = INTERIM / "quarantine" / run_id
    out_dir.mkdir(parents=True)
    warnings, outputs = [], []

    raw_index, rec_boundary_hash = load_raw_index()
    b_hash = sha256(BOUNDARY)
    if rec_boundary_hash and b_hash != rec_boundary_hash:
        warnings.append("boundary file checksum differs from the download run record")
    boundary = gpd.read_file(BOUNDARY).to_crs(PROCESSING_CRS)
    rev, dirty = git_info()
    if dirty:
        warnings.append("git working tree had uncommitted changes at run time")

    for source_id, mapping in LAYERS.items():
        for zone, circle in zip(boundary["zone_id"], boundary.geometry):
            name = f"{source_id}_{zone}.gpkg"
            rec = raw_index.get(name)
            if rec is None:
                warnings.append(f"{name}: no run record; skipped")
                continue
            raw_hash = sha256(RAW / name)
            if raw_hash != rec["checksum_sha256"]:
                raise SystemExit(f"STOP: {name} does not match its recorded checksum")

            gdf = gpd.read_file(RAW / name).to_crs(PROCESSING_CRS)
            fam = gdf.geometry.map(lambda g: family_of(g.geom_type))
            for family in sorted(f for f in fam.unique() if f):
                sub = gdf[fam == family]
                pre = measure(sub, family)
                target = mapping.get(family)

                if target is None:  # quarantine: written unclipped, not released
                    q_dir.mkdir(parents=True, exist_ok=True)
                    qpath = q_dir / f"{source_id}_{zone}_{family}.gpkg"
                    sub.to_file(qpath, driver="GPKG", layer=qpath.stem)
                    warnings.append(f"{name}: {pre['count']} {family} feature(s) quarantined")
                    outputs.append({"destination": "quarantine", "file": str(qpath),
                                    "source_id": source_id, "zone_id": zone,
                                    "geometry_family": family, "pre_clip": pre,
                                    "sha256": sha256(qpath)})
                    continue

                clipped = sub.geometry.intersection(circle)
                geoms = [to_family(g, family) for g in clipped]
                keep = [g is not None for g in geoms]
                out = sub.loc[keep].copy()
                inside = sub.geometry[keep].within(circle).to_numpy()
                gname = out.geometry.name
                out[gname] = gpd.GeoSeries([g for g in geoms if g is not None],
                                           index=out.index, crs=PROCESSING_CRS)
                out["clipped_at_boundary"] = ~inside
                out["feature_id"] = out["element"].astype(str) + "/" + out["id"].astype(str)
                out["source_id"] = source_id
                out["zone_id"] = zone
                out["accessed_at"] = rec["accessed_at"]
                out["run_id"] = run_id
                out["raw_file"] = name
                out["boundary_version"] = "boundary_pilot_v1"
                out["evidence_type"] = "observed"
                out["quality_flags"] = [
                    "clipped_at_boundary;osm_completeness_unverified" if c
                    else "osm_completeness_unverified" for c in out["clipped_at_boundary"]]
                cols = (["feature_id", "element", "id", "source_id", "zone_id", "evidence_type",
                         "accessed_at", "run_id", "raw_file", "boundary_version",
                         "clipped_at_boundary", "quality_flags"]
                        + [c for c in KEEP_COLUMNS if c in out.columns] + [gname])
                out = gpd.GeoDataFrame(out[cols], geometry=gname, crs=PROCESSING_CRS)

                post = measure(out, family)
                if post["count"] == 0:
                    warnings.append(f"{target}_{zone}: zero features after clipping (unknown, not absent)")
                    continue
                path = out_dir / f"{target}_{zone}.gpkg"
                out.to_file(path, driver="GPKG", layer=f"{target}_{zone}")
                outputs.append({"destination": "processed", "file": str(path),
                                "layer": f"{target}_{zone}", "source_id": source_id,
                                "zone_id": zone, "geometry_family": family,
                                "raw_file": name, "raw_sha256": raw_hash,
                                "pre_clip": pre, "post_clip": post,
                                "clipped_features": int(out["clipped_at_boundary"].sum()),
                                "invalid_after_clip": int((~out.geometry.is_valid).sum()),
                                "sha256": sha256(path)})

    completed = dt.datetime.now(dt.timezone.utc)
    record = {
        "run_id": run_id,
        "started_at": started.isoformat(), "completed_at": completed.isoformat(),
        "code_revision": rev, "git_dirty": dirty,
        "processing_crs": PROCESSING_CRS, "crs_status": "proposed, not approved",
        "boundary_version": "boundary_pilot_v1", "boundary_checksum_sha256": b_hash,
        "method": "clip to zone circle; split by geometry family; LineString-only roads",
        "outputs": outputs, "warnings": warnings,
        "rights_status": "review_required (ODbL; no legal review done)",
    }
    rp = RUNS / f"{run_id}.json"
    rp.write_text(json.dumps(record, indent=2, default=str), encoding="utf-8")

    print(f"\nRun: {run_id}   code_revision: {rev}   dirty: {dirty}")
    print(f"{'zone':11} {'layer':22} {'dest':10} {'pre':>16} {'post':>16} clipped")
    for o in outputs:
        pre, post = o["pre_clip"], o.get("post_clip", {})
        key = "length_km" if "length_km" in pre else ("area_km2" if "area_km2" in pre else "count")
        label = o.get("layer", o["source_id"] + "/" + o["geometry_family"])
        print(f"{o['zone_id']:11} {label:22} {o['destination']:10} "
              f"{str(pre.get(key)):>16} {str(post.get(key, '-')):>16} {o.get('clipped_features', '-')}"
              f"   [{key}]")
    for w in warnings:
        print("WARNING:", w)
    print(f"\nProcessed -> {out_dir}\nRecord    -> {rp}")


if __name__ == "__main__":
    main()
