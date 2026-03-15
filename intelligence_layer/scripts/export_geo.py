"""
export_geo.py — Regenerate geo_data_cache.json from the iso3166-2 package.

Usage (requires: pip install iso3166-2):
    python -m intelligence_layer.scripts.export_geo

This script is the authoritative source-of-record generator for
geo_data_cache.json.  The committed cache file was pre-generated using
hand-curated centroids for the 20 countries currently covered by OmnesVident.

Run this script whenever:
  - New countries are added to REGION_COORDS in geoUtils.ts
  - A more accurate centroid dataset is needed
  - The iso3166-2 package is updated with new subdivisions

Output format:
    { "US-TX": [31.054487, -97.563461], ... }

Keys  : ISO 3166-2 subdivision codes   (e.g. "US-TX", "GB-ENG")
Values: [latitude, longitude] centroid  (approximate geographic centre)
"""

import json
import os
from pathlib import Path

OUTPUT_PATH = Path(__file__).parent.parent / "geo_data_cache.json"

# Only export subdivisions for countries covered by OmnesVident
COVERED_COUNTRIES = {
    "US", "CA", "MX", "AR", "BR",
    "GB", "DE", "FR", "IT", "UA",
    "JP", "CN", "IN", "AU", "KR",
    "IL", "SA", "EG", "ZA", "NG",
}


def export() -> None:
    try:
        import iso3166_2 as iso  # type: ignore
    except ImportError:
        raise SystemExit(
            "iso3166-2 is not installed.\n"
            "Run:  pip install iso3166-2\n"
            "Then re-run this script."
        )

    mapping: dict[str, list[float]] = {}

    # subdivisions.all is {country_code: {subdivision_code: {attrs...}}}
    subdivisions = iso.Subdivisions()
    for country_code, subs in subdivisions.all.items():
        if country_code.upper() not in COVERED_COUNTRIES:
            continue
        for sub_code, attrs in subs.items():
            lat_lng = attrs.get("latLng") if isinstance(attrs, dict) else getattr(attrs, "latLng", None)
            if lat_lng and len(lat_lng) == 2:
                try:
                    mapping[sub_code.upper()] = [float(lat_lng[0]), float(lat_lng[1])]
                except (TypeError, ValueError):
                    pass  # skip entries with non-numeric coordinates

    print(f"Exported {len(mapping)} subdivision centroids across "
          f"{len(COVERED_COUNTRIES)} countries.")

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(mapping, f, indent=2)

    print(f"Saved to: {OUTPUT_PATH}")


if __name__ == "__main__":
    export()
