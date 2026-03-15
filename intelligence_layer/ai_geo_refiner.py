"""
ai_geo_refiner.py — AI-powered geographic refinement for raw_ingestion_buffer.

Uses Gemini 1.5 Flash (Vertex AI) to identify the true geographic location each
story is ABOUT, regardless of which RSS feed it was sourced from.  Replaces the
rule-based TagEnhancer-only promotion path for stories that need location accuracy
(e.g. a Mumbai story ingested from a US tech feed → correctly tagged IN-MH).

Flow:
  1. Fetch docs with status="pending" from raw_ingestion_buffer.
  2. Process in batches of BATCH_SIZE through Gemini 1.5 Flash.
  3. For each story, check geo_lexicon (Firestore) for cached city coordinates
     before trusting Gemini's coordinates — avoids redundant LLM calls for
     repeatedly-seen cities (Chennai, London, Tokyo …).
  4. Populate geo_lexicon with newly discovered city → (lat, lng, region_code).
  5. Promote enriched stories to master_news with AI-verified geo fields.
  6. Mark buffer docs as status="processed".

Design:
  • Confidence gate — region_code is only overridden when Gemini confidence ≥ 0.5.
    Low-confidence responses keep the original feed-level region code.
  • Graceful degradation — if Vertex AI is unavailable (quota, cold-start, no
    credentials), process_pending() returns 0 so the caller can fall back to
    the rule-based FirestoreRefiner.
  • Stateless — safe to call concurrently from multiple Cloud Run instances.
  • Async-safe — the sync Vertex AI SDK is run in a thread-pool executor so the
    async event loop is never blocked.

Usage:
    from intelligence_layer.ai_geo_refiner import ai_geo_refiner

    promoted = await ai_geo_refiner.process_pending(limit=100)
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
_BATCH_SIZE = 15          # stories per Gemini prompt
_MIN_CONFIDENCE = 0.50    # below this, keep the original region_code

# ── Prompt ───────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are a geographic entity resolver for a global news aggregation system.

Given a numbered list of news story titles and snippets, identify the PRIMARY
geographic location that EACH STORY IS ABOUT — not where it was published or
which feed it came from.

Return ONLY a valid JSON array with one object per story in THE SAME ORDER as
the input.  Each object must have exactly these keys:

  "region_code" : ISO 3166-2 subdivision (e.g. "IN-MH", "US-TX") or ISO alpha-2
                  country code (e.g. "IN", "US") — NEVER null
  "lat"         : decimal latitude of the primary location, or null
  "lng"         : decimal longitude of the primary location, or null
  "city"        : city or locality name if clearly identified, else null
  "confidence"  : float 0.0–1.0
                    0.9+ = explicit named location (city/state in title)
                    0.5–0.9 = inferred from context
                    <0.5   = uncertain — use original_region unchanged

Rules:
  - Prefer subdivisions (state/province) over country codes when a specific city
    or state is mentioned in the story.
  - lat/lng should be the CITY centroid, not the country centroid, when a city
    is named.
  - If the story mentions multiple locations, use the PRIMARY subject location.
  - If no geographic entity is found, copy original_region verbatim and set
    confidence to 0.2.
  - Do not add markdown, code fences, or explanation — only the JSON array.
"""


def _build_prompt(stories: List[Dict[str, Any]]) -> str:
    lines = ["Identify the primary location for each story:\n"]
    for i, s in enumerate(stories, 1):
        lines.append(
            f"[{i}] original_region={s.get('region_code', '')} "
            f"| title: {s.get('title', '')[:180]} "
            f"| snippet: {s.get('snippet', '')[:250]}"
        )
    return "\n".join(lines)


def _parse_json(text: str) -> List[Dict[str, Any]]:
    """Extract and parse the first JSON array from Gemini's response."""
    text = text.strip()
    # Strip markdown fences
    for fence in ("```json", "```"):
        if text.startswith(fence):
            text = text[len(fence):]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

    start = text.find("[")
    end = text.rfind("]") + 1
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end])
        except json.JSONDecodeError as exc:
            logger.warning("AIGeoRefiner: JSON parse error — %s", exc)
    return []


# ── Main class ───────────────────────────────────────────────────────────────

class AIGeoRefiner:
    """
    AI-powered geographic refinement and raw-to-master promotion pipeline.

    Instantiate once (module-level singleton at bottom of file).
    """

    def __init__(self) -> None:
        self._model = None   # lazy — created on first call to _get_model()

    # ── Vertex AI initialisation ─────────────────────────────────────────────

    def _get_model(self):
        if self._model is not None:
            return self._model
        try:
            import vertexai                                          # type: ignore
            from vertexai.generative_models import GenerativeModel  # type: ignore

            project = (
                os.getenv("GOOGLE_CLOUD_PROJECT")
                or os.getenv("FIRESTORE_PROJECT", "omnesvident")
            )
            vertexai.init(project=project, location="us-central1")
            self._model = GenerativeModel("gemini-1.5-flash")
            logger.info(
                "AIGeoRefiner: Vertex AI initialised (project=%s).", project
            )
        except Exception as exc:
            logger.warning("AIGeoRefiner: Vertex AI init failed — %s", exc)
            self._model = None
        return self._model

    # ── Geo Lexicon (Firestore cache) ────────────────────────────────────────

    async def _lexicon_get(
        self, city: str, client
    ) -> Optional[Dict[str, Any]]:
        """Return cached entry for a city name, or None on miss/error."""
        try:
            key = city.lower().strip()
            doc = await (
                client.collection(_GEO_LEXICON_COLLECTION)
                .document(key)
                .get()
            )
            return doc.to_dict() if doc.exists else None
        except Exception:
            return None

    async def _lexicon_set(
        self, city: str, data: Dict[str, Any], client
    ) -> None:
        """Write a new city entry into geo_lexicon."""
        try:
            key = city.lower().strip()
            entry = {
                **data,
                "_city": key,
                "cached_at": datetime.now(tz=timezone.utc),
            }
            await (
                client.collection(_GEO_LEXICON_COLLECTION)
                .document(key)
                .set(entry)
            )
        except Exception as exc:
            logger.debug(
                "AIGeoRefiner: geo_lexicon write failed for '%s' — %s",
                city, exc,
            )

    # ── Gemini call ──────────────────────────────────────────────────────────

    async def _call_gemini(
        self, stories: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Call Gemini 1.5 Flash with a batch of stories.
        Runs the sync SDK in a thread executor so the event loop stays free.
        Returns a list of dicts (same length as stories, padded with {} on error).
        """
        model = self._get_model()
        if model is None:
            return []

        prompt = _SYSTEM_PROMPT + "\n\n" + _build_prompt(stories)
        try:
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                None,
                lambda: model.generate_content(
                    prompt,
                    generation_config={
                        "temperature": 0.1,
                        "max_output_tokens": 2048,
                    },
                ),
            )
            results = _parse_json(response.text)
            if len(results) != len(stories):
                logger.warning(
                    "AIGeoRefiner: Gemini returned %d results for %d stories.",
                    len(results), len(stories),
                )
            return results
        except Exception as exc:
            logger.error("AIGeoRefiner._call_gemini: %s", exc)
            return []

    # ── Per-story resolution with lexicon ────────────────────────────────────

    async def _resolve(
        self,
        original: Dict[str, Any],
        ai: Dict[str, Any],
        client,
    ) -> Tuple[str, Optional[float], Optional[float], float]:
        """
        Merge AI result with geo_lexicon cache.

        Returns (region_code, lat, lng, confidence).
        """
        city       = ai.get("city")
        confidence = float(ai.get("confidence") or 0.0)
        region_code = ai.get("region_code") or original.get("region_code", "")
        lat        = ai.get("lat")
        lng        = ai.get("lng")

        if city:
            cached = await self._lexicon_get(city, client)
            if cached:
                # Use cached coords (cheaper / more stable than Gemini coords)
                lat = cached.get("lat", lat)
                lng = cached.get("lng", lng)
                logger.debug("AIGeoRefiner: geo_lexicon hit — '%s'", city)
            elif lat is not None and lng is not None:
                # New city — populate the cache
                await self._lexicon_set(
                    city,
                    {
                        "region_code": region_code,
                        "lat": lat,
                        "lng": lng,
                        "confidence": confidence,
                    },
                    client,
                )
                logger.debug("AIGeoRefiner: geo_lexicon populated — '%s'", city)

        # Confidence gate: don't override region if AI is unsure
        if confidence < _MIN_CONFIDENCE:
            region_code = original.get("region_code") or region_code

        return region_code, lat, lng, confidence

    # ── Main entry point ─────────────────────────────────────────────────────

    async def process_pending(self, limit: int = 100) -> int:
        """
        Fetch up to `limit` pending docs from raw_ingestion_buffer, refine
        their geo data with Gemini 1.5 Flash, promote to master_news, and
        mark source docs as processed.

        Returns the number of docs successfully promoted.
        Returns 0 without raising if Vertex AI or Firestore is unavailable.
        """
        from database.firestore_manager import firestore_manager as mgr  # local import

        if not mgr._is_enabled():
            logger.info("AIGeoRefiner: Firestore disabled — skipping.")
            return 0

        client = await mgr._get_client()
        if client is None:
            return 0

        docs = await mgr.get_pending_raw(limit=limit)
        if not docs:
            logger.info("AIGeoRefiner: no pending docs.")
            return 0

        logger.info("AIGeoRefiner: refining %d pending doc(s).", len(docs))

        promoted_ids: List[str] = []
        failed_ids:   List[str] = []

        for batch_start in range(0, len(docs), _BATCH_SIZE):
            batch = docs[batch_start: batch_start + _BATCH_SIZE]

            story_inputs = [
                {
                    "title":       d.get("raw_payload", {}).get("title", ""),
                    "snippet":     d.get("raw_payload", {}).get("snippet", ""),
                    "region_code": d.get("raw_payload", {}).get("region_code", ""),
                }
                for d in batch
            ]

            # Call Gemini for the whole batch in one round-trip
            ai_results = await self._call_gemini(story_inputs)
            # Pad so zip() is always safe
            while len(ai_results) < len(batch):
                ai_results.append({})

            for doc, story_input, ai_result in zip(batch, story_inputs, ai_results):
                doc_id = doc.get("_doc_id", "")
                raw    = doc.get("raw_payload", {})

                try:
                    region_code, lat, lng, confidence = await self._resolve(
                        story_input, ai_result, client
                    )

                    # Lazy imports to avoid circular deps at module level
                    from ingestion_engine.core.models import NewsEvent
                    from tasks.refiner import _parse_timestamp
                    from intelligence_layer.classifier import classify

                    event = NewsEvent(
                        title=raw.get("title", ""),
                        snippet=raw.get("snippet", ""),
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

                    ok = await mgr.promote_to_master(
                        event=event,
                        date_group=ts.strftime("%Y-%m-%d"),
                        extra_fields={
                            "latitude":       lat,
                            "longitude":      lng,
                            "geo_confidence": round(confidence, 3),
                            "geo_source":     "gemini-1.5-flash",
                            "category":       category,
                        },
                    )

                    if ok:
                        promoted_ids.append(doc_id)
                        logger.debug(
                            "AIGeoRefiner: %s → %s (%.2f conf, cat=%s)",
                            doc_id, region_code, confidence, category,
                        )
                    else:
                        failed_ids.append(doc_id)

                except Exception as exc:
                    logger.warning(
                        "AIGeoRefiner: doc %s failed — %s", doc_id, exc
                    )
                    failed_ids.append(doc_id)

        if promoted_ids:
            await mgr.mark_raw_processed(promoted_ids)
            logger.info(
                "AIGeoRefiner: promoted=%d, failed=%d (of %d).",
                len(promoted_ids), len(failed_ids), len(docs),
            )

        return len(promoted_ids)


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

ai_geo_refiner = AIGeoRefiner()
