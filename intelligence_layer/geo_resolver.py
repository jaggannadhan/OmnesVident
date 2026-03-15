"""
GeoResolver — maps (country_code, region_name) → (latitude, longitude).

Resolution waterfall:
  1. Exact ISO 3166-2 code lookup  (e.g. "US-TX" → [31.05, -97.56])
  2. Fuzzy subdivision name match  (e.g. "Texas" → normalise → "US-TX")
  3. Country centroid fallback      (e.g. "US"   → [37.09, -95.71])
  4. Hard None if country unknown

The cache is loaded once at module import and is read-only thereafter.
GeoResolver instances are stateless; a single shared instance is fine.
"""

from __future__ import annotations

import json
import logging
import re
import unicodedata
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Country centroids (mirrors geoUtils.ts REGION_COORDS)
# ---------------------------------------------------------------------------
_COUNTRY_CENTROIDS: dict[str, Tuple[float, float]] = {
    "US": (37.09,   -95.71),
    "CA": (56.13,  -106.35),
    "MX": (23.63,  -102.55),
    "AR": (-38.42,  -63.62),
    "BR": (-14.24,  -51.93),
    "GB": (55.38,    -3.44),
    "DE": (51.17,    10.45),
    "FR": (46.23,     2.21),
    "IT": (41.87,    12.57),
    "UA": (48.38,    31.17),
    "JP": (36.20,   138.25),
    "CN": (35.86,   104.19),
    "IN": (20.59,    78.96),
    "AU": (-25.27,  133.78),
    "KR": (35.91,   127.77),
    "IL": (31.05,    34.85),
    "SA": (23.89,    45.08),
    "EG": (26.82,    30.80),
    "ZA": (-30.56,   22.94),
    "NG": (9.08,      8.68),
}

# ---------------------------------------------------------------------------
# Subdivision name → ISO code  (hand-curated normalisation map)
# ---------------------------------------------------------------------------
# Keys are lowercased, accent-stripped, non-alpha-stripped versions of common
# region name variants that appear in news text.
_NAME_TO_CODE: dict[str, str] = {
    # United States
    "alabama": "US-AL", "alaska": "US-AK", "arizona": "US-AZ",
    "arkansas": "US-AR", "california": "US-CA", "colorado": "US-CO",
    "connecticut": "US-CT", "delaware": "US-DE", "florida": "US-FL",
    "georgia": "US-GA", "hawaii": "US-HI", "idaho": "US-ID",
    "illinois": "US-IL", "indiana": "US-IN", "iowa": "US-IA",
    "kansas": "US-KS", "kentucky": "US-KY", "louisiana": "US-LA",
    "maine": "US-ME", "maryland": "US-MD", "massachusetts": "US-MA",
    "michigan": "US-MI", "minnesota": "US-MN", "mississippi": "US-MS",
    "missouri": "US-MO", "montana": "US-MT", "nebraska": "US-NE",
    "nevada": "US-NV", "new hampshire": "US-NH", "new jersey": "US-NJ",
    "new mexico": "US-NM", "new york": "US-NY", "north carolina": "US-NC",
    "north dakota": "US-ND", "ohio": "US-OH", "oklahoma": "US-OK",
    "oregon": "US-OR", "pennsylvania": "US-PA", "rhode island": "US-RI",
    "south carolina": "US-SC", "south dakota": "US-SD", "tennessee": "US-TN",
    # US Tier 2/3 cities (resolver supplement — tagger already has them)
    "mcallen": "US-TX", "killeen": "US-TX", "frisco": "US-TX",
    "waco": "US-TX", "beaumont": "US-TX", "midland": "US-TX",
    "odessa": "US-TX", "abilene": "US-TX", "brownsville": "US-TX",
    "denton": "US-TX", "round rock": "US-TX", "mckinney": "US-TX",
    "carrollton": "US-TX", "mesquite": "US-TX",
    "modesto": "US-CA", "fontana": "US-CA", "moreno valley": "US-CA",
    "glendale": "US-CA", "huntington beach": "US-CA", "santa clarita": "US-CA",
    "garden grove": "US-CA", "oceanside": "US-CA", "rancho cucamonga": "US-CA",
    "elk grove": "US-CA", "hayward": "US-CA", "lancaster": "US-CA",
    "palmdale": "US-CA", "salinas": "US-CA", "sunnyvale": "US-CA",
    "pomona": "US-CA", "escondido": "US-CA", "torrance": "US-CA",
    "santa rosa": "US-CA", "fremont": "US-CA",
    "port st lucie": "US-FL", "pembroke pines": "US-FL", "cape coral": "US-FL",
    "lakeland": "US-FL", "clearwater": "US-FL", "west palm beach": "US-FL",
    "coral springs": "US-FL", "miramar": "US-FL", "pompano beach": "US-FL",
    "fort myers": "US-FL", "daytona beach": "US-FL", "palm bay": "US-FL",
    "texas": "US-TX", "utah": "US-UT", "vermont": "US-VT",
    "virginia": "US-VA", "washington": "US-WA", "west virginia": "US-WV",
    "wisconsin": "US-WI", "wyoming": "US-WY",
    "washington dc": "US-DC", "washington d.c.": "US-DC", "district of columbia": "US-DC",
    # Canada
    "alberta": "CA-AB", "british columbia": "CA-BC", "manitoba": "CA-MB",
    "new brunswick": "CA-NB", "newfoundland": "CA-NL", "newfoundland and labrador": "CA-NL",
    "nova scotia": "CA-NS", "northwest territories": "CA-NT", "nunavut": "CA-NU",
    "ontario": "CA-ON", "prince edward island": "CA-PE", "quebec": "CA-QC",
    "saskatchewan": "CA-SK", "yukon": "CA-YT",
    # Germany
    "berlin": "DE-BE", "hamburg": "DE-HH", "bremen": "DE-HB",
    "bavaria": "DE-BY", "bayern": "DE-BY",
    "north rhine-westphalia": "DE-NW", "northrhinewestphalia": "DE-NW",
    "nordrhein-westfalen": "DE-NW", "nordrheinwestfalen": "DE-NW",
    "lower saxony": "DE-NI", "niedersachsen": "DE-NI",
    "hesse": "DE-HE", "hessen": "DE-HE",
    "saxony": "DE-SN", "sachsen": "DE-SN",
    "thuringia": "DE-TH", "thuringen": "DE-TH", "thuringen": "DE-TH",
    "rhineland-palatinate": "DE-RP", "rheinland-pfalz": "DE-RP",
    "saarland": "DE-SL",
    "saxony-anhalt": "DE-ST", "sachsen-anhalt": "DE-ST",
    "schleswig-holstein": "DE-SH",
    "mecklenburg-vorpommern": "DE-MV",
    "brandenburg": "DE-BB",
    "baden-wurttemberg": "DE-BW", "badenwurttemberg": "DE-BW",
    # France
    "ile-de-france": "FR-IDF", "paris": "FR-IDF",
    "auvergne-rhone-alpes": "FR-ARA", "lyon": "FR-ARA",
    "nouvelle-aquitaine": "FR-NAQ", "bordeaux": "FR-NAQ",
    "occitanie": "FR-OCC", "toulouse": "FR-OCC",
    "hauts-de-france": "FR-HDF", "lille": "FR-HDF",
    "grand est": "FR-GES", "strasbourg": "FR-GES",
    "bretagne": "FR-BRE", "brittany": "FR-BRE",
    "normandie": "FR-NOR", "normandy": "FR-NOR",
    "pays de la loire": "FR-PDL", "nantes": "FR-PDL",
    "provence-alpes-cote dazur": "FR-PAC", "marseille": "FR-PAC",
    "bourgogne-franche-comte": "FR-BFC",
    "centre-val de loire": "FR-CVL",
    "corse": "FR-COR", "corsica": "FR-COR",
    # United Kingdom
    "england": "GB-ENG", "scotland": "GB-SCT", "wales": "GB-WLS",
    "northern ireland": "GB-NIR",
    "london": "GB-LND", "greater london": "GB-LND",
    "manchester": "GB-MAN", "birmingham": "GB-BRM",
    # Italy
    "lombardy": "IT-25", "lombardia": "IT-25", "milan": "IT-25",
    "lazio": "IT-62", "rome": "IT-62",
    "campania": "IT-72", "naples": "IT-72",
    "sicily": "IT-88", "sicilia": "IT-88",
    "tuscany": "IT-55", "toscana": "IT-55", "florence": "IT-55",
    "veneto": "IT-34", "venice": "IT-34",
    "emilia-romagna": "IT-45", "bologna": "IT-45",
    "piedmont": "IT-21", "piemonte": "IT-21", "turin": "IT-21",
    "puglia": "IT-65", "apulia": "IT-65",
    "calabria": "IT-78",
    # Japan (major cities / regions)
    "tokyo": "JP-13", "osaka": "JP-27", "kyoto": "JP-26",
    "yokohama": "JP-14", "nagoya": "JP-23", "sapporo": "JP-01",
    "fukuoka": "JP-40", "kobe": "JP-28", "sendai": "JP-04",
    "hokkaido": "JP-01", "okinawa": "JP-47",
    # China
    "beijing": "CN-BJ", "shanghai": "CN-SH",
    "chongqing": "CN-CQ", "tianjin": "CN-TJ",
    "guangdong": "CN-GD", "guangzhou": "CN-GD",
    "sichuan": "CN-SC", "chengdu": "CN-SC",
    "shandong": "CN-SD", "henan": "CN-HA",
    "xinjiang": "CN-XJ", "tibet": "CN-XZ",
    "hong kong": "CN-HK", "macau": "CN-MO",
    "inner mongolia": "CN-NM",
    "hubei": "CN-HB", "wuhan": "CN-HB",
    # India — states
    "andhra pradesh": "IN-AP", "visakhapatnam": "IN-AP", "vijayawada": "IN-AP",
    "arunachal pradesh": "IN-AR",
    "assam": "IN-AS", "guwahati": "IN-AS",
    "bihar": "IN-BR", "patna": "IN-BR",
    "chhattisgarh": "IN-CT", "raipur": "IN-CT",
    "goa": "IN-GA",
    "gujarat": "IN-GJ", "ahmedabad": "IN-GJ", "surat": "IN-GJ",
    "vadodara": "IN-GJ", "rajkot": "IN-GJ",
    "haryana": "IN-HR", "faridabad": "IN-HR", "gurugram": "IN-HR", "gurgaon": "IN-HR",
    "himachal pradesh": "IN-HP", "shimla": "IN-HP",
    "jharkhand": "IN-JH", "ranchi": "IN-JH", "jamshedpur": "IN-JH",
    "karnataka": "IN-KA", "bengaluru": "IN-KA", "bangalore": "IN-KA",
    "mysuru": "IN-KA", "mysore": "IN-KA", "mangaluru": "IN-KA", "hubli": "IN-KA",
    "hubballi-dharwad": "IN-KA", "hubballi dharwad": "IN-KA",
    "belagavi": "IN-KA", "belgaum": "IN-KA",
    "davanagere": "IN-KA", "ballari": "IN-KA", "bellary": "IN-KA",
    "shimoga": "IN-KA", "shivamogga": "IN-KA", "tumkur": "IN-KA",
    "bidar": "IN-KA", "raichur": "IN-KA", "udupi": "IN-KA",
    "gulbarga": "IN-KA", "kalaburagi": "IN-KA", "hassan": "IN-KA",
    "kerala": "IN-KL", "thiruvananthapuram": "IN-KL", "kochi": "IN-KL",
    "kozhikode": "IN-KL", "thrissur": "IN-KL",
    "madhya pradesh": "IN-MP", "bhopal": "IN-MP", "indore": "IN-MP", "gwalior": "IN-MP",
    "maharashtra": "IN-MH", "mumbai": "IN-MH", "pune": "IN-MH",
    "nagpur": "IN-MH", "nashik": "IN-MH", "aurangabad": "IN-MH",
    "solapur": "IN-MH", "kolhapur": "IN-MH", "thane": "IN-MH",
    "navi mumbai": "IN-MH", "amravati": "IN-MH", "akola": "IN-MH",
    "ahmednagar": "IN-MH", "satara": "IN-MH", "sangli": "IN-MH",
    "latur": "IN-MH", "jalgaon": "IN-MH", "dhule": "IN-MH",
    "ulhasnagar": "IN-MH", "bhiwandi": "IN-MH", "panvel": "IN-MH",
    "malegaon": "IN-MH", "nanded": "IN-MH", "osmanabad": "IN-MH",
    "wardha": "IN-MH",
    "manipur": "IN-MN",
    "meghalaya": "IN-ML",
    "mizoram": "IN-MZ",
    "nagaland": "IN-NL",
    "odisha": "IN-OR", "orissa": "IN-OR", "bhubaneswar": "IN-OR",
    "punjab": "IN-PB", "ludhiana": "IN-PB", "amritsar": "IN-PB",
    "rajasthan": "IN-RJ", "jaipur": "IN-RJ", "jodhpur": "IN-RJ", "udaipur": "IN-RJ",
    "sikkim": "IN-SK",
    # Tamil Nadu — exhaustive city list (critical for LPG/subsidy test case)
    "tamil nadu": "IN-TN", "tamilnadu": "IN-TN",
    "chennai": "IN-TN", "madras": "IN-TN",
    "madurai": "IN-TN", "coimbatore": "IN-TN", "salem": "IN-TN",
    "tiruchirappalli": "IN-TN", "trichy": "IN-TN",
    "tiruppur": "IN-TN", "tirupur": "IN-TN",
    "vellore": "IN-TN", "erode": "IN-TN",
    "thoothukudi": "IN-TN", "tuticorin": "IN-TN",
    "tirunelveli": "IN-TN", "thanjavur": "IN-TN",
    "tiruvannamalai": "IN-TN", "karur": "IN-TN",
    "dindigul": "IN-TN", "cuddalore": "IN-TN",
    "nagercoil": "IN-TN", "kumbakonam": "IN-TN",
    "sivakasi": "IN-TN", "pollachi": "IN-TN",
    "hosur": "IN-TN", "ambattur": "IN-TN", "tambaram": "IN-TN",
    "kanchipuram": "IN-TN", "rajapalayam": "IN-TN",
    "sriperumbudur": "IN-TN", "villupuram": "IN-TN",
    "namakkal": "IN-TN", "pudukkottai": "IN-TN",
    "virudhunagar": "IN-TN",
    "telangana": "IN-TS", "hyderabad": "IN-TS", "warangal": "IN-TS",
    "tripura": "IN-TR",
    "uttar pradesh": "IN-UP", "lucknow": "IN-UP", "kanpur": "IN-UP",
    "varanasi": "IN-UP", "agra": "IN-UP", "prayagraj": "IN-UP",
    "allahabad": "IN-UP", "meerut": "IN-UP", "noida": "IN-UP",
    "uttarakhand": "IN-UK", "dehradun": "IN-UK",
    "west bengal": "IN-WB", "kolkata": "IN-WB", "calcutta": "IN-WB",
    "howrah": "IN-WB", "durgapur": "IN-WB", "kharagpur": "IN-WB",
    "bardhaman": "IN-WB", "burdwan": "IN-WB", "haldia": "IN-WB",
    "malda": "IN-WB", "jalpaiguri": "IN-WB", "kalyani": "IN-WB",
    "barasat": "IN-WB", "raiganj": "IN-WB", "siliguri": "IN-WB",
    "delhi": "IN-DL", "new delhi": "IN-DL",
    "jammu and kashmir": "IN-JK", "jammu kashmir": "IN-JK", "srinagar": "IN-JK",
    "chandigarh": "IN-CH",
    # Australia
    "new south wales": "AU-NSW", "sydney": "AU-NSW",
    "victoria": "AU-VIC", "melbourne": "AU-VIC",
    "queensland": "AU-QLD", "brisbane": "AU-QLD",
    "western australia": "AU-WA", "perth": "AU-WA",
    "south australia": "AU-SA", "adelaide": "AU-SA",
    "tasmania": "AU-TAS", "hobart": "AU-TAS",
    "northern territory": "AU-NT", "darwin": "AU-NT",
    "australian capital territory": "AU-ACT", "canberra": "AU-ACT",
    # South Korea
    "seoul": "KR-36", "busan": "KR-26", "incheon": "KR-28",
    "daegu": "KR-27", "daejeon": "KR-30", "gwangju": "KR-29",
    "jeju": "KR-67",
    # Ukraine
    "kyiv": "UA-30", "kiev": "UA-30",
    "kharkiv": "UA-63", "odesa": "UA-51", "odessa": "UA-51",
    "lviv": "UA-46", "dnipro": "UA-12", "zaporizhzhia": "UA-23",
    "donetsk": "UA-14", "luhansk": "UA-09", "crimea": "UA-43",
    # Nigeria
    "lagos": "NG-LA", "abuja": "NG-FC",
    "kano": "NG-KN", "ibadan": "NG-OY",
    "rivers": "NG-RI", "port harcourt": "NG-RI",
    "oyo": "NG-OY", "kaduna": "NG-KD",
    # South Africa
    "gauteng": "ZA-GT", "johannesburg": "ZA-GT",
    "western cape": "ZA-WC", "cape town": "ZA-WC",
    "kwazulu-natal": "ZA-NL", "durban": "ZA-NL",
    "eastern cape": "ZA-EC",
    "limpopo": "ZA-LP",
    "mpumalanga": "ZA-MP",
    "free state": "ZA-FS",
    "north west": "ZA-NW",
    "northern cape": "ZA-NC",
    # Egypt
    "cairo": "EG-C", "giza": "EG-GZ",
    "alexandria": "EG-ALX",
    "luxor": "EG-LX", "aswan": "EG-ASN",
    # Saudi Arabia
    "riyadh": "SA-01", "mecca": "SA-02", "makkah": "SA-02",
    "medina": "SA-03", "jeddah": "SA-02",
    "eastern province": "SA-05",
    # Israel
    "tel aviv": "IL-TA", "jerusalem": "IL-JM",
    "haifa": "IL-HA",
}


def _normalise(text: str) -> str:
    """Lower-case, strip accents, collapse non-alpha to spaces, strip."""
    nfkd = unicodedata.normalize("NFKD", text)
    ascii_str = nfkd.encode("ascii", errors="ignore").decode("ascii")
    return re.sub(r"[^a-z0-9 ]", " ", ascii_str.lower()).strip()


class GeoResolver:
    """
    Resolves (country_code, region_name) to (latitude, longitude).

    Parameters
    ----------
    cache_path : Path or None
        Path to geo_data_cache.json.  Defaults to the file in this package.
    """

    _DEFAULT_CACHE = Path(__file__).parent / "geo_data_cache.json"

    def __init__(self, cache_path: Optional[Path] = None) -> None:
        path = cache_path or self._DEFAULT_CACHE
        try:
            with open(path, encoding="utf-8") as f:
                raw: dict[str, list[float]] = json.load(f)
            # Normalise keys to upper-case
            self._subdivisions: dict[str, Tuple[float, float]] = {
                k.upper(): (v[0], v[1]) for k, v in raw.items()
            }
        except FileNotFoundError:
            logger.warning(
                "geo_data_cache.json not found at %s — geo resolution disabled.", path
            )
            self._subdivisions = {}

        logger.info("GeoResolver: loaded %d subdivision centroids.", len(self._subdivisions))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_coordinates(
        self,
        country_code: str,
        region_name: Optional[str] = None,
    ) -> Optional[Tuple[float, float]]:
        """
        Return (latitude, longitude) for the given country + optional region.

        Waterfall:
          1. Exact ISO 3166-2 code in cache        ("US-TX")
          2. Name normalisation → code → cache     ("Texas" → "US-TX")
          3. Country centroid                       ("US")
          4. None if country_code is unknown

        Parameters
        ----------
        country_code : str
            ISO alpha-2 country code (e.g. "US", "gb").  Case-insensitive.
        region_name : str or None
            Free-text region/state/city name as it appears in news text.
        """
        country = country_code.upper()

        # ── Step 1: try explicit ISO 3166-2 code passed as region_name ────
        if region_name:
            candidate = region_name.upper()
            if candidate in self._subdivisions:
                return self._subdivisions[candidate]
            # Also try "CC-NAME" form when region_name already includes country
            if "-" not in candidate:
                composite = f"{country}-{candidate}"
                if composite in self._subdivisions:
                    return self._subdivisions[composite]

        # ── Step 2: name normalisation lookup ─────────────────────────────
        if region_name:
            norm = _normalise(region_name)
            code = _NAME_TO_CODE.get(norm)
            if code and code.upper() in self._subdivisions:
                return self._subdivisions[code.upper()]

            # Try prefix search (e.g. "West Virginia" → strip state suffix)
            # Remove common suffixes that appear in news text
            for suffix in (" state", " province", " region", " oblast",
                           " prefecture", " county", " district"):
                stripped = norm.removesuffix(suffix)
                if stripped != norm:
                    code2 = _NAME_TO_CODE.get(stripped)
                    if code2 and code2.upper() in self._subdivisions:
                        return self._subdivisions[code2.upper()]

        # ── Step 3: country centroid ───────────────────────────────────────
        # If a region_name was given but couldn't be resolved, apply a small
        # deterministic scatter (±3°) so stories don't all stack at the exact
        # centroid — and never land at Null Island (0, 0).
        if country in _COUNTRY_CENTROIDS:
            base_lat, base_lng = _COUNTRY_CENTROIDS[country]
            if region_name:
                seed = sum(ord(c) for c in region_name.upper())
                lat_off = (((seed * 1103515245) & 0xFFFF) / 0xFFFF) * 6 - 3   # ±3°
                lng_off = (((seed * 22695477 + 0x3039) & 0xFFFF) / 0xFFFF) * 6 - 3
                return (base_lat + lat_off, base_lng + lng_off)
            return (base_lat, base_lng)

        # ── Step 4: unknown ────────────────────────────────────────────────
        logger.debug(
            "GeoResolver: no coordinates for country=%s region=%s",
            country_code, region_name,
        )
        return None
