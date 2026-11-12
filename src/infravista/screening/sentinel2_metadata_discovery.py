import os
import json
from pathlib import Path
from urllib.parse import urlparse

import boto3

manifest_path = Path(
    "reports/p4_historical_growth/sentinel2_asset_manifest.json"
)

with manifest_path.open(encoding="utf-8") as f:
    manifest = json.load(f)

s3 = boto3.client(
    "s3",
    endpoint_url="https://eodata.dataspace.copernicus.eu",
    aws_access_key_id=os.environ["CDSE_S3_ACCESS_KEY"],
    aws_secret_access_key=os.environ["CDSE_S3_SECRET_KEY"],
    region_name="default"
)

for date in ["2017-02-03", "2025-02-06"]:
    product = next(
        p for p in manifest["products"]
        if p["study_area"] == "hsr" and p["date"] == date
    )

    href = product["assets"]["B04_20m"]["href"]
    parsed = urlparse(href)

    bucket = parsed.netloc
    key = parsed.path.lstrip("/")

    print(f"\nDATE: {date}")
    print("PRODUCT:", product["product_id"])
    print("BUCKET:", bucket)
    print("RASTER KEY:", key)

    # Find the SAFE product root.
    parts = key.split("/")
    safe_index = next(
        (i for i, part in enumerate(parts) if part.endswith(".SAFE")),
        None
    )

    if safe_index is None:
        print("SAFE product root not found in asset key.")
        continue

    prefix = "/".join(parts[:safe_index + 1]) + "/"

    print("SAFE PREFIX:", prefix)

    response = s3.list_objects_v2(
        Bucket=bucket,
        Prefix=prefix,
        Delimiter="/",
        MaxKeys=100
    )

    print("ROOT OBJECTS:")
    for obj in response.get("Contents", []):
        print(" ", obj["Key"])

    print("ROOT DIRECTORIES:")
    for item in response.get("CommonPrefixes", []):
        print(" ", item["Prefix"])

print("\nPRODUCT METADATA DISCOVERY COMPLETE")
