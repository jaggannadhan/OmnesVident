import pytest
from ingestion_engine.core.normalizer import clean_and_truncate, strip_html

# ---------------------------------------------------------------------------
# strip_html
# ---------------------------------------------------------------------------

def test_strip_html_basic():
    assert strip_html("<p>Hello <b>World</b></p>") == "Hello World"

def test_strip_html_removes_script():
    assert strip_html("<script>alert('xss')</script>Safe text") == "Safe text"

def test_strip_html_collapses_whitespace():
    assert strip_html("<p>  Too   many   spaces  </p>") == "Too many spaces"

# ---------------------------------------------------------------------------
# clean_and_truncate
# ---------------------------------------------------------------------------

def test_short_text_unchanged():
    text = "Short sentence."
    assert clean_and_truncate(text) == text

def test_html_stripped_before_truncate():
    html = "<p>" + "A" * 80 + ". " + "B" * 80 + ".</p>"
    result = clean_and_truncate(html)
    assert "<p>" not in result
    assert len(result) <= 160

def test_natural_sentence_boundary():
    # First sentence ends at char 50, well within 160
    text = ("Breaking news from the capital. " * 3) + "Extra content here."
    result = clean_and_truncate(text)
    assert len(result) <= 160
    # Should end cleanly, not mid-word
    assert not result.endswith(" ")

def test_hard_truncate_appends_ellipsis():
    # A single run-on sentence with no breaks
    text = "A" * 200
    result = clean_and_truncate(text)
    assert result.endswith("...")
    assert len(result) == 160

def test_exactly_160_chars_unchanged():
    text = "A" * 160
    assert clean_and_truncate(text) == text
