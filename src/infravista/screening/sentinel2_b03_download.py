import os
import json
from pathlib import Path
from urllib.parse import urlparse

import boto3
import rasterio

MANIFEST = Path(
    "reports/p4_historical_growth/sentinel2_asset_manifest.json"
)

with MANIFEST.open(encoding="utf-8") as f:
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
    original_key = parsed.path.lstrip("/")

    # B03 and B04 belong to the same 20m IMG_DATA directory.
    # Change only the filename suffix.
    if not original_key.endswith("_B04_20m.jp2"):
        raise RuntimeError("Unexpected B04 asset naming pattern")

    key = original_key.replace(
        "_B04_20m.jp2",
        "_B03_20m.jp2"
    )

    output = (
        Path("data/raw/historical_sentinel2")
        / date / "hsr" / "B03_20m.jp2"
    )
    output.parent.mkdir(parents=True, exist_ok=True)

    print(f"\nDATE: {date}")
    print("Checking B03 asset...")

    head = s3.head_object(Bucket=bucket, Key=key)
    expected_size = int(head["ContentLength"])

    print("Remote size:", expected_size, "bytes")

    if output.exists() and output.stat().st_size == expected_size:
        print("Existing B03 file matches size. Skipping download.")
    else:
        temp = output.with_suffix(".jp2.part")
        print("Downloading B03...")

        try:
            s3.download_file(bucket, key, str(temp))

            if temp.stat().st_size != expected_size:
                raise RuntimeError("Downloaded file size mismatch")

            temp.replace(output)
        finally:
            if temp.exists():
                temp.unlink()

    with rasterio.open(output) as src:
        print("Driver:", src.driver)
        print("CRS:", src.crs)
        print("Resolution:", src.res)
        print("Dimensions:", src.width, "x", src.height)

        if str(src.crs) != "EPSG:32643" or src.res != (20.0, 20.0):
            raise RuntimeError("Unexpected B03 spatial metadata")

print("\nB03 GREEN BAND DOWNLOAD: COMPLETE")
