
import json
import urllib.parse
import urllib.request
import zipfile

from pathlib import Path
from datetime import date, timedelta

from shapely.geometry import shape


# ============================================================
# CONFIGURATION
# ============================================================

API = "https://stac.dataspace.copernicus.eu/v1/search"

ARCHIVE = Path(
    "handoff_data/P3_20261106T191045Z_indicators.zip"
)

OUTPUT = Path(
    "reports/p4_historical_growth/sentinel2_asset_manifest.json"
)

SELECTED_DATES = [
    "2017-02-03",
    "2025-02-06",
]

# Corrected asset selection:
# B08 is available as B08_10m, not B08_20m.

ASSET_KEYS = [
    "SCL_20m",
    "CLD_20m",
    "B04_20m",
    "B08_10m",
    "B11_20m",
    "B12_20m",
]


# ============================================================
# LOAD STUDY AREA GEOMETRIES
# ============================================================

def load_windows():

    if not ARCHIVE.exists():
        raise FileNotFoundError(
            f"P3 archive not found: {ARCHIVE}"
        )

    with zipfile.ZipFile(ARCHIVE) as archive:

        data = json.loads(
            archive.read("indicators_window.geojson")
        )

    windows = {}

    for feature in data["features"]:

        area = feature["properties"]["area_id"]

        windows.setdefault(
            area,
            shape(feature["geometry"])
        )

    if not windows:
        raise ValueError(
            "No study-area geometries found in P3 archive."
        )

    return windows


# ============================================================
# COPERNICUS STAC PRODUCT SEARCH
# ============================================================

def search_products(geometry, selected_date):

    minx, miny, maxx, maxy = geometry.bounds

    next_date = (
        date.fromisoformat(selected_date)
        + timedelta(days=1)
    ).isoformat()

    params = {
        "collections": "sentinel-2-l2a",
        "bbox": f"{minx},{miny},{maxx},{maxy}",
        "datetime": (
            f"{selected_date}T00:00:00Z/"
            f"{next_date}T00:00:00Z"
        ),
        "limit": 100,
    }

    url = API + "?" + urllib.parse.urlencode(params)

    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/geo+json",
            "User-Agent": "InfraVista-P4/1.0",
        },
    )

    with urllib.request.urlopen(
        request,
        timeout=90
    ) as response:

        return json.loads(
            response.read().decode("utf-8")
        )


# ============================================================
# EXTRACT ASSET METADATA
# ============================================================

def extract_assets(item):

    available_assets = item.get("assets", {})

    assets = {}

    for key in ASSET_KEYS:

        asset = available_assets.get(key)

        if asset is None:

            assets[key] = {
                "available": False,
                "href": None,
                "type": None,
                "title": None,
                "roles": [],
            }

            continue

        assets[key] = {
            "available": True,
            "href": asset.get("href"),
            "type": asset.get("type"),
            "title": asset.get("title"),
            "roles": asset.get("roles", []),
        }

    return assets


# ============================================================
# MAIN EXECUTION
# ============================================================

def main():

    windows = load_windows()

    results = []

    for area, geometry in windows.items():

        for selected_date in SELECTED_DATES:

            print(
                f"\nChecking {area}: {selected_date}"
            )

            data = search_products(
                geometry,
                selected_date
            )

            matching_products = 0

            for item in data.get("features", []):

                props = item.get("properties", {})

                product_datetime = (
                    props.get("datetime") or ""
                )

                if product_datetime[:10] != selected_date:
                    continue

                matching_products += 1

                available_asset_keys = sorted(
                    item.get("assets", {}).keys()
                )

                assets = extract_assets(item)

                product = {
                    "study_area": area,
                    "date": selected_date,
                    "product_id": item.get("id"),
                    "platform": props.get("platform"),
                    "cloud_cover": props.get(
                        "eo:cloud_cover"
                    ),
                    "available_asset_keys": available_asset_keys,
                    "assets": assets,
                }

                results.append(product)

                print(
                    "Product:",
                    product["product_id"]
                )

                for key, asset in assets.items():

                    status = (
                        "AVAILABLE"
                        if asset["available"]
                        else "MISSING"
                    )

                    print(f"  {key}: {status}")

            if matching_products == 0:

                print(
                    "WARNING: No matching products found."
                )

    # --------------------------------------------------------
    # SAVE MANIFEST
    # --------------------------------------------------------

    OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    report = {
        "source": "Copernicus Data Space Ecosystem STAC",
        "collection": "sentinel-2-l2a",
        "selected_dates": SELECTED_DATES,
        "product_count": len(results),
        "products": results,
        "analysis_resolution_m": 20,
        "limitations": [
            "STAC asset availability does not prove download access.",
            "B08_10m requires alignment to the 20m analysis grid.",
            "Pixel-level cloud and shadow coverage is not yet assessed.",
            "Study-area raster coverage and alignment are not yet verified.",
            "Whitefield requires two-tile coverage assessment.",
            "Satellite products use different platforms and processing baselines.",
        ],
    }

    OUTPUT.write_text(
        json.dumps(report, indent=2),
        encoding="utf-8"
    )

    # --------------------------------------------------------
    # SUMMARY
    # --------------------------------------------------------

    print("\n" + "=" * 55)
    print("SENTINEL-2 ASSET MANIFEST CREATED")
    print("=" * 55)

    print("Total products:", len(results))
    print("Output:", OUTPUT)

    for area in windows:

        area_products = [
            product
            for product in results
            if product["study_area"] == area
        ]

        print(f"\n{area.upper()}")

        for product in area_products:

            available_count = sum(
                asset["available"]
                for asset in product["assets"].values()
            )

            print(
                product["date"],
                "|",
                available_count,
                "/",
                len(ASSET_KEYS),
                "assets available",
            )

    print("\nManifest generation completed successfully.")


if __name__ == "__main__":
    main()
