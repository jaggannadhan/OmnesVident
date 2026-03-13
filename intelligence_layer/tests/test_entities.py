import pytest
from intelligence_layer.entities import extract_mentioned_regions


def test_primary_region_always_included():
    regions = extract_mentioned_regions("Some headline", "", "US")
    assert "US" in regions


def test_detects_explicit_country_name():
    regions = extract_mentioned_regions("Germany signs trade deal with Japan", "", "DE")
    assert "JP" in regions
    assert "DE" in regions


def test_detects_adjective_form():
    regions = extract_mentioned_regions("Russian forces advance", "", "UA")
    assert "RU" in regions


def test_does_not_duplicate_primary_region():
    regions = extract_mentioned_regions("UK government announces policy", "", "GB")
    assert regions.count("GB") == 1


def test_multi_country_headline():
    regions = extract_mentioned_regions(
        "US and China reach agreement as Russia watches", "", "US"
    )
    assert "CN" in regions
    assert "RU" in regions
    assert "US" in regions


def test_no_country_mentioned_returns_only_primary():
    regions = extract_mentioned_regions("Local council approves budget", "", "AU")
    assert regions == ["AU"]


def test_primary_is_first_in_result():
    regions = extract_mentioned_regions("France and Germany in talks", "", "FR")
    assert regions[0] == "FR"


def test_case_insensitive_matching():
    regions = extract_mentioned_regions("JAPAN holds election", "", "JP")
    assert "JP" in regions
