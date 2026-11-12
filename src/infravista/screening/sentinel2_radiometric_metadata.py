import os
import json
import xml.etree.ElementTree as ET
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

band_ids = {
    "B04": "3",
    "B08": "7",
    "B11": "11",
    "B12": "12",
}

report = {}

for date in ["2017-02-03", "2025-02-06"]:
    product = next(
        p for p in manifest["products"]
        if p["study_area"] == "hsr" and p["date"] == date
    )

    parsed = urlparse(product["assets"]["B04_20m"]["href"])
    bucket = parsed.netloc
    parts = parsed.path.lstrip("/").split("/")

    safe_index = next(
        i for i, part in enumerate(parts)
        if part.endswith(".SAFE")
    )

    prefix = "/".join(parts[:safe_index + 1])
    key = prefix + "/MTD_MSIL2A.xml"

    output = (
        Path("data/raw/historical_sentinel2")
        / date / "hsr" / "MTD_MSIL2A.xml"
    )
    output.parent.mkdir(parents=True, exist_ok=True)

    if not output.exists():
        print(f"Downloading metadata for {date}...")
        s3.download_file(bucket, key, str(output))

    root = ET.parse(output).getroot()

    def local_name(element):
        return element.tag.rsplit("}", 1)[-1]

    quantification = []
    offsets = {}
    baseline = []

    for element in root.iter():
        name = local_name(element)

        if name == "BOA_QUANTIFICATION_VALUE":
            quantification.append(element.text)

        elif name == "BOA_ADD_OFFSET":
            band_id = element.attrib.get("band_id")
            offsets[band_id] = element.text

        elif name == "PROCESSING_BASELINE":
            baseline.append(element.text)

    result = {
        "product_id": product["product_id"],
        "date": date,
        "processing_baseline": baseline,
        "boa_quantification_values": quantification,
        "boa_add_offsets": {
            band: offsets.get(band_id)
            for band, band_id in band_ids.items()
        },
        "all_offset_band_ids": offsets,
    }

    report[date] = result

    print(f"\nDATE: {date}")
    print("Processing baseline:", baseline)
    print("BOA quantification:", quantification)

    for band, value in result["boa_add_offsets"].items():
        print(f"{band} offset: {value}")

    if not quantification or any(
        value is None for value in result["boa_add_offsets"].values()
    ):
        print("WARNING: Incomplete calibration metadata!")

output = Path(
    "reports/p4_historical_growth/sentinel2_radiometric_calibration.json"
)
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(report, indent=2), encoding="utf-8")

print("\nCalibration report:", output)
print("RADIOMETRIC METADATA INSPECTION: COMPLETE")
