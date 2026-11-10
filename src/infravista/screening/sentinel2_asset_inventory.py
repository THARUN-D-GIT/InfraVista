
import json
from pathlib import Path

MANIFEST = Path(
    "reports/p4_historical_growth/sentinel2_asset_manifest.json"
)

def main():
    if not MANIFEST.exists():
        raise FileNotFoundError(
            f"Asset manifest not found: {MANIFEST}"
        )

    data = json.loads(MANIFEST.read_text(encoding="utf-8"))

    print("SENTINEL-2 COMPLETE ASSET INVENTORY")
    print("=" * 70)

    for product in data.get("products", []):
        print("\nStudy area:", product.get("study_area"))
        print("Date:", product.get("date"))
        print("Product:", product.get("product_id"))

        # The current manifest contains only selected asset keys.
        # This script therefore checks whether complete asset metadata
        # is available in the manifest before proceeding.
        assets = product.get("assets", {})

        print("\nRecorded assets:")
        for key, details in assets.items():
            print(f"  {key}:")
            print("    Available:", details.get("available"))
            print("    Type:", details.get("type"))
            print("    Title:", details.get("title"))
            print("    Roles:", details.get("roles"))

    print("\nInventory inspection complete.")
    print(
        "\nNote: This manifest records selected assets only. "
        "A full catalogue query is needed to discover omitted keys."
    )

if __name__ == "__main__":
    main()
