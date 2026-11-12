import os
import json
from pathlib import Path
from urllib.parse import urlparse

import boto3
import rasterio

manifest_path = Path(
    "reports/p4_historical_growth/sentinel2_asset_manifest.json"
)

with manifest_path.open(encoding="utf-8") as f:
    manifest = json.load(f)

product = next(
    p for p in manifest["products"]
    if p["study_area"] == "hsr"
    and p["date"] == "2025-02-06"
)

asset = product["assets"]["SCL_20m"]

if not asset["available"] or not asset.get("href"):
    raise RuntimeError("2025 HSR SCL asset is unavailable")

href = asset["href"]
parsed = urlparse(href)

bucket = parsed.netloc
key = parsed.path.lstrip("/")

output = Path(
    "data/raw/historical_sentinel2/2025-02-06/hsr/SCL_20m.jp2"
)
output.parent.mkdir(parents=True, exist_ok=True)

s3 = boto3.client(
    "s3",
    endpoint_url="https://eodata.dataspace.copernicus.eu",
    aws_access_key_id=os.environ["CDSE_S3_ACCESS_KEY"],
    aws_secret_access_key=os.environ["CDSE_S3_SECRET_KEY"],
    region_name="default"
)

print("Checking remote asset...")
head = s3.head_object(Bucket=bucket, Key=key)
print("Remote size:", head["ContentLength"], "bytes")

if not output.exists() or output.stat().st_size != head["ContentLength"]:
    print("Downloading 2025 HSR SCL raster...")
    s3.download_file(bucket, key, str(output))
else:
    print("Existing file has matching size; skipping download.")

print("Local file:", output)
print("Local size:", output.stat().st_size, "bytes")

print("\nInspecting raster metadata...")

with rasterio.open(output) as src:
    metadata = {
        "product_id": product["product_id"],
        "study_area": product["study_area"],
        "date": product["date"],
        "asset": "SCL_20m",
        "driver": src.driver,
        "width": src.width,
        "height": src.height,
        "count": src.count,
        "crs": str(src.crs),
        "resolution": list(src.res),
        "bounds": list(src.bounds),
        "dtype": list(src.dtypes),
        "nodata": src.nodata,
        "file_size_bytes": output.stat().st_size,
    }

    print(json.dumps(metadata, indent=2))

report_path = Path(
    "reports/p4_historical_growth/sentinel2_raster_metadata_2025_hsr.json"
)
report_path.parent.mkdir(parents=True, exist_ok=True)
report_path.write_text(
    json.dumps(metadata, indent=2),
    encoding="utf-8"
)

print("\nMetadata report saved:", report_path)
print("2025 HSR SCL DOWNLOAD AND INSPECTION: SUCCESS")
