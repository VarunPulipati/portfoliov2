"""
UNLOOP — Path Matcher (Phase 1 upgraded)

Improvements:
- two-stage heuristic matching
- confidence filtering
- normalized category / style-cluster similarity
- future usefulness and transition coherence
"""

from __future__ import annotations

from typing import Dict, List, Any, Tuple
from services.database import get_all_user_timelines


def find_path_matches(
    current_features: dict,
    velocity_score: float = 0.5,
    num_matches: int = 10,
    lookahead_weeks: int = 12,
    exclude_user: str = None
) -> List[dict]:
    all_timelines = get_all_user_timelines()
    candidates = []

    for uid, timeline in all_timelines.items():
        if uid == exclude_user or len(timeline) < 3:
            continue

        local_candidates = _retrieve_candidate_points(
            timeline=timeline,
            current_features=current_features,
            lookahead_weeks=lookahead_weeks
        )

        for cand in local_candidates:
            candidates.append((uid, cand))

    reranked = []
    for uid, cand in candidates:
        reranked.append(_rerank_candidate(uid, cand, current_features, velocity_score))

    reranked = [r for r in reranked if r["similarity_score"] >= 0.35 and r["match_confidence"] >= 0.35]
    reranked.sort(key=lambda x: x["similarity_score"], reverse=True)
    return reranked[:num_matches]


def _retrieve_candidate_points(timeline: List[dict], current_features: dict, lookahead_weeks: int) -> List[dict]:
    output = []

    current_cats = set(current_features.get("dominant_categories", {}).keys())
    current_clusters = set(current_features.get("style_clusters", {}).keys())
    current_price_tier = current_features.get("price_range", {}).get("tier", "unknown")

    for i in range(len(timeline) - 1):
        past = timeline[i]
        if float(past.get("state_confidence", 0.0)) < 0.30:
            continue

        past_features = past.get("features", {})
        past_cats = set(past_features.get("dominant_categories", {}).keys())
        past_clusters = set(past_features.get("style_clusters", {}).keys())
        past_price_tier = past_features.get("price_range", {}).get("tier", "unknown")

        cat_overlap = _jaccard(current_cats, past_cats)
        cluster_overlap = _jaccard(current_clusters, past_clusters)

        if max(cat_overlap, cluster_overlap) < 0.15:
            continue

        # price-band compatibility is soft, not mandatory
        price_band_score = 1.0 if current_price_tier == "unknown" or past_price_tier == "unknown" else (1.0 if current_price_tier == past_price_tier else 0.6)

        coarse_score = (cat_overlap * 0.55) + (cluster_overlap * 0.30) + (price_band_score * 0.15)
        if coarse_score < 0.28:
            continue

        fi = min(i + lookahead_weeks, len(timeline) - 1)
        if fi <= i:
            continue

        future = timeline[fi]
        if float(future.get("state_confidence", 0.0)) < 0.30:
            continue

        output.append({
            "past_index": i,
            "future_index": fi,
            "past_state": past,
            "future_state": future,
            "coarse_score": round(coarse_score, 3)
        })

    return output


def _rerank_candidate(uid: str, cand: dict, current_features: dict, velocity_score: float) -> dict:
    past = cand["past_state"]
    future = cand["future_state"]
    past_features = past.get("features", {})
    future_features = future.get("features", {})

    state_similarity = _similarity(current_features, past_features)
    evolution_magnitude = _evolution(past_features, future_features)
    transition_coherence = _transition_coherence(past_features, future_features)
    future_usefulness = _future_usefulness(current_features, future_features)
    hist_velocity = _two_point_velocity(past_features, future_features)
    velocity_compatibility = 1.0 - abs(velocity_score - hist_velocity)

    match_confidence = round(
        min(
            1.0,
            (float(past.get("state_confidence", 0.0)) * 0.45) +
            (float(future.get("state_confidence", 0.0)) * 0.35) +
            (transition_coherence * 0.20)
        ),
        3
    )

    final_score = (
        state_similarity * 0.33 +
        future_usefulness * 0.24 +
        transition_coherence * 0.18 +
        evolution_magnitude * 0.13 +
        velocity_compatibility * 0.12
    )

    return {
        "user_id": uid,
        "similarity_score": round(final_score, 3),
        "match_confidence": match_confidence,
        "direction_alignment": round(future_usefulness, 3),
        "transition_coherence": round(transition_coherence, 3),
        "future_usefulness_score": round(future_usefulness, 3),
        "velocity_label": _vel_label(hist_velocity),
        "velocity_compatibility": round(velocity_compatibility, 3),
        "past_features": _summarize(past_features),
        "future_features": _summarize(future_features),
        "transition_items": _transitions(past_features, future_features),
        "weeks_ahead": cand["future_index"] - cand["past_index"]
    }


def _similarity(a: dict, b: dict) -> float:
    score = 0.0
    weight = 0.0

    a_cats = set(a.get("dominant_categories", {}).keys())
    b_cats = set(b.get("dominant_categories", {}).keys())
    if a_cats or b_cats:
        score += _jaccard(a_cats, b_cats) * 0.40
        weight += 0.40

    a_clusters = set(a.get("style_clusters", {}).keys())
    b_clusters = set(b.get("style_clusters", {}).keys())
    if a_clusters or b_clusters:
        score += _jaccard(a_clusters, b_clusters) * 0.20
        weight += 0.20

    pa = a.get("price_range", {}).get("avg")
    pb = b.get("price_range", {}).get("avg")
    if pa and pb and max(pa, pb) > 0:
        score += (1.0 - min(abs(pa - pb) / max(pa, pb), 1.0)) * 0.20
        weight += 0.20

    a_color = set((c["family"] if isinstance(c, dict) else c) for c in a.get("color_families", []))
    b_color = set((c["family"] if isinstance(c, dict) else c) for c in b.get("color_families", []))
    if a_color or b_color:
        score += _jaccard(a_color, b_color) * 0.10
        weight += 0.10

    a_brands = set(a.get("brand_signals", {}).keys())
    b_brands = set(b.get("brand_signals", {}).keys())
    if a_brands or b_brands:
        score += _jaccard(a_brands, b_brands) * 0.10
        weight += 0.10

    return round(score / weight, 3) if weight > 0 else 0.0


def _evolution(past: dict, future: dict) -> float:
    past_cats = set(past.get("dominant_categories", {}).keys())
    future_cats = set(future.get("dominant_categories", {}).keys())
    past_clusters = set(past.get("style_clusters", {}).keys())
    future_clusters = set(future.get("style_clusters", {}).keys())

    cat_shift = (len(future_cats - past_cats) + len(past_cats - future_cats)) / max(len(past_cats | future_cats), 1)
    cluster_shift = (len(future_clusters - past_clusters) + len(past_clusters - future_clusters)) / max(len(past_clusters | future_clusters), 1)

    return round(min(1.0, (cat_shift * 0.65) + (cluster_shift * 0.35)), 3)


def _transition_coherence(past: dict, future: dict) -> float:
    past_cats = set(past.get("dominant_categories", {}).keys())
    future_cats = set(future.get("dominant_categories", {}).keys())
    new_cats = future_cats - past_cats

    past_clusters = set(past.get("style_clusters", {}).keys())
    future_clusters = set(future.get("style_clusters", {}).keys())

    cluster_progression = 1.0 if future_clusters != past_clusters else 0.55
    novelty = min(len(new_cats) / 4.0, 1.0)

    old_price = past.get("price_range", {}).get("avg")
    new_price = future.get("price_range", {}).get("avg")
    price_continuity = 0.7
    if old_price and new_price:
        ratio = new_price / max(old_price, 1.0)
        if 0.75 <= ratio <= 1.35:
            price_continuity = 1.0
        elif 0.55 <= ratio <= 1.75:
            price_continuity = 0.8
        else:
            price_continuity = 0.55

    return round(min(1.0, novelty * 0.35 + cluster_progression * 0.35 + price_continuity * 0.30), 3)


def _future_usefulness(current: dict, future: dict) -> float:
    current_cats = set(current.get("dominant_categories", {}).keys())
    future_cats = set(future.get("dominant_categories", {}).keys())
    new_future = future_cats - current_cats

    current_clusters = set(current.get("style_clusters", {}).keys())
    future_clusters = set(future.get("style_clusters", {}).keys())
    cluster_gain = len(future_clusters - current_clusters)

    if not future_cats and not future_clusters:
        return 0.0

    usefulness = min(len(new_future) / 4.0, 1.0) * 0.65 + min(cluster_gain / 2.0, 1.0) * 0.35
    return round(min(1.0, usefulness), 3)


def _two_point_velocity(past: dict, future: dict) -> float:
    a = past.get("dominant_categories", {})
    b = future.get("dominant_categories", {})
    keys = set(list(a.keys()) + list(b.keys()))
    change = sum(abs(a.get(k, 0) - b.get(k, 0)) for k in keys)
    return round(min(1.0, change / 5.0), 3)


def _vel_label(score: float) -> str:
    if score < 0.15:
        return "anchored"
    if score < 0.35:
        return "steady"
    if score < 0.55:
        return "flowing"
    if score < 0.75:
        return "shifting"
    return "transforming"


def _transitions(past: dict, future: dict) -> List[dict]:
    output = []

    past_cats = set(past.get("dominant_categories", {}).keys())
    future_cats = future.get("dominant_categories", {})
    for cat, strength in future_cats.items():
        if cat not in past_cats:
            output.append({"category": cat, "strength": round(float(strength), 3), "type": "new_interest"})

    past_clusters = set(past.get("style_clusters", {}).keys())
    future_clusters = future.get("style_clusters", {})
    for sc, strength in future_clusters.items():
        if sc not in past_clusters:
            output.append({"category": sc, "strength": round(float(strength), 3), "type": "style_cluster_shift"})

    past_price = past.get("price_range", {}).get("avg")
    future_price = future.get("price_range", {}).get("avg")
    if past_price and future_price:
        if future_price > past_price * 1.2:
            output.append({"category": "price_upgrade", "from": round(past_price, 2), "to": round(future_price, 2), "type": "price_shift"})
        elif future_price < past_price * 0.8:
            output.append({"category": "price_downgrade", "from": round(past_price, 2), "to": round(future_price, 2), "type": "price_shift"})

    return output[:10]


def _summarize(features: dict) -> dict:
    return {
        "top_categories": list(features.get("dominant_categories", {}).keys())[:5],
        "style_clusters": list(features.get("style_clusters", {}).keys())[:4],
        "price_avg": features.get("price_range", {}).get("avg"),
        "price_tier": features.get("price_range", {}).get("tier"),
        "top_colors": [c["color"] if isinstance(c, dict) else c for c in features.get("top_colors", [])][:5],
        "confidence": features.get("state_confidence")
    }


def _jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 0.0
    return len(a & b) / max(len(a | b), 1)