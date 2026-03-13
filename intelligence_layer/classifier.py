"""
Lightweight keyword-based topic classifier.

Maps a story's title + snippet text to one of eight canonical categories.
Each category has a scored keyword list.  The category with the most keyword
hits wins.  Ties are broken by keyword weight (each entry carries a score).

Design rationale: zero external model dependencies, deterministic output,
sub-millisecond latency per event, easy to extend.  A transformer-based
zero-shot model can replace this in a later module once the data pipeline
is stable.
"""

import logging
import re
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Category taxonomy
# ---------------------------------------------------------------------------

CATEGORIES = [
    "WORLD",
    "POLITICS",
    "TECHNOLOGY",
    "BUSINESS",
    "SCIENCE",
    "HEALTH",
    "ENTERTAINMENT",
    "SPORTS",
]

FALLBACK_CATEGORY = "WORLD"

# Each entry: (keyword_pattern, score)
# Higher score = stronger signal.  Patterns are compiled as whole-word
# case-insensitive regexes at module import time.
_RAW_RULES: Dict[str, List[Tuple[str, int]]] = {
    "POLITICS": [
        (r"elect(ion|ed|oral)", 3),
        (r"president(ial)?", 3),
        (r"parliament", 3),
        (r"senator?", 3),
        (r"congress(man|woman|ional)?", 3),
        (r"legislat(ion|ure|ive)", 3),
        (r"prime\s+minister", 3),
        (r"political\s+part(y|ies)", 2),
        (r"democrat(ic)?", 2),
        (r"republican", 2),
        (r"government", 2),
        (r"diplomac(y|tic)", 2),
        (r"sanction", 2),
        (r"treaty", 2),
        (r"referendum", 3),
        (r"minister", 1),
        (r"vote|voter|voting", 2),
        (r"policy|policies", 1),
        (r"campaign", 2),
        (r"white\s+house", 2),
        (r"kremlin", 2),
    ],
    "TECHNOLOGY": [
        (r"artificial\s+intelligence|ai\b", 3),
        (r"machine\s+learning", 3),
        (r"software", 2),
        (r"cybersecurit(y|ies)", 3),
        (r"hack(er|ing|ed)?", 2),
        (r"data\s+breach", 3),
        (r"smartphone", 2),
        (r"silicon\s+valley", 2),
        (r"startup", 2),
        (r"cloud\s+computing", 3),
        (r"semiconductor", 3),
        (r"robot(ics)?", 2),
        (r"space(x)?|rocket|satellite", 2),
        (r"5g|6g", 2),
        (r"tech\s+(giant|company|firm)", 2),
        (r"apple|google|microsoft|meta|amazon|nvidia|openai", 2),
        (r"algorithm", 2),
        (r"encryption", 2),
        (r"autonomous\s+vehicle|self.driving", 3),
        (r"quantum\s+computing", 3),
    ],
    "BUSINESS": [
        (r"stock\s+market|stock\s+exchange", 3),
        (r"nasdaq|nyse|dow\s+jones|s&p\s*500", 3),
        (r"gdp|inflation|interest\s+rate", 3),
        (r"merger|acquisition", 3),
        (r"ipo\b", 3),
        (r"earnings|revenue|profit|loss", 2),
        (r"central\s+bank|federal\s+reserve|imf|world\s+bank", 3),
        (r"trade\s+(war|deal|deficit|surplus)", 3),
        (r"supply\s+chain", 2),
        (r"bankruptcy|insolvency", 3),
        (r"cryptocurrency|bitcoin|ethereum", 2),
        (r"hedge\s+fund|private\s+equity", 3),
        (r"recession|economic\s+growth", 3),
        (r"tariff", 2),
        (r"invest(or|ment|ing)", 2),
        (r"unemployment|job(s)?\s+(cut|loss|market)", 2),
    ],
    "SCIENCE": [
        (r"research(er|ers)?", 1),
        (r"study\s+finds|study\s+shows|new\s+study", 2),
        (r"scientist(s)?", 2),
        (r"physics|chemistry|biolog(y|ical)", 3),
        (r"climate\s+change|global\s+warming", 3),
        (r"fossil", 2),
        (r"astronaut|nasa|esa\b", 3),
        (r"genome|dna|rna\b", 3),
        (r"particle\s+accelerator|cern\b", 3),
        (r"asteroid|comet|exoplanet", 3),
        (r"experiment", 2),
        (r"peer.reviewed", 3),
        (r"carbon\s+emission", 2),
        (r"renewable\s+energy|solar\s+panel|wind\s+turbine", 2),
        (r"evolution", 2),
        (r"species", 2),
    ],
    "HEALTH": [
        (r"hospital|clinic|nhs\b", 2),
        (r"doctor|physician|surgeon|nurse", 2),
        (r"cancer|tumor|oncolog", 3),
        (r"pandemic|epidemic|outbreak", 3),
        (r"vaccine|vaccination", 3),
        (r"virus|bacterial|pathogen", 2),
        (r"mental\s+health|depression|anxiety", 3),
        (r"drug\s+(trial|approval|shortage)", 3),
        (r"fda\b|who\b|cdc\b", 2),
        (r"public\s+health", 2),
        (r"surgery|transplant", 2),
        (r"obesity|diabetes|alzheimer", 3),
        (r"pharmaceutical|biotech", 2),
        (r"mortality|life\s+expectancy", 2),
        (r"antibiotic\s+resistance", 3),
    ],
    "ENTERTAINMENT": [
        (r"movie|film|cinema|box\s+office", 2),
        (r"oscar|grammy|bafta|emmy|golden\s+globe", 3),
        (r"celebrity|star|actor|actress", 2),
        (r"album|single|tour|concert", 2),
        (r"netflix|hbo|disney\+?|streaming", 2),
        (r"tv\s+show|television\s+series|season\s+\d", 2),
        (r"fashion|runway|vogue", 2),
        (r"book\s+(deal|release|award)", 2),
        (r"video\s+game|esports", 2),
        (r"social\s+media\s+influencer", 2),
        (r"hollywood|bollywood", 2),
        (r"music\s+(video|festival|chart)", 2),
    ],
    "SPORTS": [
        (r"world\s+cup|championship|league\s+title", 3),
        (r"olympic(s)?", 3),
        (r"football|soccer|basketball|baseball|cricket|tennis|golf", 2),
        (r"nfl|nba|mlb|nhl|premier\s+league|la\s+liga|serie\s+a", 3),
        (r"athlete|player|coach|manager", 1),
        (r"match|game\s+\d|fixture", 2),
        (r"score|goal|touchdown|home\s+run", 2),
        (r"transfer|signing|contract\s+extension", 2),
        (r"injury|suspension|ban", 1),
        (r"playoff|semifinal|final|quarterfinal", 2),
        (r"formula\s+1|f1\b|grand\s+prix", 3),
        (r"marathon|triathlon|cycling\s+race", 2),
    ],
    "WORLD": [
        (r"war|conflict|ceasefire", 3),
        (r"military|troops|soldier", 2),
        (r"refugee|migrant|asylum", 2),
        (r"earthquake|flood|hurricane|wildfire|tsunami", 3),
        (r"united\s+nations|un\s+security\s+council", 3),
        (r"nato\b|eu\b|g7\b|g20\b", 2),
        (r"coup|protest|civil\s+unrest", 3),
        (r"terror(ist|ism|attack)", 3),
        (r"murder|shooting|bombing", 2),
        (r"humanitarian|aid\s+worker", 2),
        (r"foreign\s+(affairs|policy|minister)", 2),
    ],
}

# Compile all patterns once at import time
_COMPILED_RULES: Dict[str, List[Tuple[re.Pattern, int]]] = {
    category: [
        (re.compile(r"\b" + pattern + r"\b", re.IGNORECASE), score)
        for pattern, score in rules
    ]
    for category, rules in _RAW_RULES.items()
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def classify(title: str, snippet: str = "") -> str:
    """
    Return the best-matching category label for the given text.

    Scoring:
    - Matches in the title are weighted ×2 (titles are denser signals).
    - Matches in the snippet are weighted ×1.
    - The category with the highest total score wins.
    - Ties are resolved alphabetically (deterministic).
    - Falls back to WORLD if no keywords match at all.
    """
    text_title = title.lower()
    text_snippet = snippet.lower()

    scores: Dict[str, int] = {cat: 0 for cat in CATEGORIES}

    for category, rules in _COMPILED_RULES.items():
        for pattern, score in rules:
            if pattern.search(text_title):
                scores[category] += score * 2   # title bonus
            if text_snippet and pattern.search(text_snippet):
                scores[category] += score

    best_category = max(scores, key=lambda c: (scores[c], c))

    if scores[best_category] == 0:
        logger.debug("No keyword match for: '%s' — defaulting to %s", title[:80], FALLBACK_CATEGORY)
        return FALLBACK_CATEGORY

    return best_category


def classify_with_scores(title: str, snippet: str = "") -> Dict[str, int]:
    """Return the full score breakdown — useful for debugging and testing."""
    text_title = title.lower()
    text_snippet = snippet.lower()

    scores: Dict[str, int] = {cat: 0 for cat in CATEGORIES}

    for category, rules in _COMPILED_RULES.items():
        for pattern, score in rules:
            if pattern.search(text_title):
                scores[category] += score * 2
            if text_snippet and pattern.search(text_snippet):
                scores[category] += score

    return scores
