"""
geo_tagger.py — City-to-State/Province Mapper

Scans a story's title + snippet for known city names and returns the
corresponding ISO 3166-2 subdivision code (e.g. "IN-TN").

`TagEnhancer` is the primary interface: it both tags a story and can update
the `region_code` on the lead NewsEvent so downstream dedup + filtering
operates at subdivision rather than country granularity.

Coverage: 300+ cities across the 7 high-res countries — US, IN, CN, BR, CA, AU, ZA.

Geo-tagging accuracy rules (local → state → country hierarchy):
  A  Country-lock   — only match subdivisions within the story's own country.
                      A BBC story about the Kennedy Center won't be misfiled as
                      "US-NV" just because "Nevada" appears in the snippet.
  B  Title-first    — title is scanned before snippet; if a city appears in the
                      title it is the primary subject and wins outright.
  C  Word-boundary  — \\b anchors prevent partial-word false positives (e.g.
                      "in" matching "international", "or" matching "order").
"""

import re
from typing import Optional, Tuple

from ingestion_engine.core.models import NewsEvent

# ---------------------------------------------------------------------------
# City → ISO 3166-2 subdivision mapping
# ---------------------------------------------------------------------------

CITY_TO_STATE: dict[str, str] = {

    # ── United States ────────────────────────────────────────────────────
    # California
    "Los Angeles":    "US-CA", "San Francisco": "US-CA", "San Diego":     "US-CA",
    "Sacramento":     "US-CA", "Oakland":       "US-CA", "San Jose":      "US-CA",
    "Fresno":         "US-CA", "Long Beach":    "US-CA", "Bakersfield":   "US-CA",
    "Anaheim":        "US-CA", "Santa Ana":     "US-CA", "Riverside":     "US-CA",
    "Stockton":       "US-CA", "Irvine":        "US-CA", "Chula Vista":   "US-CA",
    "Modesto":        "US-CA", "Fontana":       "US-CA", "Moreno Valley": "US-CA",
    "Glendale":       "US-CA", "Huntington Beach":"US-CA","Santa Clarita": "US-CA",
    "Garden Grove":   "US-CA", "Oceanside":     "US-CA", "Rancho Cucamonga":"US-CA",
    "Elk Grove":      "US-CA", "Hayward":       "US-CA", "Lancaster":     "US-CA",
    "Palmdale":       "US-CA", "Salinas":       "US-CA", "Sunnyvale":     "US-CA",
    "Pomona":         "US-CA", "Escondido":     "US-CA", "Torrance":      "US-CA",
    "Pasadena":       "US-CA", "Santa Rosa":    "US-CA", "Fremont":       "US-CA",
    # Texas
    "Houston":        "US-TX", "Dallas":        "US-TX", "Austin":        "US-TX",
    "San Antonio":    "US-TX", "Fort Worth":    "US-TX", "El Paso":       "US-TX",
    "Arlington":      "US-TX", "Corpus Christi":"US-TX", "Plano":         "US-TX",
    "Lubbock":        "US-TX", "Laredo":        "US-TX", "Irving":        "US-TX",
    "Garland":        "US-TX", "Amarillo":      "US-TX", "Grand Prairie": "US-TX",
    "McAllen":        "US-TX", "Killeen":       "US-TX", "Frisco":        "US-TX",
    "Waco":           "US-TX", "Beaumont":      "US-TX", "Midland":       "US-TX",
    "Odessa":         "US-TX", "Abilene":       "US-TX", "Brownsville":   "US-TX",
    "Denton":         "US-TX", "Pasadena":      "US-TX", "Mesquite":      "US-TX",
    "Carrollton":     "US-TX", "Round Rock":    "US-TX", "McKinney":      "US-TX",
    # New York
    "New York":       "US-NY", "Buffalo":       "US-NY", "Albany":        "US-NY",
    "Rochester":      "US-NY", "Syracuse":      "US-NY", "Yonkers":       "US-NY",
    "New York City":  "US-NY", "Brooklyn":      "US-NY", "Manhattan":     "US-NY",
    "Queens":         "US-NY", "Bronx":         "US-NY", "Staten Island": "US-NY",
    # Florida
    "Miami":          "US-FL", "Orlando":       "US-FL", "Tampa":         "US-FL",
    "Jacksonville":   "US-FL", "Tallahassee":   "US-FL", "St. Petersburg":"US-FL",
    "Fort Lauderdale":"US-FL", "Hialeah":       "US-FL", "Gainesville":   "US-FL",
    "Port St. Lucie": "US-FL", "Pembroke Pines":"US-FL", "Cape Coral":    "US-FL",
    "Lakeland":       "US-FL", "Clearwater":    "US-FL", "West Palm Beach":"US-FL",
    "Coral Springs":  "US-FL", "Miramar":       "US-FL", "Pompano Beach": "US-FL",
    "Fort Myers":     "US-FL", "Daytona Beach": "US-FL", "Palm Bay":      "US-FL",
    # Washington
    "Seattle":        "US-WA", "Spokane":       "US-WA", "Tacoma":        "US-WA",
    "Bellevue":       "US-WA", "Olympia":       "US-WA",
    # Illinois
    "Chicago":        "US-IL", "Aurora":        "US-IL", "Naperville":    "US-IL",
    # Arizona
    "Phoenix":        "US-AZ", "Tucson":        "US-AZ", "Mesa":          "US-AZ",
    "Scottsdale":     "US-AZ", "Chandler":      "US-AZ", "Tempe":         "US-AZ",
    # Colorado
    "Denver":         "US-CO", "Colorado Springs": "US-CO", "Aurora":     "US-CO",
    "Fort Collins":   "US-CO", "Boulder":       "US-CO",
    # Other US states (one or two cities each)
    "Las Vegas":      "US-NV", "Henderson":     "US-NV", "Reno":          "US-NV",
    "Atlanta":        "US-GA", "Savannah":      "US-GA", "Augusta":       "US-GA",
    "Nashville":      "US-TN", "Memphis":       "US-TN", "Knoxville":     "US-TN",
    "Boston":         "US-MA", "Worcester":     "US-MA", "Cambridge":     "US-MA",
    "Washington":     "US-DC",
    "Philadelphia":   "US-PA", "Pittsburgh":    "US-PA", "Allentown":     "US-PA",
    "Detroit":        "US-MI", "Grand Rapids":  "US-MI", "Warren":        "US-MI",
    "Minneapolis":    "US-MN", "St. Paul":      "US-MN",
    "Portland":       "US-OR", "Eugene":        "US-OR",
    "Salt Lake City": "US-UT", "West Valley":   "US-UT",
    "Charlotte":      "US-NC", "Raleigh":       "US-NC", "Durham":        "US-NC",
    "Columbus":       "US-OH", "Cleveland":     "US-OH", "Cincinnati":    "US-OH",
    "Indianapolis":   "US-IN", "Fort Wayne":    "US-IN",
    "Kansas City":    "US-MO", "St. Louis":     "US-MO",
    "New Orleans":    "US-LA", "Baton Rouge":   "US-LA",
    "Birmingham":     "US-AL", "Montgomery":    "US-AL",
    "Louisville":     "US-KY", "Lexington":     "US-KY",
    "Richmond":       "US-VA", "Virginia Beach": "US-VA", "Norfolk":      "US-VA",
    "Baltimore":      "US-MD",
    "Milwaukee":      "US-WI", "Madison":       "US-WI",
    "Albuquerque":    "US-NM", "Santa Fe":      "US-NM",
    "Omaha":          "US-NE",
    "Oklahoma City":  "US-OK", "Tulsa":         "US-OK",
    "Honolulu":       "US-HI",
    "Anchorage":      "US-AK",
    "Charleston":     "US-SC", "Columbia":      "US-SC",
    "Providence":     "US-RI",
    "Hartford":       "US-CT",
    "Des Moines":     "US-IA",
    "Little Rock":    "US-AR",
    "Jackson":        "US-MS",

    # ── India ────────────────────────────────────────────────────────────
    # Maharashtra — Tier 1 + Tier 2/3 divisional HQs and industrial towns
    "Navi Mumbai":    "IN-MH", "Mumbai":        "IN-MH", "Pune":          "IN-MH",
    "Nagpur":         "IN-MH", "Nashik":        "IN-MH", "Aurangabad":    "IN-MH",
    "Solapur":        "IN-MH", "Kolhapur":      "IN-MH", "Thane":         "IN-MH",
    "Amravati":       "IN-MH", "Akola":         "IN-MH", "Ahmednagar":    "IN-MH",
    "Satara":         "IN-MH", "Sangli":        "IN-MH", "Latur":         "IN-MH",
    "Jalgaon":        "IN-MH", "Dhule":         "IN-MH", "Ulhasnagar":    "IN-MH",
    "Bhiwandi":       "IN-MH", "Panvel":        "IN-MH", "Malegaon":      "IN-MH",
    "Nanded":         "IN-MH", "Osmanabad":     "IN-MH", "Wardha":        "IN-MH",
    # Delhi
    "New Delhi":      "IN-DL", "Delhi":         "IN-DL",
    # Karnataka — Tier 1 + Tier 2/3 district towns
    "Hubballi-Dharwad":"IN-KA","Bengaluru":     "IN-KA", "Bangalore":     "IN-KA",
    "Mysuru":         "IN-KA", "Mangaluru":     "IN-KA", "Hubli":         "IN-KA",
    "Dharwad":        "IN-KA", "Belagavi":      "IN-KA", "Belgaum":       "IN-KA",
    "Davanagere":     "IN-KA", "Ballari":       "IN-KA", "Bellary":       "IN-KA",
    "Shimoga":        "IN-KA", "Shivamogga":    "IN-KA", "Tumkur":        "IN-KA",
    "Bidar":          "IN-KA", "Raichur":       "IN-KA", "Udupi":         "IN-KA",
    "Gulbarga":       "IN-KA", "Kalaburagi":    "IN-KA", "Hassan":        "IN-KA",
    # Tamil Nadu — Tier 1 + Tier 2/3 district headquarters and industrial towns
    "Chennai":        "IN-TN", "Coimbatore":    "IN-TN", "Madurai":       "IN-TN",
    "Salem":          "IN-TN", "Tiruchirappalli":"IN-TN", "Tiruppur":     "IN-TN",
    "Trichy":         "IN-TN", "Tirunelveli":   "IN-TN", "Erode":         "IN-TN",
    "Vellore":        "IN-TN", "Thoothukudi":   "IN-TN", "Tuticorin":     "IN-TN",
    "Thanjavur":      "IN-TN", "Dindigul":      "IN-TN", "Tiruvannamalai":"IN-TN",
    "Cuddalore":      "IN-TN", "Karur":         "IN-TN", "Nagercoil":     "IN-TN",
    "Kumbakonam":     "IN-TN", "Sivakasi":      "IN-TN", "Pollachi":      "IN-TN",
    "Hosur":          "IN-TN", "Ambattur":      "IN-TN", "Tambaram":      "IN-TN",
    "Kanchipuram":    "IN-TN", "Rajapalayam":   "IN-TN", "Sriperumbudur": "IN-TN",
    "Villupuram":     "IN-TN", "Namakkal":      "IN-TN", "Tirupur":       "IN-TN",
    "Pudukkottai":    "IN-TN", "Virudhunagar":  "IN-TN", "Madras":        "IN-TN",
    # West Bengal — Tier 1 + Tier 2 industrial belt
    "Kolkata":        "IN-WB", "Howrah":        "IN-WB", "Durgapur":      "IN-WB",
    "Asansol":        "IN-WB", "Siliguri":      "IN-WB", "Kharagpur":     "IN-WB",
    "Bardhaman":      "IN-WB", "Burdwan":       "IN-WB", "Haldia":        "IN-WB",
    "Malda":          "IN-WB", "Jalpaiguri":    "IN-WB", "Kalyani":       "IN-WB",
    "Barasat":        "IN-WB", "Raiganj":       "IN-WB",
    # Telangana
    "Hyderabad":      "IN-TS", "Warangal":      "IN-TS", "Nizamabad":     "IN-TS",
    # Andhra Pradesh
    "Visakhapatnam":  "IN-AP", "Vijayawada":    "IN-AP", "Guntur":        "IN-AP",
    # Gujarat
    "Ahmedabad":      "IN-GJ", "Surat":         "IN-GJ", "Vadodara":      "IN-GJ",
    "Rajkot":         "IN-GJ", "Bhavnagar":     "IN-GJ",
    # Rajasthan
    "Jaipur":         "IN-RJ", "Jodhpur":       "IN-RJ", "Kota":          "IN-RJ",
    "Bikaner":        "IN-RJ", "Udaipur":       "IN-RJ",
    # Uttar Pradesh
    "Lucknow":        "IN-UP", "Kanpur":        "IN-UP", "Varanasi":      "IN-UP",
    "Agra":           "IN-UP", "Prayagraj":     "IN-UP", "Meerut":        "IN-UP",
    "Allahabad":      "IN-UP", "Ghaziabad":     "IN-UP", "Noida":         "IN-UP",
    # Kerala
    "Thiruvananthapuram": "IN-KL", "Kochi":     "IN-KL", "Kozhikode":     "IN-KL",
    "Thrissur":       "IN-KL", "Kannur":        "IN-KL",
    # Punjab
    "Ludhiana":       "IN-PB", "Amritsar":      "IN-PB", "Jalandhar":     "IN-PB",
    # Other
    "Patna":          "IN-BR", "Ranchi":        "IN-JH", "Jamshedpur":    "IN-JH",
    "Bhopal":         "IN-MP", "Indore":        "IN-MP", "Gwalior":       "IN-MP",
    "Raipur":         "IN-CT", "Guwahati":      "IN-AS",
    "Chandigarh":     "IN-CH", "Dehradun":      "IN-UK",
    "Srinagar":       "IN-JK", "Jammu":         "IN-JK",
    "Shimla":         "IN-HP",

    # ── China ────────────────────────────────────────────────────────────
    "Beijing":        "CN-BJ",
    "Shanghai":       "CN-SH",
    # Guangdong
    "Guangzhou":      "CN-GD", "Shenzhen":      "CN-GD", "Dongguan":      "CN-GD",
    "Foshan":         "CN-GD", "Zhuhai":        "CN-GD", "Huizhou":       "CN-GD",
    # Sichuan
    "Chengdu":        "CN-SC",
    # Chongqing (municipality)
    "Chongqing":      "CN-CQ",
    # Hubei
    "Wuhan":          "CN-HB", "Yichang":       "CN-HB", "Xiangyang":     "CN-HB",
    # Shaanxi
    "Xi'an":          "CN-SN", "Xian":          "CN-SN",
    # Jiangsu
    "Nanjing":        "CN-JS", "Suzhou":        "CN-JS", "Wuxi":          "CN-JS",
    "Nantong":        "CN-JS",
    # Zhejiang
    "Hangzhou":       "CN-ZJ", "Ningbo":        "CN-ZJ", "Wenzhou":       "CN-ZJ",
    # Tianjin (municipality)
    "Tianjin":        "CN-TJ",
    # Liaoning
    "Shenyang":       "CN-LN", "Dalian":        "CN-LN",
    # Heilongjiang
    "Harbin":         "CN-HL",
    # Jilin
    "Changchun":      "CN-JL",
    # Yunnan
    "Kunming":        "CN-YN",
    # Guangxi
    "Nanning":        "CN-GX",
    # Xinjiang
    "Urumqi":         "CN-XJ",
    # Tibet
    "Lhasa":          "CN-XZ",
    # Shandong
    "Qingdao":        "CN-SD", "Jinan":         "CN-SD",
    # Henan
    "Zhengzhou":      "CN-HN", "Luoyang":       "CN-HN",
    # Anhui
    "Hefei":          "CN-AH",
    # Fujian
    "Fuzhou":         "CN-FJ", "Xiamen":        "CN-FJ",
    # Jiangxi
    "Nanchang":       "CN-JX",
    # Guizhou
    "Guiyang":        "CN-GZ",
    # Shanxi (different from Shaanxi)
    "Taiyuan":        "CN-SX",
    # Gansu
    "Lanzhou":        "CN-GS",
    # Inner Mongolia
    "Hohhot":         "CN-NM", "Baotou":        "CN-NM",

    # ── Brazil ───────────────────────────────────────────────────────────
    # São Paulo
    "São Paulo":      "BR-SP", "Sao Paulo":     "BR-SP", "Campinas":      "BR-SP",
    "Guarulhos":      "BR-SP", "Santos":        "BR-SP", "Sorocaba":      "BR-SP",
    "Ribeirão Preto": "BR-SP", "Ribeiro Preto": "BR-SP",
    # Rio de Janeiro
    "Rio de Janeiro": "BR-RJ", "Niterói":       "BR-RJ", "Nova Iguaçu":   "BR-RJ",
    # Minas Gerais
    "Belo Horizonte": "BR-MG", "Contagem":      "BR-MG", "Uberlândia":    "BR-MG",
    "Juiz de Fora":   "BR-MG", "Montes Claros": "BR-MG",
    # Ceará
    "Fortaleza":      "BR-CE", "Juazeiro":      "BR-CE", "Caucaia":       "BR-CE",
    # Bahia
    "Salvador":       "BR-BA", "Feira de Santana": "BR-BA", "Vitória da Conquista": "BR-BA",
    # Rio Grande do Sul
    "Porto Alegre":   "BR-RS", "Caxias do Sul": "BR-RS",
    # Paraná
    "Curitiba":       "BR-PR", "Londrina":      "BR-PR", "Maringá":       "BR-PR",
    # Pernambuco
    "Recife":         "BR-PE", "Olinda":        "BR-PE", "Caruaru":       "BR-PE",
    # Amazonas
    "Manaus":         "BR-AM",
    # Other
    "Brasília":       "BR-DF", "Brasilia":      "BR-DF",
    "Belém":          "BR-PA",
    "Natal":          "BR-RN",
    "Maceió":         "BR-AL",
    "Teresina":       "BR-PI",
    "Campo Grande":   "BR-MS",
    "Cuiabá":         "BR-MT",
    "Goiânia":        "BR-GO", "Goiania":       "BR-GO",
    "Florianópolis":  "BR-SC", "Joinville":     "BR-SC",
    "Vitória":        "BR-ES",
    "Aracaju":        "BR-SE",

    # ── Canada ───────────────────────────────────────────────────────────
    # Ontario
    "Toronto":        "CA-ON", "Ottawa":        "CA-ON", "Hamilton":      "CA-ON",
    "Mississauga":    "CA-ON", "Brampton":      "CA-ON", "London":        "CA-ON",
    "Markham":        "CA-ON", "Vaughan":       "CA-ON", "Kitchener":     "CA-ON",
    "Windsor":        "CA-ON", "Thunder Bay":   "CA-ON",
    # British Columbia
    "Vancouver":      "CA-BC", "Victoria":      "CA-BC", "Kelowna":       "CA-BC",
    "Abbotsford":     "CA-BC", "Surrey":        "CA-BC", "Burnaby":       "CA-BC",
    # Québec
    "Montreal":       "CA-QC", "Quebec City":   "CA-QC", "Laval":         "CA-QC",
    "Gatineau":       "CA-QC", "Longueuil":     "CA-QC",
    # Alberta
    "Calgary":        "CA-AB", "Edmonton":      "CA-AB", "Red Deer":      "CA-AB",
    "Lethbridge":     "CA-AB",
    # Other
    "Winnipeg":       "CA-MB", "Brandon":       "CA-MB",
    "Saskatoon":      "CA-SK", "Regina":        "CA-SK",
    "Halifax":        "CA-NS",
    "St. John's":     "CA-NL",
    "Fredericton":    "CA-NB", "Moncton":       "CA-NB", "Saint John":    "CA-NB",
    "Charlottetown":  "CA-PE",

    # ── Australia ────────────────────────────────────────────────────────
    # New South Wales
    "Sydney":         "AU-NSW", "Newcastle":    "AU-NSW", "Wollongong":   "AU-NSW",
    "Central Coast":  "AU-NSW", "Maitland":     "AU-NSW",
    # Victoria
    "Melbourne":      "AU-VIC", "Geelong":      "AU-VIC", "Ballarat":     "AU-VIC",
    "Bendigo":        "AU-VIC", "Shepparton":   "AU-VIC",
    # Queensland
    "Brisbane":       "AU-QLD", "Gold Coast":   "AU-QLD", "Cairns":       "AU-QLD",
    "Townsville":     "AU-QLD", "Rockhampton":  "AU-QLD", "Mackay":       "AU-QLD",
    "Toowoomba":      "AU-QLD", "Sunshine Coast": "AU-QLD",
    # Western Australia
    "Perth":          "AU-WA",  "Fremantle":    "AU-WA",  "Bunbury":      "AU-WA",
    "Mandurah":       "AU-WA",
    # South Australia
    "Adelaide":       "AU-SA",
    # Northern Territory
    "Darwin":         "AU-NT",  "Alice Springs": "AU-NT",
    # ACT
    "Canberra":       "AU-ACT",
    # Tasmania
    "Hobart":         "AU-TAS", "Launceston":   "AU-TAS",

    # ── South Africa ─────────────────────────────────────────────────────
    # Gauteng
    "Johannesburg":   "ZA-GT", "Pretoria":      "ZA-GT", "Soweto":        "ZA-GT",
    "Tshwane":        "ZA-GT", "Ekurhuleni":    "ZA-GT", "Vanderbijlpark":"ZA-GT",
    "Vereeniging":    "ZA-GT", "Krugersdorp":   "ZA-GT",
    # Western Cape
    "Cape Town":      "ZA-WC", "Stellenbosch":  "ZA-WC", "George":        "ZA-WC",
    "Paarl":          "ZA-WC",
    # KwaZulu-Natal
    "Durban":         "ZA-KZN","Pietermaritzburg": "ZA-KZN", "Richards Bay": "ZA-KZN",
    # Eastern Cape
    "Port Elizabeth": "ZA-EC", "Gqeberha":      "ZA-EC", "East London":   "ZA-EC",
    # Free State
    "Bloemfontein":   "ZA-FS", "Welkom":        "ZA-FS",
    # Northern Cape
    "Kimberley":      "ZA-NC",
    # Limpopo
    "Polokwane":      "ZA-LP",
    # Mpumalanga
    "Nelspruit":      "ZA-MP", "Mbombela":      "ZA-MP",
    # North West
    "Rustenburg":     "ZA-NW",
}

# ---------------------------------------------------------------------------
# Precompile word-boundary patterns grouped by country prefix.
# Built once at import time; used for all three accuracy fixes (A, B, C).
# ---------------------------------------------------------------------------
_CITY_PATTERNS_BY_COUNTRY: dict[str, list[tuple[re.Pattern, str]]] = {}
for _city, _code in CITY_TO_STATE.items():
    _country = _code.split("-")[0]
    _pat = re.compile(r"\b" + re.escape(_city.lower()) + r"\b", re.IGNORECASE)
    _CITY_PATTERNS_BY_COUNTRY.setdefault(_country, []).append((_pat, _code))

# Sort each country's list: longer patterns first so multi-word cities
# (e.g. "Navi Mumbai", "Rancho Cucamonga") are matched before their
# single-word components ("Mumbai", "Cucamonga"). — Module 9.5 Fix B
for _ckey in _CITY_PATTERNS_BY_COUNTRY:
    _CITY_PATTERNS_BY_COUNTRY[_ckey].sort(
        key=lambda pair: len(pair[0].pattern), reverse=True
    )

# Flat list used when no country lock is in effect
_ALL_CITY_PATTERNS: list[tuple[re.Pattern, str]] = [
    p for pl in _CITY_PATTERNS_BY_COUNTRY.values() for p in pl
]


def tag_with_state(
    title: str,
    snippet: str,
    country_lock: Optional[str] = None,
) -> Optional[str]:
    """
    Scan title (first) then snippet for a known city name.

    Returns the ISO 3166-2 subdivision code of the first match, or None.

    Args:
        title:        Story headline.
        snippet:      Story body / description.
        country_lock: ISO alpha-2 country code (e.g. "US").  When set, only
                      subdivisions within that country are considered (Fix A).
                      Pass None to search across all countries.
    """
    # A: restrict candidate set to the story's own country; unknown country → []
    if country_lock:
        patterns = _CITY_PATTERNS_BY_COUNTRY.get(country_lock.upper(), [])
    else:
        patterns = _ALL_CITY_PATTERNS

    if not patterns:
        return None

    # B + C: title first, word-boundary regex
    for pattern, code in patterns:
        if pattern.search(title):
            return code

    # B: only fall through to snippet when title had no match
    for pattern, code in patterns:
        if pattern.search(snippet):
            return code

    return None


class TagEnhancer:
    """
    Stateless city-to-subdivision tagger.

    Usage:
        tagger = TagEnhancer()
        updated_lead, subdivision = tagger.enhance(lead_event)

    `enhance()` returns a (possibly new) NewsEvent with region_code updated to
    the matched subdivision, plus the matched code (or None if no city found).
    If a city is found the lead's region_code is replaced so that downstream
    deduplication, API filtering, and globe blip placement all operate at
    subdivision resolution.
    """

    def tag(
        self,
        title: str,
        snippet: str,
        country_lock: Optional[str] = None,
    ) -> Optional[str]:
        """Return an ISO 3166-2 code if any known city appears in the text."""
        return tag_with_state(title, snippet, country_lock)

    def enhance(self, lead: NewsEvent) -> Tuple[NewsEvent, Optional[str]]:
        """
        Tag the lead event and, if a city is found within the story's own
        country, return a copy with `region_code` updated to the subdivision.

        Country lock (Fix A) is derived automatically from the existing
        region_code so cross-country misfires are impossible.
        """
        rc = lead.region_code or ""
        # "US" from "US" or "US-CA"; None if region_code is blank
        country_lock = rc.split("-")[0] or None
        sub = self.tag(lead.title, lead.snippet, country_lock)
        if sub:
            lead = lead.model_copy(update={"region_code": sub})
        return lead, sub