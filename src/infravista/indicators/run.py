"""CLI: build P3 indicator records from a verified P2 package.

    python -m infravista.indicators.run --package <zip-or-folder> --config config/indicators.yml

Writes (never overwrites) data/processed/p3/<run_id>/ and manifests/runs/<run_id>.json.
Outputs are DERIVED evidence, not validated; P6 must review before any release.
"""
import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import geopandas as gpd
import yaml

from . import METHOD_VERSION, facilities, roads, water
from .common import BASE_FLAGS, make_grid, make_record, to_geojson_geom, window_polygon
from .io import load_package


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def git_rev():
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def cell_flags(cov, min_cov):
    f = list(BASE_FLAGS)
    if cov < 1.0:
        f.append("partial_cell_coverage")
    if cov < min_cov:
        f.append("small_denominator")
    return f


def run(package, config_path, out_root):
    cfg = yaml.safe_load(open(config_path, encoding="utf-8"))
    crs = cfg["processing_crs"]
    started = datetime.now(timezone.utc)
    run_id = started.strftime("%Y%m%dT%H%M%SZ") + "_indicators"
    out = Path(out_root) / run_id
    out.mkdir(parents=True, exist_ok=False)          # refuse to overwrite a published run

    catalog, layers = load_package(package)
    cat = {r["layer_id"]: r for r in catalog["layers"]}
    grid_recs, window_recs, warnings, indicator_ids = [], [], [], set()

    for zone, c in cfg["zones"].items():
        win = window_polygon(c["lat"], c["lon"], cfg["radius_m"], crs)
        win_km2 = win.area / 1e6
        grid = make_grid(win, cfg["grid_cell_m"], zone, crs)
        gi = grid.set_index("cell_id")
        win_geo = to_geojson_geom(win, crs)
        cov_all = 1.0

        def metric(lid):
            return layers[lid].to_crs(crs)

        # ---- roads -------------------------------------------------------------------------
        rid = f"roads_{zone}"
        r_m = metric(rid)
        r_src, r_date = cat[rid]["source_ids"], cat[rid]["acquired_at"]
        per_group = roads.length_by_group(r_m, cfg["road_groups"])
        for grp, length in per_group.items():
            iid = f"road_density_km_per_km2_{grp}"
            indicator_ids.add(iid)
            window_recs.append(make_record(
                feature_id=f"{zone}_window_{iid}", area_id=zone, indicator_id=iid,
                value=length / 1000 / win_km2, units="km/km2", denominator=win_km2,
                coverage_fraction=cov_all, quality_flags=BASE_FLAGS + ["centreline_length_not_lane_km"],
                source_ids=r_src, acquired_at=r_date, run_id=run_id, geometry=win_geo))
        rc = roads.length_by_cell(r_m, grid, cfg["road_groups"])
        for cell_id, row in gi.iterrows():
            geo = to_geojson_geom(row.geometry, crs)
            for grp in list(cfg["road_groups"]) + [roads.OTHER]:
                length = float(rc.get((cell_id, grp), 0.0))
                area_km2 = row.area_in_window_m2 / 1e6
                iid = f"road_density_km_per_km2_{grp}"
                fl = cell_flags(row.coverage_fraction, cfg["min_coverage_for_density"])
                if length == 0:
                    fl.append("none_mapped_not_confirmed_absent")
                grid_recs.append(make_record(
                    feature_id=f"{cell_id}_{iid}", area_id=zone, indicator_id=iid,
                    value=length / 1000 / area_km2, units="km/km2", denominator=area_km2,
                    coverage_fraction=row.coverage_fraction, quality_flags=fl,
                    source_ids=r_src, acquired_at=r_date, run_id=run_id, geometry=geo))

        # ---- facilities --------------------------------------------------------------------
        fp = facilities.categorize(metric(f"facilities_points_{zone}"), cfg["facility_categories"])
        fg = facilities.categorize(metric(f"facilities_polygons_{zone}"), cfg["facility_categories"])
        reps, st = facilities.dedupe(fp, fg, cfg["facility_dedupe"])
        warnings.append(f"{zone} facility dedupe: {st}")
        f_src = cat[f"facilities_points_{zone}"]["source_ids"]
        f_date = cat[f"facilities_points_{zone}"]["acquired_at"]
        tot = facilities.counts_by_category(reps, cfg["facility_categories"])
        for ccat, n in tot.items():
            iid = f"facility_count_{ccat}"
            indicator_ids.add(iid)
            window_recs.append(make_record(
                feature_id=f"{zone}_window_{iid}", area_id=zone, indicator_id=iid, value=n,
                units="count", denominator=None, coverage_fraction=cov_all,
                quality_flags=BASE_FLAGS + ["point_polygon_dedupe_assumption", "count_not_complete_inventory"],
                source_ids=f_src, acquired_at=f_date, run_id=run_id, geometry=win_geo))
        fc = facilities.counts_by_cell(reps, grid)
        for cell_id, row in gi.iterrows():
            geo = to_geojson_geom(row.geometry, crs)
            for ccat in cfg["facility_categories"]:
                n = int(fc.get((cell_id, ccat), 0))
                fl = cell_flags(row.coverage_fraction, cfg["min_coverage_for_density"]) + ["point_polygon_dedupe_assumption"]
                if n == 0:
                    fl.append("none_mapped_not_confirmed_absent")
                grid_recs.append(make_record(
                    feature_id=f"{cell_id}_facility_count_{ccat}", area_id=zone,
                    indicator_id=f"facility_count_{ccat}", value=n, units="count", denominator=None,
                    coverage_fraction=row.coverage_fraction, quality_flags=fl,
                    source_ids=f_src, acquired_at=f_date, run_id=run_id, geometry=geo))

        # ---- water -------------------------------------------------------------------------
        wl, wp = metric(f"water_lines_{zone}"), metric(f"water_polygons_{zone}")
        w_src, w_date = cat[f"water_lines_{zone}"]["source_ids"], cat[f"water_lines_{zone}"]["acquired_at"]
        wflags = BASE_FLAGS + ["storm_drains_often_unmapped"]
        for wtype, length in water.waterway_length_by_type(wl).items():
            iid = f"waterway_density_km_per_km2_{wtype}"
            indicator_ids.add(iid)
            window_recs.append(make_record(
                feature_id=f"{zone}_window_{iid}", area_id=zone, indicator_id=iid,
                value=length / 1000 / win_km2, units="km/km2", denominator=win_km2,
                coverage_fraction=cov_all, quality_flags=wflags, source_ids=w_src,
                acquired_at=w_date, run_id=run_id, geometry=win_geo))
        u_area = water.water_union(wp).area if len(wp) else 0.0
        indicator_ids.add("water_area_share")
        window_recs.append(make_record(
            feature_id=f"{zone}_window_water_area_share", area_id=zone, indicator_id="water_area_share",
            value=u_area / win.area, units="fraction", denominator=win.area, coverage_fraction=cov_all,
            quality_flags=wflags, source_ids=w_src, acquired_at=w_date, run_id=run_id, geometry=win_geo))
        wa = water.water_area_by_cell(wp, grid)
        wlc = water.waterway_length_by_cell(wl, grid)
        wlc_by_type = water.waterway_length_by_type_by_cell(wl, grid)
        waterway_types = sorted(wl["waterway"].dropna().astype(str).unique())

        for wtype in waterway_types:
            indicator_ids.add(f"waterway_density_km_per_km2_{wtype}")

        indicator_ids.add("waterway_density_km_per_km2_all")

        for cell_id, row in gi.iterrows():
            geo = to_geojson_geom(row.geometry, crs)
            fl = cell_flags(row.coverage_fraction, cfg["min_coverage_for_density"]) + ["storm_drains_often_unmapped"]
            grid_recs.append(make_record(
                feature_id=f"{cell_id}_water_area_share", area_id=zone, indicator_id="water_area_share",
                value=float(wa.get(cell_id, 0.0)) / row.area_in_window_m2, units="fraction",
                denominator=row.area_in_window_m2, coverage_fraction=row.coverage_fraction,
                quality_flags=fl, source_ids=w_src, acquired_at=w_date, run_id=run_id, geometry=geo))
            area_km2 = row.area_in_window_m2 / 1e6
            grid_recs.append(make_record(
                feature_id=f"{cell_id}_waterway_density_km_per_km2_all", area_id=zone,
                indicator_id="waterway_density_km_per_km2_all",
                value=float(wlc.get(cell_id, 0.0)) / 1000 / area_km2, units="km/km2",
                denominator=area_km2, coverage_fraction=row.coverage_fraction, quality_flags=fl,
                source_ids=w_src, acquired_at=w_date, run_id=run_id, geometry=geo))

            for wtype in waterway_types:
                iid = f"waterway_density_km_per_km2_{wtype}"
                length_m = float(wlc_by_type.get((cell_id, wtype), 0.0))
                type_flags = list(fl)
                if length_m == 0:
                    type_flags.append("none_mapped_not_confirmed_absent")
                grid_recs.append(make_record(
                    feature_id=f"{cell_id}_{iid}", area_id=zone, indicator_id=iid,
                    value=length_m / 1000 / area_km2, units="km/km2",
                    denominator=area_km2, coverage_fraction=row.coverage_fraction,
                    quality_flags=type_flags, source_ids=w_src, acquired_at=w_date,
                    run_id=run_id, geometry=geo))

    # ---- write outputs ---------------------------------------------------------------------
    def to_feature(rec):
        props = {k: v for k, v in rec.items() if k != "geometry"}
        props["quality_flags"] = ";".join(rec["quality_flags"])       # same convention as P2 GeoJSON
        props["source_ids"] = ";".join(rec["source_ids"])
        return {"type": "Feature", "properties": props, "geometry": rec["geometry"]}

    for name, recs in (("indicators_grid", grid_recs), ("indicators_window", window_recs)):
        fc = {"type": "FeatureCollection", "features": [to_feature(r) for r in recs]}
        (out / f"{name}.geojson").write_text(json.dumps(fc), encoding="utf-8")

    manifest = {
        "run_id": run_id, "started_at": started.isoformat(),
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "method_version": METHOD_VERSION, "git_commit": git_rev(),
        "config_id": cfg["config_id"], "config_hash": sha256_file(config_path),
        "input_package": str(package), "input_run_id": catalog["run_id"],
        "input_layer_sha256": {r["layer_id"]: r["sha256"] for r in catalog["layers"]},
        "processing_crs": crs, "processing_crs_status": "proposed, not approved",
        "boundary_version": cfg["boundary_version"],
        "evidence_type": "derived", "validation_status": "not validated (P6 independent review pending)",
        "rights_status": "review_required (inherits OSM/ODbL status from P2); team use only",
        "indicator_ids": sorted(indicator_ids),
        "outputs": {f.name: sha256_file(f) for f in sorted(out.glob("*.geojson"))},
        "warnings": warnings,
    }
    mpath = Path("manifests/runs") / f"{run_id}.json"
    mpath.parent.mkdir(parents=True, exist_ok=True)
    mpath.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"run {run_id}: {len(grid_recs)} grid records, {len(window_recs)} window records -> {out}")
    return run_id


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--package", required=True)
    ap.add_argument("--config", default="config/indicators.yml")
    ap.add_argument("--out-root", default="data/processed/p3")
    a = ap.parse_args(argv)
    run(a.package, a.config, a.out_root)


if __name__ == "__main__":
    main()
