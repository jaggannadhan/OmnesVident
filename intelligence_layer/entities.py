"""
Geo-enrichment: extract ISO alpha-2 region codes mentioned in article text.

Strategy:
1. The event's own `region_code` is always included (primary tag from Module 1).
2. The title and snippet are scanned against a comprehensive country-name →
   ISO-code lookup table.
3. Results are de-duplicated and sorted for stable output.

This approach is deliberately dependency-free (no spaCy, no NLTK) to keep
the service lightweight.  A named-entity recognition model can replace this
in a later module for higher recall on demonyms ("French", "American", etc.)
and informal country references.
"""

import re
import logging
from typing import Dict, List, Set

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Country name → ISO alpha-2 lookup table
# ---------------------------------------------------------------------------
# Includes common short-forms, adjective forms, and abbreviations that appear
# frequently in news headlines.

_COUNTRY_MAP: Dict[str, str] = {
    # A
    "afghanistan": "AF", "albania": "AL", "algeria": "DZ", "angola": "AO",
    "argentina": "AR", "armenia": "AM", "australia": "AU", "austria": "AT",
    "azerbaijan": "AZ",
    # B
    "bahrain": "BH", "bangladesh": "BD", "belarus": "BY", "belgium": "BE",
    "bolivia": "BO", "bosnia": "BA", "botswana": "BW", "brazil": "BR",
    "bulgaria": "BG", "myanmar": "MM", "burma": "MM",
    # C
    "cambodia": "KH", "cameroon": "CM", "canada": "CA", "chile": "CL",
    "china": "CN", "chinese": "CN", "colombia": "CO", "congo": "CG",
    "costa rica": "CR", "croatia": "HR", "cuba": "CU", "cyprus": "CY",
    "czech republic": "CZ", "czechia": "CZ",
    # D
    "denmark": "DK", "dominican republic": "DO",
    # E
    "ecuador": "EC", "egypt": "EG", "el salvador": "SV", "ethiopia": "ET",
    # F
    "finland": "FI", "france": "FR", "french": "FR",
    # G
    "georgia": "GE", "germany": "DE", "german": "DE", "ghana": "GH",
    "greece": "GR", "greek": "GR", "guatemala": "GT",
    # H
    "haiti": "HT", "honduras": "HN", "hungary": "HU",
    # I
    "india": "IN", "indian": "IN", "indonesia": "ID", "iran": "IR",
    "iranian": "IR", "iraq": "IQ", "iraqi": "IQ", "ireland": "IE",
    "israel": "IL", "israeli": "IL", "italy": "IT", "italian": "IT",
    "ivory coast": "CI", "côte d'ivoire": "CI",
    # J
    "jamaica": "JM", "japan": "JP", "japanese": "JP", "jordan": "JO",
    # K
    "kazakhstan": "KZ", "kenya": "KE", "north korea": "KP",
    "south korea": "KR", "korean": "KR", "kuwait": "KW",
    # L
    "laos": "LA", "latvia": "LV", "lebanon": "LB", "libya": "LY",
    "lithuania": "LT",
    # M
    "malaysia": "MY", "mali": "ML", "mexico": "MX", "mexican": "MX",
    "moldova": "MD", "mongolia": "MN", "morocco": "MA", "mozambique": "MZ",
    # N
    "nepal": "NP", "netherlands": "NL", "dutch": "NL", "new zealand": "NZ",
    "nicaragua": "NI", "nigeria": "NG", "niger": "NE", "norway": "NO",
    # O / P
    "oman": "OM", "pakistan": "PK", "pakistani": "PK", "panama": "PA",
    "paraguay": "PY", "peru": "PE", "philippines": "PH", "poland": "PL",
    "polish": "PL", "portugal": "PT", "portuguese": "PT",
    # Q / R
    "qatar": "QA", "romania": "RO", "russia": "RU", "russian": "RU",
    "rwanda": "RW",
    # S
    "saudi arabia": "SA", "saudi": "SA", "senegal": "SN", "serbia": "RS",
    "sierra leone": "SL", "singapore": "SG", "slovakia": "SK",
    "somalia": "SO", "south africa": "ZA", "south sudan": "SS",
    "spain": "ES", "spanish": "ES", "sri lanka": "LK", "sudan": "SD",
    "sweden": "SE", "swedish": "SE", "switzerland": "CH", "swiss": "CH",
    "syria": "SY", "syrian": "SY",
    # T
    "taiwan": "TW", "tajikistan": "TJ", "tanzania": "TZ", "thailand": "TH",
    "thai": "TH", "tunisia": "TN", "turkey": "TR", "turkish": "TR",
    "turkmenistan": "TM",
    # U
    "uganda": "UG", "ukraine": "UA", "ukrainian": "UA",
    "united arab emirates": "AE", "uae": "AE",
    "united kingdom": "GB", "uk": "GB", "britain": "GB", "british": "GB",
    "united states": "US", "usa": "US", "american": "US",
    "uruguay": "UY", "uzbekistan": "UZ",
    # V
    "venezuela": "VE", "vietnam": "VN", "vietnamese": "VN",
    # Y / Z
    "yemen": "YE", "zambia": "ZM", "zimbabwe": "ZW",
}

# Sort by length descending so multi-word names ("north korea") are matched
# before single-word substrings ("korea").
_SORTED_NAMES = sorted(_COUNTRY_MAP.keys(), key=len, reverse=True)

# Pre-compile one pattern per country name (whole-word, case-insensitive)
_COMPILED_PATTERNS: List[tuple] = [
    (re.compile(r"\b" + re.escape(name) + r"\b", re.IGNORECASE), code)
    for name, code in ((n, _COUNTRY_MAP[n]) for n in _SORTED_NAMES)
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_mentioned_regions(title: str, snippet: str, primary_region: str) -> List[str]:
    """
    Return a de-duplicated, sorted list of ISO alpha-2 codes found in text.

    The event's own `primary_region` is always included as the first tag so
    the story remains discoverable in its originating region even when the
    title mentions no countries explicitly.
    """
    found: Set[str] = {primary_region.upper()}
    combined = f"{title} {snippet}"

    for pattern, iso_code in _COMPILED_PATTERNS:
        if pattern.search(combined):
            found.add(iso_code)

    # Primary region first, then others sorted alphabetically
    others = sorted(found - {primary_region.upper()})
    return [primary_region.upper()] + others
