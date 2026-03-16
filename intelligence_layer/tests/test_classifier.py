import pytest
from intelligence_layer.classifier import classify, classify_with_scores, CATEGORIES


# ---------------------------------------------------------------------------
# Category coverage — one clear-signal headline per category
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("title, snippet, expected", [
    (
        "Presidential election results certified by Congress",
        "Voters across the nation turned out in record numbers.",
        "POLITICS",
    ),
    (
        "OpenAI releases new AI model with quantum computing capabilities",
        "The startup announced the software at Silicon Valley summit.",
        "SCIENCE_TECH",
    ),
    (
        "Stock market hits record high as Fed cuts interest rates",
        "The Nasdaq and S&P 500 both surged following the central bank decision.",
        "BUSINESS",
    ),
    (
        "Scientists discover new exoplanet orbiting distant star",
        "NASA researchers published the peer-reviewed findings on climate change.",
        "SCIENCE_TECH",
    ),
    (
        "WHO declares new pandemic as vaccine rollout begins",
        "Hospitals report rising cases; the FDA fast-tracked drug approval.",
        "HEALTH",
    ),
    (
        "Oscar nominations announced for best film of the year",
        "Hollywood studios celebrate as Netflix leads with streaming hits.",
        "ENTERTAINMENT",
    ),
    (
        "World Cup final: Brazil beats Germany in penalty shootout",
        "The Premier League champions lifted the trophy at the Olympic stadium.",
        "SPORTS",
    ),
    (
        "UN Security Council condemns military coup and civil unrest",
        "NATO called for ceasefire as troops crossed the border.",
        "WORLD",
    ),
])
def test_classify_category(title, snippet, expected):
    result = classify(title, snippet)
    assert result == expected, (
        f"Expected {expected}, got {result}. "
        f"Scores: {classify_with_scores(title, snippet)}"
    )


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_no_keyword_match_falls_back_to_world():
    result = classify("Untitled lorem ipsum dolor sit amet", "")
    assert result == "WORLD"

def test_title_weighted_higher_than_snippet():
    # Title is pure SPORTS, snippet is pure HEALTH — SPORTS should win (2× weight)
    scores = classify_with_scores(
        "Premier League match kicks off",
        "Hospital reports rising cancer cases.",
    )
    assert scores["SPORTS"] > scores["HEALTH"]

def test_output_always_in_canonical_set():
    titles = [
        "EU summit on trade tariffs",
        "New smartphone released by Apple",
        "Olympic runner breaks world record",
        "Earthquake devastates coastal town",
    ]
    for title in titles:
        assert classify(title) in CATEGORIES

def test_classify_with_scores_returns_all_categories():
    scores = classify_with_scores("Breaking news", "")
    assert set(scores.keys()) == set(CATEGORIES)
