"""
refiner.py — AI-driven Geographic Refinement Agent (Module 16.1).

Reads raw news events from Firestore `raw_ingestion_buffer`, resolves their
true geographic location (city → subdivision → coordinates) using OpenAI
gpt-4o-mini, and promotes enriched records to `master_news`.

Architecture:
  GeocodingCache  — Firestore-backed city→(lat, lng, region_code) cache.
                    Eliminates repeated LLM calls for the same city.
  AIRefiner       — Main agent class.  Batches 15 stories per OpenAI call.
                    Steps per batch:
                      1. Detect non-Latin script (Devanagari, Arabic, CJK…)
                      2. Translate non-English titles/snippets to English
                      3. Pass English text + script_hint to geo-resolver
                      4. Consult GeocodingCache for coordinates
                      5. Promote to master_news with English title stored

Entry point:
    from intelligence_layer.refiner import ai_refiner
    promoted = await ai_refiner.process_buffer(limit=200)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────

_GEO_LEXICON_COLLECTION = "geo_lexicon"
_BATCH_SIZE             = 15      # stories per OpenAI prompt
_MIN_CONFIDENCE         = 0.50    # below this, keep the original region_code

# ── Script detection ──────────────────────────────────────────────────────────
#
# Unicode block ranges for non-Latin scripts.
# Tuple: (range_start, range_end, script_name)

_NON_LATIN_RANGES: List[Tuple[int, int, str]] = [
    (0x0900, 0x097F, "Devanagari"),   # Hindi, Marathi, Sanskrit
    (0x0980, 0x09FF, "Bengali"),       # Bengali, Assamese
    (0x0A00, 0x0A7F, "Gurmukhi"),     # Punjabi
    (0x0A80, 0x0AFF, "Gujarati"),     # Gujarati
    (0x0B00, 0x0B7F, "Oriya"),        # Odia
    (0x0B80, 0x0BFF, "Tamil"),        # Tamil
    (0x0C00, 0x0C7F, "Telugu"),       # Telugu
    (0x0C80, 0x0CFF, "Kannada"),      # Kannada
    (0x0D00, 0x0D7F, "Malayalam"),    # Malayalam
    (0x0600, 0x06FF, "Arabic"),       # Arabic, Urdu, Persian, Pashto
    (0x4E00, 0x9FFF, "CJK"),          # Chinese (Simplified + Traditional)
    (0x3040, 0x309F, "Hiragana"),     # Japanese
    (0x30A0, 0x30FF, "Katakana"),     # Japanese
    (0xAC00, 0xD7AF, "Hangul"),       # Korean
    (0x0400, 0x04FF, "Cyrillic"),     # Russian, Ukrainian, Bulgarian…
    (0x0E00, 0x0E7F, "Thai"),         # Thai
    (0x0370, 0x03FF, "Greek"),        # Greek
    (0x05D0, 0x05EA, "Hebrew"),       # Hebrew
]

# Strong country hints derived from script alone (used in geo-resolution prompt)
_SCRIPT_COUNTRY_HINT: Dict[str, str] = {
    "Devanagari": "IN",
    "Bengali":    "IN",
    "Gurmukhi":   "IN",
    "Gujarati":   "IN",
    "Oriya":      "IN",
    "Tamil":      "IN",
    "Telugu":     "IN",
    "Kannada":    "IN",
    "Malayalam":  "IN",
    "Hiragana":   "JP",
    "Katakana":   "JP",
    "Hangul":     "KR",
    "Thai":       "TH",
    "Greek":      "GR",
    "Hebrew":     "IL",
    # Arabic/CJK/Cyrillic intentionally omitted — too many countries
}


def _detect_script(text: str) -> Optional[str]:
    """
    Return the dominant non-Latin script name if >30 % of alpha characters
    belong to it, otherwise None.
    """
    alpha_chars = [c for c in text if c.isalpha()]
    if not alpha_chars:
        return None

    counts: Dict[str, int] = {}
    for char in alpha_chars:
        cp = ord(char)
        for start, end, name in _NON_LATIN_RANGES:
            if start <= cp <= end:
                counts[name] = counts.get(name, 0) + 1
                break

    if not counts:
        return None

    dominant = max(counts, key=lambda k: counts[k])
    if counts[dominant] / len(alpha_chars) > 0.30:
        return dominant
    return None


# ── Geo-resolution prompt ─────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are a geographic entity resolver for a global news aggregation system.

Given a numbered list of news story titles and snippets (always in English),
identify the PRIMARY geographic location that EACH STORY IS ABOUT — not where
it was published.

Return ONLY a valid JSON array with one object per story IN THE SAME ORDER as
the input.  Each object must have exactly these keys:

  "region_code" : ISO 3166-2 subdivision (e.g. "IN-TN", "US-TX") or ISO alpha-2
                  country code (e.g. "IN", "US") — NEVER null
  "lat"         : decimal latitude of the primary location, or null
  "lng"         : decimal longitude of the primary location, or null
  "city"        : city or locality name if clearly identified, else null
  "confidence"  : float 0.0–1.0
                    0.9+ = explicit named location in title/snippet
                    0.5–0.9 = inferred from context
                    <0.5   = uncertain — return original_region unchanged

Rules:
  - Prefer subdivision codes when a city or state is named.
  - lat/lng must be the CITY centroid (not the country centroid).
  - For cross-regional stories, use the PRIMARY subject location.
  - If no geographic entity is found, copy original_region verbatim and set
    confidence to 0.2.
  - Do NOT add markdown fences, code blocks, or explanation — only the JSON.

Script-hint rules (each story may carry a [script_hint=XX] tag):
  If a script_hint is present, treat it as a STRONG prior for that country
  (confidence ≥ 0.7) unless the title/snippet names an explicit conflicting
  location.  Examples:
    script_hint=IN  → story is almost certainly about India
    script_hint=JP  → story is almost certainly about Japan
    script_hint=KR  → story is almost certainly about South Korea
    script_hint=TH  → story is almost certainly about Thailand
    script_hint=IL  → story is almost certainly about Israel
  For Arabic/CJK/Cyrillic (no single country), use the script as a broad
  regional prior and rely on named entities to narrow it down.
"""

_TRANSLATE_SYSTEM_PROMPT = """\
You are a news translator. Translate each numbered news item to English.

Return ONLY a valid JSON array in the same order as the input. Each object
must have exactly two keys: "title" and "snippet".

Rules:
  - Preserve proper nouns, place names, person names, and numbers exactly.
  - Keep the translation concise and journalistic in tone.
  - Do NOT add markdown fences or explanation — only the JSON array.
"""


def _build_prompt(stories: List[Dict[str, Any]]) -> str:
    lines = ["Identify the primary location for each story:\n"]
    for i, s in enumerate(stories, 1):
        hint = s.get("_script_hint")
        hint_str = f" [script_hint={hint}]" if hint else ""
        lines.append(
            f"[{i}] original_region={s.get('region_code', '')}{hint_str}"
            f" | title: {s.get('title', '')[:180]}"
            f" | snippet: {s.get('snippet', '')[:250]}"
        )
    return "\n".join(lines)


def _parse_json(text: str) -> List[Dict[str, Any]]:
    """Extract and parse the first JSON array from an LLM response."""
    text = text.strip()
    for fence in ("```json", "```"):
        if text.startswith(fence):
            text = text[len(fence):]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()
    start, end = text.find("["), text.rfind("]") + 1
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end])
        except json.JSONDecodeError as exc:
            logger.warning("AIRefiner: JSON parse error — %s", exc)
    return []


# ── GeocodingCache ────────────────────────────────────────────────────────────

class GeocodingCache:
    """
    Firestore-backed cache mapping city names → (lat, lng, region_code).

    Collection: geo_lexicon
    Document ID: city name, lower-stripped (e.g. "mumbai", "coimbatore")
    Fields: region_code, lat, lng, confidence, _city, cached_at
    """

    def __init__(self, client) -> None:
        self._client = client

    async def get(self, city: str) -> Optional[Dict[str, Any]]:
        try:
            doc = await (
                self._client
                .collection(_GEO_LEXICON_COLLECTION)
                .document(city.lower().strip())
                .get()
            )
            return doc.to_dict() if doc.exists else None
        except Exception:
            return None

    async def set(self, city: str, data: Dict[str, Any]) -> None:
        try:
            entry = {
                **data,
                "_city": city.lower().strip(),
                "cached_at": datetime.now(tz=timezone.utc),
            }
            await (
                self._client
                .collection(_GEO_LEXICON_COLLECTION)
                .document(city.lower().strip())
                .set(entry)
            )
            logger.debug("GeocodingCache: stored '%s'", city)
        except Exception as exc:
            logger.debug("GeocodingCache: write failed for '%s' — %s", city, exc)


# ── AIRefiner ─────────────────────────────────────────────────────────────────

class AIRefiner:
    """
    AI-driven geographic refinement and raw-to-master promotion agent.

    Pipeline per batch of 15 stories:
      1. Detect non-Latin script in each title (Layer 1)
      2. Batch-translate non-English titles/snippets to English (Layer 2)
      3. Attach script_hint to translated stories (Layer 3)
      4. Call OpenAI for geo-resolution with script-aware prompt (Layer 3)
      5. GeocodingCache lookup/write for city coordinates
      6. Promote to master_news with English title + correct region/lat/lng

    Usage:
        from intelligence_layer.refiner import ai_refiner
        promoted = await ai_refiner.process_buffer(limit=200)
    """

    def __init__(self) -> None:
        self._client = None   # lazy — openai.OpenAI singleton

    # ── OpenAI client ─────────────────────────────────────────────────────────

    def _get_client(self):
        if self._client is not None:
            return self._client
        api_key = os.getenv("OPEN_AI_API_KEY", "") or os.getenv("OPENAI_API_KEY", "")
        if not api_key:
            logger.warning("AIRefiner: OPEN_AI_API_KEY not set — geo refinement disabled.")
            return None
        try:
            from openai import OpenAI  # type: ignore
            self._client = OpenAI(api_key=api_key)
            logger.info("AIRefiner: OpenAI client ready.")
        except Exception as exc:
            logger.warning("AIRefiner: OpenAI init failed — %s", exc)
            self._client = None
        return self._client

    # ── Layer 1 + 2: script detection + batch translation ────────────────────

    async def _translate_batch(
        self, stories: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Detect non-Latin scripts in each story title.  Batch-translate those
        that need it into English.  Returns a new list (same length) with:
          - Translated stories: title/snippet replaced with English,
            plus _translated=True, _original_title, _script_hint keys.
          - Untranslated stories: passed through unchanged (possibly with
            _script_hint if an Arabic/CJK/Cyrillic script was detected).
        """
        result = [dict(s) for s in stories]

        # Identify stories needing translation
        to_translate: List[Tuple[int, Dict[str, Any], str]] = []  # (index, story, script)
        for i, story in enumerate(stories):
            script = _detect_script(story.get("title", ""))
            if script:
                hint = _SCRIPT_COUNTRY_HINT.get(script)
                result[i]["_script"] = script
                if hint:
                    result[i]["_script_hint"] = hint
                to_translate.append((i, story, script))

        if not to_translate:
            return result

        client = self._get_client()
        if client is None:
            return result

        # Build a single translation request for all non-English stories
        batch_lines = "\n\n".join(
            f"[{seq+1}] title: {item['title'][:300]}\nsnippet: {item.get('snippet', '')[:400]}"
            for seq, (_, item, _) in enumerate(to_translate)
        )

        try:
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                None,
                lambda: client.chat.completions.create(
                    model="gpt-4o-mini",
                    temperature=0,
                    max_tokens=2000,
                    messages=[
                        {"role": "system", "content": _TRANSLATE_SYSTEM_PROMPT},
                        {"role": "user",   "content": batch_lines},
                    ],
                ),
            )
            translations = _parse_json(response.choices[0].message.content or "")

            for seq, ((orig_idx, orig_story, script), translation) in enumerate(
                zip(to_translate, translations)
            ):
                en_title   = translation.get("title", "").strip() or orig_story["title"]
                en_snippet = translation.get("snippet", "").strip() or orig_story.get("snippet", "")
                result[orig_idx].update({
                    "title":           en_title,
                    "snippet":         en_snippet,
                    "_translated":     True,
                    "_original_title": orig_story["title"],
                })
                logger.debug(
                    "AIRefiner: [%s] translated '%s' → '%s'",
                    script, orig_story["title"][:50], en_title[:50],
                )

            untranslated = len(to_translate) - len(translations)
            if untranslated:
                logger.warning(
                    "AIRefiner._translate_batch: got %d translations for %d stories.",
                    len(translations), len(to_translate),
                )

        except Exception as exc:
            logger.warning("AIRefiner._translate_batch: failed — %s", exc)

        return result

    # ── Layer 3: geo-resolution call ─────────────────────────────────────────

    async def _call_geo(
        self, stories: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Call OpenAI gpt-4o-mini with the script-aware geo-resolution prompt.
        `stories` must already be in English (run _translate_batch first).
        """
        client = self._get_client()
        if client is None:
            return []
        prompt = _build_prompt(stories)
        try:
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                None,
                lambda: client.chat.completions.create(
                    model="gpt-4o-mini",
                    temperature=0.1,
                    max_tokens=2048,
                    messages=[
                        {"role": "system", "content": _SYSTEM_PROMPT},
                        {"role": "user",   "content": prompt},
                    ],
                ),
            )
            text = response.choices[0].message.content or ""
            results = _parse_json(text)
            if len(results) != len(stories):
                logger.warning(
                    "AIRefiner: OpenAI returned %d results for %d stories.",
                    len(results), len(stories),
                )
            return results
        except Exception as exc:
            logger.error("AIRefiner._call_geo: %s", exc)
            return []

    # Keep legacy name so existing callers don't break
    _call_gemini = _call_geo

    # ── Per-story geo resolution ──────────────────────────────────────────────

    async def _resolve(
        self,
        original: Dict[str, Any],
        ai: Dict[str, Any],
        cache: GeocodingCache,
    ) -> Tuple[str, Optional[float], Optional[float], float]:
        """
        Merge AI result with GeocodingCache.

        If AI confidence < MIN_CONFIDENCE AND a script_hint is present,
        use the script_hint country instead of the fallback original_region.

        Returns (region_code, lat, lng, confidence).
        """
        city        = ai.get("city")
        confidence  = float(ai.get("confidence") or 0.0)
        region_code = ai.get("region_code") or original.get("region_code", "")
        lat         = ai.get("lat")
        lng         = ai.get("lng")

        if city:
            cached = await cache.get(city)
            if cached:
                lat = cached.get("lat", lat)
                lng = cached.get("lng", lng)
                logger.debug("GeocodingCache: hit — '%s'", city)
            elif lat is not None and lng is not None:
                await cache.set(city, {
                    "region_code": region_code,
                    "lat": lat,
                    "lng": lng,
                    "confidence": confidence,
                })

        if confidence < _MIN_CONFIDENCE:
            # Prefer script_hint over the (potentially wrong) original region
            script_hint = original.get("_script_hint")
            if script_hint:
                region_code = script_hint
                logger.debug(
                    "AIRefiner._resolve: low confidence %.2f, using script_hint=%s",
                    confidence, script_hint,
                )
            else:
                region_code = original.get("region_code") or region_code

        return region_code, lat, lng, confidence

    # ── Re-refine existing master_news ────────────────────────────────────────

    async def refine_master_news(self, limit: int = 5000) -> int:
        """
        Re-run geo-refinement (with translation) on all existing master_news docs.

        - Translates non-English titles/snippets to English (Layer 2)
        - Re-resolves region_code/lat/lng using script-aware prompt (Layer 3)
        - Updates title/snippet to English in master_news when translated
        - Updates region_code, lat, lng, geo_confidence, geo_source, category

        Returns number of docs updated.
        """
        from database.firestore_manager import firestore_manager as mgr
        from intelligence_layer.classifier import classify

        if not mgr._is_enabled():
            logger.info("AIRefiner.refine_master_news: Firestore disabled — skipping.")
            return 0

        client = await mgr._get_client()
        if client is None:
            return 0

        docs = await mgr.stream_all_master(limit=limit)
        if not docs:
            logger.info("AIRefiner.refine_master_news: no docs in master_news.")
            return 0

        logger.info(
            "AIRefiner.refine_master_news: processing %d master_news doc(s).", len(docs)
        )

        geo_cache = GeocodingCache(client)
        updated = 0

        for batch_start in range(0, len(docs), _BATCH_SIZE):
            batch = docs[batch_start: batch_start + _BATCH_SIZE]

            raw_inputs = [
                {
                    "title":       d.get("title", ""),
                    "snippet":     d.get("snippet", ""),
                    "region_code": d.get("region_code", ""),
                }
                for d in batch
            ]

            # Layer 1+2: detect scripts, translate non-English
            en_inputs = await self._translate_batch(raw_inputs)

            # Layer 3: geo-resolve on English text with script hints
            ai_results = await self._call_geo(en_inputs)
            while len(ai_results) < len(batch):
                ai_results.append({})

            for doc, en_input, ai_result in zip(batch, en_inputs, ai_results):
                doc_id = doc.get("_doc_id", "")
                try:
                    region_code, lat, lng, confidence = await self._resolve(
                        en_input, ai_result, geo_cache
                    )

                    # Classify using the (possibly translated) English text
                    category = classify(en_input["title"], en_input.get("snippet", ""))

                    patch: Dict[str, Any] = {
                        "region_code":    region_code,
                        "latitude":       lat,
                        "longitude":      lng,
                        "geo_confidence": round(confidence, 3),
                        "geo_source":     "openai-gpt4o-mini",
                        "category":       category,
                    }
                    # Also store English title/snippet when translation occurred
                    if en_input.get("_translated"):
                        patch["title"]          = en_input["title"]
                        patch["snippet"]        = en_input.get("snippet", "")
                        patch["original_title"] = en_input.get("_original_title", "")

                    ok = await mgr.update_master_geo(doc_id, patch)
                    if ok:
                        updated += 1
                        logger.debug(
                            "AIRefiner.refine_master_news: %s → %s (conf=%.2f, translated=%s)",
                            doc_id, region_code, confidence,
                            en_input.get("_translated", False),
                        )
                except Exception as exc:
                    logger.warning(
                        "AIRefiner.refine_master_news: doc %s failed — %s", doc_id, exc
                    )

        logger.info(
            "AIRefiner.refine_master_news: updated=%d of %d total.", updated, len(docs)
        )
        return updated

    # ── Main entry point: drain raw_ingestion_buffer ──────────────────────────

    async def process_buffer(self, limit: int = 100) -> int:
        """
        Fetch up to `limit` pending docs from raw_ingestion_buffer, translate
        non-English content, resolve geography, and promote to master_news.

        Steps:
          1. Fetch status="pending" docs from raw_ingestion_buffer.
          2. Detect non-Latin scripts → batch translate to English (Layers 1+2).
          3. Attach script_hint → call OpenAI geo-resolver (Layer 3).
          4. GeocodingCache lookup/write per city.
          5. Promote to master_news with English title stored.
          6. Delete promoted docs from raw_ingestion_buffer.

        Returns number of docs promoted.
        """
        from database.firestore_manager import firestore_manager as mgr

        if not mgr._is_enabled():
            logger.info("AIRefiner: Firestore disabled — skipping.")
            return 0

        client = await mgr._get_client()
        if client is None:
            return 0

        docs = await mgr.get_pending_raw(limit=limit)
        if not docs:
            logger.info("AIRefiner: no pending docs in buffer.")
            return 0

        logger.info("AIRefiner: processing %d doc(s) from raw buffer.", len(docs))

        geo_cache     = GeocodingCache(client)
        promoted_ids: List[str] = []
        failed_ids:   List[str] = []

        for batch_start in range(0, len(docs), _BATCH_SIZE):
            batch = docs[batch_start: batch_start + _BATCH_SIZE]

            raw_inputs = [
                {
                    "title":       d.get("raw_payload", {}).get("title", ""),
                    "snippet":     d.get("raw_payload", {}).get("snippet", ""),
                    "region_code": d.get("raw_payload", {}).get("region_code", ""),
                }
                for d in batch
            ]

            # Layer 1+2: translate non-English stories to English
            en_inputs = await self._translate_batch(raw_inputs)

            # Layer 3: geo-resolve on English text
            ai_results = await self._call_geo(en_inputs)
            while len(ai_results) < len(batch):
                ai_results.append({})

            for doc, raw_input, en_input, ai_result in zip(
                batch, raw_inputs, en_inputs, ai_results
            ):
                doc_id = doc.get("_doc_id", "")
                raw    = doc.get("raw_payload", {})

                try:
                    region_code, lat, lng, confidence = await self._resolve(
                        en_input, ai_result, geo_cache
                    )

                    from ingestion_engine.core.models import NewsEvent
                    from tasks.refiner import _parse_timestamp
                    from intelligence_layer.classifier import classify

                    # Use English title/snippet for storage (show users English content)
                    title   = en_input["title"]   or raw.get("title", "")
                    snippet = en_input.get("snippet", "") or raw.get("snippet", "")

                    event = NewsEvent(
                        title=title,
                        snippet=snippet,
                        source_url=raw.get("source_url", ""),
                        source_name=raw.get("source_name", ""),
                        region_code=region_code,
                        timestamp=_parse_timestamp(raw.get("timestamp")),
                    )

                    if not event.source_url:
                        failed_ids.append(doc_id)
                        continue

                    category = classify(event.title, event.snippet)
                    ts       = event.timestamp or datetime.now(tz=timezone.utc)

                    extra: Dict[str, Any] = {
                        "latitude":       lat,
                        "longitude":      lng,
                        "geo_confidence": round(confidence, 3),
                        "geo_source":     "openai-gpt4o-mini",
                        "category":       category,
                    }
                    # Preserve original non-English title for reference
                    if en_input.get("_translated"):
                        extra["original_title"] = en_input.get("_original_title", "")

                    ok = await mgr.promote_to_master(
                        event=event,
                        date_group=ts.strftime("%Y-%m-%d"),
                        extra_fields=extra,
                    )

                    if ok:
                        promoted_ids.append(doc_id)
                        logger.debug(
                            "AIRefiner: %s → %s (conf=%.2f, cat=%s, translated=%s)",
                            doc_id, region_code, confidence, category,
                            en_input.get("_translated", False),
                        )
                    else:
                        failed_ids.append(doc_id)

                except Exception as exc:
                    logger.warning("AIRefiner: doc %s failed — %s", doc_id, exc)
                    failed_ids.append(doc_id)

        if promoted_ids:
            await mgr.mark_raw_processed(promoted_ids)
            logger.info(
                "AIRefiner: promoted=%d, failed=%d (of %d total).",
                len(promoted_ids), len(failed_ids), len(docs),
            )

        return len(promoted_ids)


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

ai_refiner = AIRefiner()
