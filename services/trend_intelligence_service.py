"""
UNLOOP — Trend intelligence service (Phase 1 seeded version)

Phase 1:
- manually seeded trend signals
- source-backed
- taxonomy-aligned
"""

from __future__ import annotations

from typing import Dict, List
from services.source_registry import SOURCE_REGISTRY

SEEDED_TREND_SIGNALS = [
    {
        "trend": "structured minimalism",
        "mapped_terms": ["minimalist", "structured", "basics", "tailored"],
        "trajectory_tags": ["minimalist-destination", "smart-casual-destination", "bridge"],
        "source_ids": ["vogue_editorial", "who_what_wear"],
        "freshness": 0.92,
        "confidence": 0.90,
        "description": "Cleaner silhouettes, premium basics, quieter construction."
    },
    {
        "trend": "earth tone refinement",
        "mapped_terms": ["earth tones", "quiet luxury", "linen", "wool"],
        "trajectory_tags": ["earth-tones-trend", "minimalist-destination", "bridge"],
        "source_ids": ["vogue_editorial", "bazaar_editorial"],
        "freshness": 0.88,
        "confidence": 0.84,
        "description": "Muted palettes, soft tailoring, grounded premium neutrals."
    },
    {
        "trend": "elevated smart casual",
        "mapped_terms": ["smart casual", "structured", "classic", "loafers"],
        "trajectory_tags": ["smart-casual-destination", "bridge"],
        "source_ids": ["who_what_wear", "bazaar_editorial"],
        "freshness": 0.83,
        "confidence": 0.81,
        "description": "Relaxed tailoring, polished separates, wearable formality."
    },
    {
        "trend": "technical everyday wear",
        "mapped_terms": ["techwear", "technical", "outdoor", "gorpcore"],
        "trajectory_tags": ["techwear-destination", "bridge"],
        "source_ids": ["highsnobiety", "creator_signal"],
        "freshness": 0.80,
        "confidence": 0.78,
        "description": "Technical fabrics and functional layering in everyday wardrobes."
    },
]


def _source_weight_map() -> Dict[str, float]:
    return {s["source_id"]: s["weight"] for s in SOURCE_REGISTRY}


def get_ranked_trend_signals() -> List[dict]:
    weights = _source_weight_map()
    ranked = []

    for signal in SEEDED_TREND_SIGNALS:
        source_score = 0.0
        for sid in signal["source_ids"]:
            source_score += weights.get(sid, 0.6)
        source_score = source_score / max(len(signal["source_ids"]), 1)

        final_score = (
            signal["freshness"] * 0.35 +
            signal["confidence"] * 0.35 +
            source_score * 0.30
        )

        ranked.append({
            **signal,
            "source_score": round(source_score, 3),
            "final_score": round(final_score, 3),
        })

    ranked.sort(key=lambda x: x["final_score"], reverse=True)
    return ranked


def get_fallback_tags(limit: int = 4) -> List[str]:
    ranked = get_ranked_trend_signals()[:limit]
    tags = []
    for r in ranked:
        tags.extend(r["trajectory_tags"])
    # keep order, dedupe
    seen = set()
    out = []
    for t in tags:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


def get_trend_summary() -> dict:
    ranked = get_ranked_trend_signals()
    return {
        "updated_from_sources": True,
        "signals": ranked[:4]
    }