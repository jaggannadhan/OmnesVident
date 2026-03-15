"""
ai_geo_refiner.py — Legacy shim.

The canonical implementation is intelligence_layer/refiner.py (Module 16.1).
This module re-exports under the old names so any existing references keep
working without code changes.
"""

from intelligence_layer.refiner import AIRefiner as AIGeoRefiner  # noqa: F401
from intelligence_layer.refiner import ai_refiner as ai_geo_refiner  # noqa: F401

# process_pending() alias for backwards compatibility
AIGeoRefiner.process_pending = AIGeoRefiner.process_buffer  # type: ignore[attr-defined]
