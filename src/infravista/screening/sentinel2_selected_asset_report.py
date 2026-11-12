
import json
from pathlib import Path

MANIFEST = Path(
    "reports/p4_historical_growth/sentinel2_full_asset_manifest.json"
)

SELECTED_KEYS = [
    "B04_10m",
    "B08_10m",
    "B11_20m",
    "B12_20m",
    "SCL_20m",
    "CLD_20m"
]


def main():
    data = json.loads(
        MANIFEST.read_text(encoding="utf-8")
    )

    print("SELECTED SENTINEL-2 ASSET REPORT")
    print("=" * 75)

    for product in data["products"]:
        print(
            f"\n{product['study_area'].upper()} | "
            f"{product['date']} | "
            f"{product['product_id']}"
        )

        assets = product["assets"]

        for key in SELECTED_KEYS:
            asset = assets.get(key)

            if asset is None:
                print(f"\n{key}: NOT AVAILABLE")
                continue

            print(f"\n{key}")
            print("  Type:", asset.get("type"))
            print("  Title:", asset.get("title"))
            print("  Roles:", asset.get("roles"))
            print("  Href present:", bool(asset.get("href")))
            print("  Extra metadata:", asset.get("extra_fields"))

    print("\nInspection complete.")
    print("No imagery was downloaded.")


if __name__ == "__main__":
    main()
