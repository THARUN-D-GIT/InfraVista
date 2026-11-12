import json
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://stac.dataspace.copernicus.eu/v1/search"
COLLECTION = "sentinel-2-l2a"

AREAS = {
    "hsr": [77.6158785589, 12.8890171528, 77.6619209909, 12.9341828039],
    "whitefield": [77.7269753234, 12.9472193263, 77.7730242071, 12.99238062998],
}

PERIODS = {
    "2017": "2017-01-01T00:00:00Z/2017-03-01T00:00:00Z",
    "2025": "2025-01-01T00:00:00Z/2025-03-01T00:00:00Z",
}

OUTPUT = Path("reports/p4_historical_growth")
OUTPUT.mkdir(parents=True, exist_ok=True)


def get_json(url):
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/geo+json"},
    )

    with urllib.request.urlopen(request, timeout=90) as response:
        return json.loads(response.read().decode("utf-8"))


def search_items(bbox, datetime_range):
    params = {
        "collections": COLLECTION,
        "bbox": ",".join(map(str, bbox)),
        "datetime": datetime_range,
        "limit": 100,
    }

    url = API + "?" + urllib.parse.urlencode(params)
    items = []

    while url:
        data = get_json(url)
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
    report = {
        "collection": COLLECTION,
        "catalogue": API,
        "search_type": "bounding_box_candidate_search",
        "periods": PERIODS,
        "areas": {},
        "limitations": [
            "P3 pilot window geometries are used as search proxies.",
            "Bounding-box intersection does not prove exact polygon intersection.",
            "Cloud cover is scene-level metadata, not study-area cloud cover.",
            "No imagery has been downloaded or processed.",
            "Catalogue availability does not establish classification suitability.",
        ],
    }

    for area, bbox in AREAS.items():
        report["areas"][area] = {}

        for year, date_range in PERIODS.items():
            print(f"\nSearching {area.upper()} — {year}...")

            items = search_items(bbox, date_range)
            results = []

            for item in items:
                props = item.get("properties", {})
                results.append({
                    "id": item.get("id"),
                    "datetime": props.get("datetime"),
                    "cloud_cover_percent": props.get("eo:cloud_cover"),
                    "platform": props.get("platform"),
                    "processing_level": props.get("processing:level"),
                    "mgrs_tile": props.get("s2:mgrs_tile"),
                    "bbox": item.get("bbox"),
                })

            results.sort(
                key=lambda x: (
                    x.get("cloud_cover_percent")
                    if isinstance(x.get("cloud_cover_percent"), (int, float))
                    else 999
                )
            )

            report["areas"][area][year] = {
                "candidate_count": len(results),
                "candidates": results,
            }

            print("Candidate scenes:", len(results))

            for item in results[:10]:
                print(
                    item["datetime"],
                    "| cloud:",
                    item["cloud_cover_percent"],
                    "| tile:",
                    item["mgrs_tile"],
                    "| id:",
                    item["id"],
                )

    output_file = OUTPUT / "sentinel2_catalogue_candidates.json"
    output_file.write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )

    print("\nCatalogue search completed.")
    print("Report:", output_file)


if __name__ == "__main__":
    main()
