import re

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_SCRIPT_RE = re.compile(r"<script[^>]*>.*?</script>", re.IGNORECASE | re.DOTALL)
_STYLE_RE = re.compile(r"<style[^>]*>.*?</style>", re.IGNORECASE | re.DOTALL)
_SENTENCE_END_RE = re.compile(r"[.!?]\s")

SNIPPET_MAX_LEN = 160


def clean_and_truncate(text: str) -> str:
    """Strip HTML, find a natural sentence boundary, and enforce 160-char limit."""
    # Remove scripts and styles before stripping tags
    text = _SCRIPT_RE.sub("", text)
    text = _STYLE_RE.sub("", text)
    text = _HTML_TAG_RE.sub("", text)

    # Collapse whitespace
    text = " ".join(text.split())

    if len(text) <= SNIPPET_MAX_LEN:
        return text

    # Try to find end of 1st or 2nd sentence within the limit
    search_window = text[: SNIPPET_MAX_LEN + 40]
    matches = list(_SENTENCE_END_RE.finditer(search_window))
    if matches:
        # Prefer second sentence end, fall back to first
        best = matches[1] if len(matches) >= 2 else matches[0]
        candidate = text[: best.start() + 1]
        if len(candidate) <= SNIPPET_MAX_LEN:
            return candidate

    # Hard truncate
    return text[: SNIPPET_MAX_LEN - 3] + "..."


def strip_html(text: str) -> str:
    """Strip HTML only — no truncation."""
    text = _SCRIPT_RE.sub("", text)
    text = _STYLE_RE.sub("", text)
    text = _HTML_TAG_RE.sub("", text)
    return " ".join(text.split())
