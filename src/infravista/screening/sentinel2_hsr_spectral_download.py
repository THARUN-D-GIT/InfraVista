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

bands = ["B04_20m", "B08_10m", "B11_20m", "B12_20m"]
dates = ["2017-02-03", "2025-02-06"]

s3 = boto3.client(
    "s3",
    endpoint_url="https://eodata.dataspace.copernicus.eu",
    aws_access_key_id=os.environ["CDSE_S3_ACCESS_KEY"],
    aws_secret_access_key=os.environ["CDSE_S3_SECRET_KEY"],
    region_name="default"
)

records = []

for date in dates:
    product = next(
        p for p in manifest["products"]
        if p["study_area"] == "hsr" and p["date"] == date
    )

    print(f"\nDATE: {date}")
    print("PRODUCT:", product["product_id"])

    for band in bands:
        asset = product["assets"][band]

        if not asset["available"] or not asset.get("href"):
            raise RuntimeError(f"Missing {band} for {date}")

        parsed = urlparse(asset["href"])
        bucket = parsed.netloc
        key = parsed.path.lstrip("/")

        output = (
            Path("data/raw/historical_sentinel2")
            / date / "hsr" / f"{band}.jp2"
        )
        output.parent.mkdir(parents=True, exist_ok=True)

        head = s3.head_object(Bucket=bucket, Key=key)
        remote_size = int(head["ContentLength"])

        if output.exists() and output.stat().st_size == remote_size:
            print(f"Skipping existing {band}: {remote_size:,} bytes")
        else:
            print(f"Downloading {band}: {remote_size:,} bytes")
            temp = output.with_suffix(".jp2.part")

            try:
                s3.download_file(bucket, key, str(temp))
                if temp.stat().st_size != remote_size:
                    raise RuntimeError(f"Size mismatch for {band}")
                temp.replace(output)
            finally:
                if temp.exists():
                    temp.unlink()

        with rasterio.open(output) as src:
            info = {
                "date": date,
                "product_id": product["product_id"],
                "band": band,
                "path": str(output),
                "size_bytes": output.stat().st_size,
                "crs": str(src.crs),
                "resolution": list(src.res),
                "width": src.width,
                "height": src.height,
                "dtype": src.dtypes[0],
                "bounds": list(src.bounds),
            }

            records.append(info)
            print(
                f"  Verified: {src.width}x{src.height}, "
                f"{src.res}, {src.crs}"
            )

report = Path(
    "reports/p4_historical_growth/sentinel2_hsr_spectral_assets.json"
)
report.parent.mkdir(parents=True, exist_ok=True)
report.write_text(
    json.dumps(records, indent=2),
    encoding="utf-8"
)

print("\nAssets verified:", len(records))
print("Report saved:", report)
print("HSR SPECTRAL BAND DOWNLOAD: COMPLETE")
