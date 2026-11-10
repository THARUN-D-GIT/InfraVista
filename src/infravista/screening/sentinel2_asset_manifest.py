
import json
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path
from datetime import date, timedelta

from shapely.geometry import shape

API = "https://stac.dataspace.copernicus.eu/v1/search"

ARCHIVE = Path(
    "handoff_data/P3_20261106T191045Z_indicators.zip"
)

OUTPUT = Path(
    "reports/p4_historical_growth/sentinel2_full_asset_manifest.json"
)

SELECTED_DATES = ["2017-02-03", "2025-02-06"]

IMPORTANT_ASSETS = [
    "B02", "B03", "B04", "B08", "B11", "B12",
    "B08_10m", "B08_20m",
    "SCL_20m", "CLD_20m", "CLP",
    "visual", "thumbnail"
]


def load_windows():
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

    return windows


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
        "limit": 100
    }

    url = API + "?" + urllib.parse.urlencode(params)

    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/geo+json",
            "User-Agent": "InfraVista-P4/1.0"
        }
    )

    with urllib.request.urlopen(
        request,
        timeout=90
    ) as response:
        return json.loads(
            response.read().decode("utf-8")
        )


def main():
    windows = load_windows()
    results = []

    for area, geometry in windows.items():
        for selected_date in SELECTED_DATES:

            data = search_products(
                geometry,
                selected_date
            )

            for item in data.get("features", []):
                props = item.get("properties", {})

                if (
                    (props.get("datetime") or "")[:10]
                    != selected_date
                ):
                    continue

                all_assets = {}

                for key, asset in item.get(
                    "assets", {}
                ).items():

                    all_assets[key] = {
                        "href": asset.get("href"),
                        "type": asset.get("type"),
                        "title": asset.get("title"),
                        "roles": asset.get("roles"),
                        "extra_fields": {
                            name: value
                            for name, value in asset.items()
                            if name not in {
                                "href", "type", "title",
                                "roles"
                            }
                        }
                    }

                results.append({
                    "study_area": area,
                    "date": selected_date,
                    "product_id": item.get("id"),
                    "platform": props.get("platform"),
                    "cloud_cover": props.get(
                        "eo:cloud_cover"
                    ),
                    "all_asset_keys": sorted(
                        all_assets.keys()
                    ),
                    "assets": all_assets
                })

    OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    report = {
        "source": "Copernicus Data Space Ecosystem STAC",
        "collection": "sentinel-2-l2a",
        "selected_dates": SELECTED_DATES,
        "product_count": len(results),
        "important_asset_keys_checked": IMPORTANT_ASSETS,
        "products": results
    }

    OUTPUT.write_text(
        json.dumps(report, indent=2),
        encoding="utf-8"
    )

    print("Full Sentinel-2 asset manifest created.")
    print("Products:", len(results))
    print("Output:", OUTPUT)

    for product in results:
        print(
            "\n",
            product["study_area"],
            product["date"],
            product["product_id"]
        )

        keys = set(product["all_asset_keys"])

        for key in IMPORTANT_ASSETS:
            if key in keys:
                print("  FOUND:", key)

        print("  Total asset keys:", len(keys))


if __name__ == "__main__":
    main()
