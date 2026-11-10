import json
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path
from collections import defaultdict

from shapely.geometry import shape

API = "https://stac.dataspace.copernicus.eu/v1/search"
COLLECTION = "sentinel-2-l2a"

ARCHIVE = Path(
    "handoff_data/P3_20261106T191045Z_indicators.zip"
)

OUTPUT = Path(
    "reports/p4_historical_growth/sentinel2_verified_candidates.json"
)

PERIODS = {
    "2017": "2017-01-01T00:00:00Z/2017-03-01T00:00:00Z",
    "2025": "2025-01-01T00:00:00Z/2025-03-01T00:00:00Z",
}


def load_windows():
    with zipfile.ZipFile(ARCHIVE) as archive:
        data = json.loads(
            archive.read("indicators_window.geojson")
        )

    windows = {}

    for feature in data["features"]:
        area = feature["properties"]["area_id"]
        geometry = shape(feature["geometry"])

        if area in windows and not windows[area].equals(geometry):
            raise ValueError(
                f"Inconsistent window geometry for {area}"
            )

        windows[area] = geometry

    return windows


def request_json(url):
    req = urllib.request.Request(
        url,
        headers={"Accept": "application/geo+json"},
    )

    with urllib.request.urlopen(req, timeout=90) as response:
        return json.loads(response.read().decode("utf-8"))


def search(area_geometry, date_range):
    minx, miny, maxx, maxy = area_geometry.bounds

    params = {
        "collections": COLLECTION,
        "bbox": f"{minx},{miny},{maxx},{maxy}",
        "datetime": date_range,
        "limit": 100,
    }

    url = API + "?" + urllib.parse.urlencode(params)
    items = []

    while url:
        data = request_json(url)
        items.extend(data.get("features", []))

        next_link = next(
            (
                link for link in data.get("links", [])
                if link.get("rel") == "next"
            ),
            None,
        )

        url = next_link.get("href") if next_link else None

    return items


def main():
    windows = load_windows()

    report = {
        "collection": COLLECTION,
        "method": "exact_study_area_scene_footprint_intersection",
        "areas": {},
        "limitations": [
            "Intersection verifies geometry overlap, not usable pixel coverage.",
            "Scene cloud cover is not study-area cloud cover.",
            "No imagery has been downloaded.",
            "No classification or change detection has been performed.",
        ],
    }

    for area, geometry in windows.items():
        report["areas"][area] = {}

        for year, date_range in PERIODS.items():
            items = search(geometry, date_range)
            verified = []
            rejected = 0

            for item in items:
                footprint_data = item.get("geometry")

                if not footprint_data:
                    rejected += 1
                    continue

                footprint = shape(footprint_data)

                if not footprint.is_valid:
                    footprint = footprint.buffer(0)

                if footprint.is_empty or not geometry.intersects(footprint):
                    rejected += 1
                    continue

                props = item.get("properties", {})
                product_id = item.get("id", "")
                tile = None

                if "_T" in product_id:
                    tile = product_id.split("_T")[-1][:5]

                verified.append({
                    "product_id": product_id,
                    "acquisition_datetime": props.get("datetime"),
                    "acquisition_date": (
                        props.get("datetime", "")[:10]
                    ),
                    "platform": props.get("platform"),
                    "mgrs_tile": tile,
                    "cloud_cover_metadata": props.get(
                        "eo:cloud_cover"
                    ),
                    "processing_level": props.get(
                        "processing:level"
                    ),
                    "footprint_intersects": True,
                })

            verified.sort(
                key=lambda x: (
                    x["acquisition_datetime"] or "",
                    x["mgrs_tile"] or "",
                )
            )

            dates = defaultdict(list)

            for product in verified:
                dates[product["acquisition_date"]].append(product)

            report["areas"][area][year] = {
                "verified_product_count": len(verified),
                "rejected_product_count": rejected,
                "unique_acquisition_dates": len(dates),
                "products": verified,
                "acquisition_dates": {
                    date: products
                    for date, products in sorted(dates.items())
                },
            }

            print(
                f"\n{area.upper()} {year}: "
                f"{len(verified)} intersecting products, "
                f"{len(dates)} acquisition dates, "
                f"{rejected} rejected"
            )

            for date, products in sorted(dates.items()):
                tiles = sorted({
                    p["mgrs_tile"] for p in products
                    if p["mgrs_tile"]
                })
                print(
                    date,
                    "| tiles:", ", ".join(tiles),
                    "| products:", len(products),
                )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )

    print("\nVerification completed.")
    print("Report:", OUTPUT)


if __name__ == "__main__":
    main()
