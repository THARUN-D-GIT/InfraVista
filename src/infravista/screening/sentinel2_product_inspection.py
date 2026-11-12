
import json
import urllib.parse
import urllib.request
import urllib.error
import zipfile
from pathlib import Path

from shapely.geometry import shape


API = "https://stac.dataspace.copernicus.eu/v1/search"

ARCHIVE = Path(
    "handoff_data/P3_20261106T191045Z_indicators.zip"
)

SELECTED_DATES = [
    "2017-02-03",
    "2025-02-06",
]


def load_windows():
    """Load one unique study-area geometry from the P3 package."""

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

        if area not in windows:
            windows[area] = shape(feature["geometry"])

    return windows


def request_json(params):
    """Send one STAC request and return its JSON response."""

    url = API + "?" + urllib.parse.urlencode(params)

    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/geo+json",
            "User-Agent": "InfraVista-P4/1.0",
        },
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=90,
        ) as response:
            return json.loads(
                response.read().decode("utf-8")
            )

    except urllib.error.HTTPError as error:
        error_body = error.read().decode(
            "utf-8",
            errors="replace",
        )

        raise RuntimeError(
            f"STAC API returned HTTP {error.code}\n"
            f"Request URL: {url}\n"
            f"Response: {error_body}"
        ) from error


def search_date(geometry, date):
    """Search one calendar date independently."""

    minx, miny, maxx, maxy = geometry.bounds

    from datetime import date as date_type, timedelta

    selected_date = date_type.fromisoformat(date)
    next_date = selected_date + timedelta(days=1)

    params = {
        "collections": "sentinel-2-l2a",
        "bbox": f"{minx},{miny},{maxx},{maxy}",
        "datetime": (
            f"{date}T00:00:00Z/"
            f"{next_date.isoformat()}T00:00:00Z"
        ),
        "limit": 100,
    }

    data = request_json(params)

    return data.get("features", [])


def inspect_area(area, geometry):
    print(f"\n{'=' * 75}")
    print(f"{area.upper()} PRODUCT INSPECTION")
    print("=" * 75)

    all_items = {}

    for selected_date in SELECTED_DATES:
        print(f"\nSearching date: {selected_date}")

        items = search_date(
            geometry,
            selected_date,
        )

        print(f"Products returned: {len(items)}")

        for item in items:
            item_id = item.get("id")

            if item_id:
                all_items[item_id] = item

    if not all_items:
        print("\nNo products returned for this study area.")
        return

    for item in all_items.values():
        props = item.get("properties", {})
        product_date = (props.get("datetime") or "")[:10]

        if product_date not in SELECTED_DATES:
            continue

        print(f"\n{'-' * 75}")
        print("Product:", item.get("id"))
        print("Date:", product_date)
        print("Platform:", props.get("platform"))
        print(
            "Processing baseline:",
            props.get("s2:processing_baseline"),
        )
        print(
            "Cloud cover:",
            props.get("eo:cloud_cover"),
        )
        print("Projection:", props.get("proj:epsg"))
        print("Ground sample distance:", props.get("gsd"))

        print("\nAssets:")

        for key, asset in item.get("assets", {}).items():
            print(
                " ",
                key,
                "| type:", asset.get("type"),
                "| title:", asset.get("title"),
                "| roles:", asset.get("roles"),
            )

        print("\nRelevant links:")

        for link in item.get("links", []):
            if link.get("rel") in (
                "self",
                "preview",
                "license",
            ):
                print(
                    " ",
                    link.get("rel"),
                    link.get("href"),
                )


def main():
    windows = load_windows()

    print("InfraVista P4 - Sentinel-2 Product Inspection")
    print("Selected dates:", ", ".join(SELECTED_DATES))
    print("Study areas:", ", ".join(windows.keys()))

    for area, geometry in windows.items():
        inspect_area(area, geometry)

    print("\nInspection completed.")
    print("Note: This script only inspects catalogue metadata.")
    print("No satellite imagery has been downloaded.")


if __name__ == "__main__":
    main()
