"""
refiner.py — AI-driven Geographic Refinement Agent (Module 16.1).

Reads raw news events from Firestore `raw_ingestion_buffer`, resolves their
true geographic location (city → subdivision → coordinates) using Gemini 1.5
Flash, and promotes enriched records to `master_news`.

Architecture:
  GeocodingCache  — Firestore-backed city→(lat, lng, region_code) cache.
                    Eliminates repeated LLM calls for the same city.
  AIRefiner       — Main agent class.  Batches 15 stories per Gemini call,
                    consults GeocodingCache before every coordinate lookup,
                    then promotes via FirestoreManager.

Entry point:
    from intelligence_layer.refiner import ai_refiner
    promoted = await ai_refiner.process_buffer(limit=200)

Triggered by:
    /tasks/ingest endpoint (FastAPI BackgroundTask) immediately after the
    ingestion cycle writes raw docs to the buffer.

Graceful degradation:
    If Vertex AI is unavailable (quota, cold-start, missing IAM) the method
    returns 0 and the caller falls back to the rule-based FirestoreRefiner,
    so the buffer is never left stranded.
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
_BATCH_SIZE             = 15      # stories per Gemini prompt
_MIN_CONFIDENCE         = 0.50    # below this, keep the original region_code

# ── Gemini prompt ─────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are a geographic entity resolver for a global news aggregation system.

Given a numbered list of news story titles and snippets, identify the PRIMARY
geographic location that EACH STORY IS ABOUT — not where it was published.

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

    On a cache hit, coordinate lookups skip the LLM entirely.  On a miss,
    the refiner calls Gemini and then writes the result back via `set()`.

    Collection: geo_lexicon
    Document ID: city name, lower-stripped (e.g. "mumbai", "coimbatore")
    Fields: region_code, lat, lng, confidence, _city, cached_at
    """

    def __init__(self, client) -> None:
        self._client = client

    async def get(self, city: str) -> Optional[Dict[str, Any]]:
        """Return cached entry for `city`, or None on miss / error."""
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
        """Write / overwrite an entry in geo_lexicon."""
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

    Typical usage — instantiate once as a module-level singleton:

        from intelligence_layer.refiner import ai_refiner
        promoted = await ai_refiner.process_buffer(limit=200)
    """

    def __init__(self) -> None:
        self._model = None   # lazy — created on first _get_model() call

    # ── Vertex AI ────────────────────────────────────────────────────────────

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
            logger.info("AIRefiner: Vertex AI ready (project=%s).", project)
        except Exception as exc:
            logger.warning("AIRefiner: Vertex AI init failed — %s", exc)
            self._model = None
        return self._model

    # ── Gemini call ──────────────────────────────────────────────────────────

    async def _call_gemini(
        self, stories: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
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
                    generation_config={"temperature": 0.1, "max_output_tokens": 2048},
                ),
            )
            results = _parse_json(response.text)
            if len(results) != len(stories):
                logger.warning(
                    "AIRefiner: Gemini returned %d results for %d stories.",
                    len(results), len(stories),
                )
            return results
        except Exception as exc:
            logger.error("AIRefiner._call_gemini: %s", exc)
            return []

    # ── Per-story geo resolution ──────────────────────────────────────────────

    async def _resolve(
        self,
        original: Dict[str, Any],
        ai: Dict[str, Any],
        cache: GeocodingCache,
    ) -> Tuple[str, Optional[float], Optional[float], float]:
        """
        Merge AI result with GeocodingCache.

        Resolution order:
          1. Gemini returns city name → check cache for coords.
          2. Cache miss and Gemini has coords → populate cache.
          3. Confidence < MIN_CONFIDENCE → revert to original region_code.

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
            region_code = original.get("region_code") or region_code

        return region_code, lat, lng, confidence

    # ── Main entry point ──────────────────────────────────────────────────────

    async def process_buffer(self, limit: int = 100) -> int:
        """
        Fetch up to `limit` pending docs from raw_ingestion_buffer, resolve
        their geographic data via Gemini 1.5 Flash + GeocodingCache, and
        promote enriched records to master_news.

        Steps:
          1. Query raw_ingestion_buffer for status="pending" docs.
          2. Batch through Gemini (15 stories/call) to get region_code+lat+lng.
          3. Check GeocodingCache for cached city coordinates.
          4. Classify category with the rule-based keyword classifier.
          5. Upsert into master_news (keyed by SHA-256[:24] of source_url).
          6. Batch-update buffer docs to status="processed".

        Returns the number of docs successfully promoted to master_news.
        Returns 0 (without raising) if Vertex AI or Firestore is unavailable.
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

        cache = GeocodingCache(client)
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

            ai_results = await self._call_gemini(story_inputs)
            while len(ai_results) < len(batch):
                ai_results.append({})

            for doc, story_input, ai_result in zip(batch, story_inputs, ai_results):
                doc_id = doc.get("_doc_id", "")
                raw    = doc.get("raw_payload", {})

                try:
                    region_code, lat, lng, confidence = await self._resolve(
                        story_input, ai_result, cache
                    )

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
                            "AIRefiner: %s → %s (conf=%.2f, cat=%s, city=%s)",
                            doc_id, region_code, confidence, category,
                            ai_result.get("city"),
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
