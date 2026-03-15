"""
refiner.py — Raw-to-Master Firestore promotion pipeline.

Triggered after every ingestion cycle (by /tasks/ingest or manually).

Flow:
  1. Fetch docs with status="pending" from raw_ingestion_buffer.
  2. Reconstruct NewsEvent objects from the stored raw_payload.
  3. Run TagEnhancer.enhance() on each event to resolve subdivision region_codes.
  4. Calculate date_group from the story timestamp ("YYYY-MM-DD").
  5. Batch-promote refined events to master_news (upsert by source_url hash).
  6. Mark processed buffer docs as status="processed".

Design:
  • Stateless — no in-memory state between calls; safe to call concurrently.
  • Graceful degradation — if Firestore is disabled (FIRESTORE_PROJECT not set),
    refine_pending() returns immediately with a zero count.
  • Chunk-aware — processes up to `limit` docs per call to stay within Cloud Run
    request timeouts.  Chain multiple calls for large backlogs.

Usage:
    from tasks.refiner import FirestoreRefiner

    refiner = FirestoreRefiner()
    promoted = await refiner.refine_pending(limit=100)
    # promoted == number of docs successfully written to master_news
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from database.firestore_manager import FirestoreManager, firestore_manager as _default_mgr
from ingestion_engine.core.models import NewsEvent
from intelligence_layer.geo_tagger import TagEnhancer

logger = logging.getLogger(__name__)


def _parse_timestamp(value: Any) -> datetime:
    """
    Coerce various timestamp representations that may come out of Firestore
    back to a timezone-aware datetime.
    """
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            pass
    # Firestore DatetimeWithNanoseconds has a .timestamp_pb() but is
    # also directly convertible; fall back to utcnow.
    try:
        return datetime.fromtimestamp(float(value), tz=timezone.utc)
    except Exception:
        return datetime.now(tz=timezone.utc)


class FirestoreRefiner:
    """
    Promotes pending raw_ingestion_buffer documents to master_news.

    Args:
        manager: A FirestoreManager instance.  Defaults to the module-level
                 singleton so callers can just do `FirestoreRefiner()`.
    """

    def __init__(self, manager: Optional[FirestoreManager] = None) -> None:
        self._mgr = manager or _default_mgr
        self._tagger = TagEnhancer()

    async def refine_pending(self, limit: int = 100) -> int:
        """
        Fetch up to `limit` pending docs, promote them, and mark as processed.

        Returns the number of documents successfully promoted to master_news.
        """
        docs = await self._mgr.get_pending_raw(limit=limit)
        if not docs:
            logger.info("FirestoreRefiner: no pending docs found.")
            return 0

        logger.info("FirestoreRefiner: processing %d pending doc(s).", len(docs))

        promoted_ids: List[str] = []
        failed_ids: List[str] = []

        for doc in docs:
            doc_id: str = doc.get("_doc_id", "")
            raw: Dict[str, Any] = doc.get("raw_payload", {})

            # ── Reconstruct NewsEvent ────────────────────────────────────────
            try:
                event = NewsEvent(
                    title=raw.get("title", ""),
                    snippet=raw.get("snippet", ""),
                    source_url=raw.get("source_url", ""),
                    source_name=raw.get("source_name", ""),
                    region_code=raw.get("region_code", ""),
                    timestamp=_parse_timestamp(raw.get("timestamp")),
                )
            except Exception as exc:
                logger.warning(
                    "FirestoreRefiner: could not reconstruct NewsEvent from doc %s — %s",
                    doc_id, exc,
                )
                failed_ids.append(doc_id)
                continue

            if not event.source_url:
                logger.warning(
                    "FirestoreRefiner: doc %s has no source_url, skipping.", doc_id
                )
                failed_ids.append(doc_id)
                continue

            # ── TagEnhancer: resolve subdivision region_code ─────────────────
            enhanced, _ = self._tagger.enhance(event)

            # ── date_group ───────────────────────────────────────────────────
            ts = enhanced.timestamp or datetime.now(tz=timezone.utc)
            date_group = ts.strftime("%Y-%m-%d")

            # ── Promote to master_news ────────────────────────────────────────
            ok = await self._mgr.promote_to_master(
                event=enhanced,
                date_group=date_group,
            )

            if ok:
                promoted_ids.append(doc_id)
            else:
                failed_ids.append(doc_id)

        # ── Mark successfully promoted docs as "processed" ───────────────────
        if promoted_ids:
            await self._mgr.mark_raw_processed(promoted_ids)
            logger.info(
                "FirestoreRefiner: promoted=%d, failed=%d.",
                len(promoted_ids), len(failed_ids),
            )

        return len(promoted_ids)


# Module-level singleton — import and call directly from routes / runner.
refiner = FirestoreRefiner()
