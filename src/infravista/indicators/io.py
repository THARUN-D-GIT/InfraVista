"""Read the P2 handoff package (zip or unzipped folder) and verify checksums first."""
import hashlib
import io
import json
import zipfile
from pathlib import Path

import geopandas as gpd


def _norm(name: str) -> str:
    return name.replace("\\", "/").split("/")[-1]


def _read_bytes(path: Path):
    """Return (catalog_dict, {filename: bytes}). Handles Windows backslash zips."""
    if path.is_dir():
        files = {p.name: p.read_bytes() for p in path.rglob("*") if p.is_file()}
    else:
        z = zipfile.ZipFile(path)
        files = {_norm(n): z.read(n) for n in z.namelist() if not n.endswith("/")}
    return json.loads(files["layer_catalog.json"]), files


def split_flags(value):
    if value is None or value == "":
        return []
    return [v for v in str(value).split(";") if v]


def load_package(path):
    """Return (catalog, {layer_id: GeoDataFrame in EPSG:4326}). Refuses checksum mismatches."""
    path = Path(path)
    catalog, files = _read_bytes(path)
    layers = {}
    for rec in catalog["layers"]:
        raw = files[f"{rec['layer_id']}.geojson"]
        if hashlib.sha256(raw).hexdigest() != rec["sha256"]:
            raise ValueError(f"checksum mismatch for {rec['layer_id']}: do not use this package")
        gdf = gpd.read_file(io.BytesIO(raw))
        if len(gdf) != rec["feature_count"]:
            raise ValueError(f"feature count mismatch for {rec['layer_id']}")
        gdf["flags_list"] = gdf["quality_flags"].apply(split_flags)
        layers[rec["layer_id"]] = gdf
    return catalog, layers
