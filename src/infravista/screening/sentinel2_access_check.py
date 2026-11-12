import os
import json
from pathlib import Path
from urllib.parse import urlparse

import boto3
from botocore.config import Config

MANIFEST = Path("reports/p4_historical_growth/sentinel2_asset_manifest.json")
OUTPUT = Path("reports/p4_historical_growth/sentinel2_asset_access_check.json")

ESSENTIAL = [
    "SCL_20m",
    "B04_20m",
    "B08_10m",
    "B11_20m",
    "B12_20m",
]

with MANIFEST.open(encoding="utf-8") as f:
    manifest = json.load(f)

client = boto3.client(
    "s3",
    endpoint_url="https://eodata.dataspace.copernicus.eu",
    aws_access_key_id=os.environ["CDSE_S3_ACCESS_KEY"],
    aws_secret_access_key=os.environ["CDSE_S3_SECRET_KEY"],
    region_name="default",
    config=Config(signature_version="s3v4")
)

cache = {}
results = []

for product in manifest["products"]:
    for asset_name in ESSENTIAL:
        asset = product["assets"].get(asset_name, {})
        href = asset.get("href")
        available = asset.get("available", False)

        record = {
            "study_area": product["study_area"],
            "date": product["date"],
            "product_id": product["product_id"],
            "asset": asset_name,
            "catalogue_available": available,
            "access_status": "NOT_TESTED",
            "error": None,
        }

        if not available or not href:
            record["access_status"] = "UNAVAILABLE_IN_CATALOGUE"
            results.append(record)
            continue

        if href in cache:
            record.update(cache[href])
            record["access_status"] = (
                "ACCESSIBLE_CACHED" if cache[href]["access_status"] == "ACCESSIBLE"
                else cache[href]["access_status"]
            )
            results.append(record)
            continue

        try:
            parsed = urlparse(href)

            if parsed.scheme == "s3":
                bucket = parsed.netloc
                key = parsed.path.lstrip("/")
            else:
                raise ValueError("Unexpected asset URI scheme")

            response = client.get_object(
                Bucket=bucket,
                Key=key,
                Range="bytes=0-99"
            )
            data = response["Body"].read()

            check = {
                "access_status": "ACCESSIBLE",
                "http_status": response["ResponseMetadata"]["HTTPStatusCode"],
                "bytes_received": len(data),
                "content_range": response.get("ContentRange"),
                "error": None,
            }
            response["Body"].close()

        except Exception as exc:
            check = {
                "access_status": "FAILED",
                "http_status": getattr(exc, "response", {})
                    .get("ResponseMetadata", {}).get("HTTPStatusCode"),
                "bytes_received": 0,
                "content_range": None,
                "error": f"{type(exc).__name__}: {str(exc)[:500]}",
            }

        cache[href] = check
        record.update(check)
        results.append(record)

summary = {
    "manifest_product_records": len(manifest["products"]),
    "unique_asset_requests": len(cache),
    "total_asset_references": len(results),
    "accessible": sum(r["access_status"] in ("ACCESSIBLE", "ACCESSIBLE_CACHED") for r in results),
    "failed": sum(r["access_status"] == "FAILED" for r in results),
    "unavailable_in_catalogue": sum(r["access_status"] == "UNAVAILABLE_IN_CATALOGUE" for r in results),
}

report = {
    "source_manifest": str(MANIFEST),
    "test": "Authenticated S3 ranged GET, bytes 0-99",
    "summary": summary,
    "results": results,
}

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
with OUTPUT.open("w", encoding="utf-8") as f:
    json.dump(report, f, indent=2)

print("\nSENTINEL-2 ASSET ACCESS SUMMARY")
for key, value in summary.items():
    print(f"{key}: {value}")

print("\nFailed assets:")
for item in results:
    if item["access_status"] == "FAILED":
        print(item["study_area"], item["date"], item["asset"], item["error"])

print("\nReport saved:", OUTPUT)
