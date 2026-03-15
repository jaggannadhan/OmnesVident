"""
firestore_manager.py — Async Firestore persistence layer.

Two collections:

  raw_ingestion_buffer
    Temporary landing zone written immediately after every ingestion cycle.
    One document per NewsEvent.  TagEnhancer has NOT run yet.
    Fields: raw_payload, provider_id, fetched_at, status

  master_news
    Clean, geo-tagged, de-duplicated stories promoted by the Refiner.
    Document ID = SHA-256 hex[:16] of source_url to prevent duplicates.
    Fields: title, snippet, source_url, region_code, timestamp, date_group, …

Design principles:
  • Lazy singleton — the AsyncClient is created on first use, not at import time.
    This means local dev without GCP credentials never fails to import this module.
  • Graceful no-op — if FIRESTORE_PROJECT is unset or credentials are absent,
    every method logs a warning and returns a safe empty result without raising.
  • Batch writes — `push_to_raw` uses a WriteBatch for atomic, efficient writes.

Usage:
    from database.firestore_manager import FirestoreManager

    mgr = FirestoreManager()
    await mgr.push_to_raw(events, provider_id="newscatcher_in-tn")
    docs = await mgr.get_pending_raw(limit=50)
    await mgr.promote_to_master(news_event, date_group="2026-03-14")
"""

from __future__ import annotations

import hashlib
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ingestion_engine.core.models import NewsEvent

logger = logging.getLogger(__name__)

# Env var: set to your GCP Project ID in Cloud Run env vars.
# If absent, all Firestore operations become no-ops.
_FIRESTORE_PROJECT = os.getenv("FIRESTORE_PROJECT", "")

_RAW_COLLECTION = "raw_ingestion_buffer"
_MASTER_COLLECTION = "master_news"


def _doc_id_from_url(source_url: str) -> str:
    """Stable, Firestore-safe document ID derived from source_url."""
    return hashlib.sha256(source_url.encode()).hexdigest()[:24]


class FirestoreManager:
    """
    Async Firestore client wrapper.

    A single shared instance is sufficient — AsyncClient is thread-safe and
    reuses gRPC connection pools internally.
    """

    def __init__(self, project: Optional[str] = None) -> None:
        self._project = project or _FIRESTORE_PROJECT
        self._client = None   # lazy — created on first call to _get_client()

    # ------------------------------------------------------------------
    # Internal helpers

    async def _get_client(self):
        """Return the AsyncClient, creating it on first call."""
        if self._client is not None:
            return self._client
        if not self._project:
            return None   # Firestore disabled; caller must handle None
        try:
            from google.cloud import firestore  # type: ignore
            self._client = firestore.AsyncClient(project=self._project)
            logger.info("FirestoreManager: connected to project '%s'.", self._project)
        except Exception as exc:
            logger.warning("FirestoreManager: could not initialise client — %s", exc)
            self._client = None
        return self._client

    def _is_enabled(self) -> bool:
        return bool(self._project)

    # ------------------------------------------------------------------
    # Public API

    async def push_to_raw(
        self,
        events: List[NewsEvent],
        provider_id: str = "unknown",
    ) -> int:
        """
        Write one Firestore document per NewsEvent into raw_ingestion_buffer.

        Returns the number of documents written (0 on error or when disabled).
        Uses a batched write for atomic efficiency (max 500 per batch).
        """
        if not events or not self._is_enabled():
            return 0

        client = await self._get_client()
        if client is None:
            return 0

        from google.cloud import firestore  # type: ignore

        written = 0
        # Firestore batch limit is 500 operations.
        chunk_size = 500
        fetched_at = datetime.now(tz=timezone.utc)

        for i in range(0, len(events), chunk_size):
            chunk = events[i: i + chunk_size]
            batch = client.batch()
            for event in chunk:
                doc_ref = client.collection(_RAW_COLLECTION).document()
                batch.set(doc_ref, {
                    "raw_payload": {
                        "title":       event.title,
                        "snippet":     event.snippet,
                        "source_url":  event.source_url,
                        "source_name": event.source_name,
                        "region_code": event.region_code,
                        "timestamp":   event.timestamp,
                    },
                    "provider_id": provider_id,
                    "fetched_at":  fetched_at,
                    "status":      "pending",
                })
                written += 1
            try:
                await batch.commit()
            except Exception as exc:
                logger.error(
                    "FirestoreManager.push_to_raw: batch commit failed — %s", exc
                )
                written -= len(chunk)   # Rollback count for failed batch

        logger.info(
            "FirestoreManager.push_to_raw: %d docs written to %s.",
            written, _RAW_COLLECTION,
        )
        return written

    async def get_pending_raw(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Return up to `limit` documents from raw_ingestion_buffer where
        status = "pending".

        Each returned dict has:  {"id": str, **fields}
        """
        if not self._is_enabled():
            return []
        client = await self._get_client()
        if client is None:
            return []

        try:
            query = (
                client.collection(_RAW_COLLECTION)
                .where("status", "==", "pending")
                .limit(limit)
            )
            results = []
            async for doc in query.stream():
                data = doc.to_dict()
                data["_doc_id"] = doc.id
                results.append(data)
            return results
        except Exception as exc:
            logger.error("FirestoreManager.get_pending_raw: query failed — %s", exc)
            return []

    async def promote_to_master(
        self,
        event: NewsEvent,
        date_group: str,
        extra_fields: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Upsert a single story into master_news.

        Document ID = SHA-256[:24] of source_url — guarantees idempotency.
        Merges extra_fields (e.g. category, lat/lng) if provided.

        Returns True on success.
        """
        if not self._is_enabled():
            return False
        client = await self._get_client()
        if client is None:
            return False

        from google.cloud import firestore  # type: ignore

        doc_id = _doc_id_from_url(event.source_url)
        doc_ref = client.collection(_MASTER_COLLECTION).document(doc_id)

        payload: Dict[str, Any] = {
            "title":       event.title,
            "snippet":     event.snippet,
            "source_url":  event.source_url,
            "source_name": event.source_name,
            "region_code": event.region_code,
            "timestamp":   event.timestamp,
            "date_group":  date_group,
            "promoted_at": datetime.now(tz=timezone.utc),
        }
        if extra_fields:
            payload.update(extra_fields)

        try:
            # merge=True → update existing fields, add new ones; don't overwrite
            await doc_ref.set(payload, merge=True)
            return True
        except Exception as exc:
            logger.error(
                "FirestoreManager.promote_to_master: write failed for %s — %s",
                doc_id, exc,
            )
            return False

    async def mark_raw_processed(self, doc_ids: List[str]) -> None:
        """
        Batch-update status → "processed" for the given raw_ingestion_buffer docs.
        """
        if not doc_ids or not self._is_enabled():
            return
        client = await self._get_client()
        if client is None:
            return

        from google.cloud import firestore  # type: ignore

        processed_at = datetime.now(tz=timezone.utc)
        chunk_size = 500
        for i in range(0, len(doc_ids), chunk_size):
            batch = client.batch()
            for doc_id in doc_ids[i: i + chunk_size]:
                ref = client.collection(_RAW_COLLECTION).document(doc_id)
                batch.update(ref, {"status": "processed", "processed_at": processed_at})
            try:
                await batch.commit()
            except Exception as exc:
                logger.error(
                    "FirestoreManager.mark_raw_processed: batch failed — %s", exc
                )

    async def query_master(
        self,
        region_code: Optional[str] = None,
        start_date: Optional[str] = None,   # "YYYY-MM-DD"
        end_date: Optional[str] = None,     # "YYYY-MM-DD"
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Query master_news with optional region_code and date_group filters.

        date_group is stored as "YYYY-MM-DD" string so lexicographic comparison
        works correctly for range queries.
        """
        if not self._is_enabled():
            return []
        client = await self._get_client()
        if client is None:
            return []

        try:
            q = client.collection(_MASTER_COLLECTION)
            if region_code:
                q = q.where("region_code", "==", region_code.upper())
            if start_date:
                q = q.where("date_group", ">=", start_date)
            if end_date:
                q = q.where("date_group", "<=", end_date)
            q = q.order_by("timestamp", direction="DESCENDING").limit(limit)

            results = []
            async for doc in q.stream():
                data = doc.to_dict()
                data["_doc_id"] = doc.id
                results.append(data)
            return results
        except Exception as exc:
            logger.error("FirestoreManager.query_master: query failed — %s", exc)
            return []


# ---------------------------------------------------------------------------
# Module-level singleton — import and use directly in routes / runner
# ---------------------------------------------------------------------------

firestore_manager = FirestoreManager()
