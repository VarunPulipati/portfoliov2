"""
UNLOOP — Trajectory Analysis Service (Phase 1 v2)
"""

from __future__ import annotations

from typing import Dict, List
from datetime import datetime, timedelta
from collections import defaultdict, Counter

from services.database import get_entries, save_insights, update_user
from services.style_taxonomy import (
    normalize_categories,
    normalize_colors,
    detect_price_tier,
    fashion_relevance_score,
)

INTERACTION_WEIGHTS = {"purchase": 5.0, "cart": 3.0, "save": 2.5, "view": 1.0}


def analyze_trajectory(user_id: str) -> dict:
    entries = get_entries(user_id)
    if len(entries) < 12:
        return {"status": "insufficient_data", "count": len(entries)}

    buckets = _bucket_by_week(entries)
    week_keys = sorted(buckets.keys())
    if len(week_keys) < 2:
        return {"status": "insufficient_weeks", "week_count": len(week_keys)}

    timeline = []
    for wk in week_keys:
        weekly_entries = buckets[wk]
        features = _extract_features(weekly_entries)
        state_confidence = _compute_state_confidence(weekly_entries, features)

        timeline.append({
            "week": wk,
            "entry_count": len(weekly_entries),
            "weighted_count": round(sum(e.get("interaction_weight", 1.0) for e in weekly_entries), 2),
            "state_confidence": state_confidence,
            "features": features,
        })

    # only use fashion-relevant weeks for direction / velocity / phase
    fashion_timeline = [
        t for t in timeline
        if t["features"].get("fashion_relevance_ratio", 0) >= 0.45
    ]
    if len(fashion_timeline) < 2:
        fashion_timeline = timeline[-4:]

    direction = _detect_direction(fashion_timeline)
    velocity = _calculate_velocity(fashion_timeline, direction)
    phases = _detect_phases(fashion_timeline)

    domain_dist = defaultdict(int)
    interaction_totals = {"view": 0, "save": 0, "cart": 0, "purchase": 0}
    for e in entries:
        domain_dist[e.get("domain", "")] += 1
        it = e.get("interaction_type", "view")
        interaction_totals[it] = interaction_totals.get(it, 0) + 1

    ts_list = [e["timestamp"] for e in entries if e.get("timestamp")]
    tracking_days = max(1, _days_between(ts_list[0], ts_list[-1])) if len(ts_list) >= 2 else 1

    insights = {
        "generated_at": datetime.utcnow().isoformat(),
        "total_tracked": len(entries),
        "tracking_days": tracking_days,
        "feature_timeline": timeline,
        "fashion_feature_timeline": fashion_timeline,
        "direction": direction,
        "velocity": velocity,
        "phase_transitions": phases,
        "interaction_totals": interaction_totals,
        "top_domains": sorted(
            [{"domain": d, "count": c} for d, c in domain_dist.items()],
            key=lambda x: x["count"],
            reverse=True
        )[:15],
        "weekly_activity": [
            {
                "week": t["week"],
                "items": t["entry_count"],
                "confidence": t["state_confidence"],
                "fashion_relevance_ratio": t["features"].get("fashion_relevance_ratio", 0),
            }
            for t in timeline
        ]
    }

    save_insights(user_id, insights)

    tier = "general"
    if len(entries) >= 20 and direction.get("status") == "analyzed":
        tier = "emerging"
    if len(fashion_timeline) >= 6 and len(direction.get("emerging_interests", {})) >= 2 and direction.get("direction_confidence", 0) >= 0.55:
        tier = "personal"
    update_user(user_id, tier=tier)

    return {"status": "analyzed", "insights": insights}


def _bucket_by_week(entries: List[dict]) -> Dict[str, List[dict]]:
    buckets = {}
    for e in entries:
        d = datetime.fromisoformat(e["timestamp"].replace("Z", "+00:00"))
        week_start = d - timedelta(days=d.weekday())
        key = week_start.strftime("%Y-%m-%d")
        buckets.setdefault(key, []).append(e)
    return buckets


def _extract_features(entries: List[dict]) -> dict:
    raw_cats = Counter()
    norm_cats = Counter()
    style_clusters = Counter()
    colors = Counter()
    color_families = Counter()
    brands = Counter()
    prices = []
    interaction = {"view": 0, "save": 0, "cart": 0, "purchase": 0}
    domains = set()
    total_dwell = 0.0
    high_count = 0
    raw_category_count = 0
    normalized_coverage_values = []

    fashion_entries = 0
    excluded_entries = 0

    for e in entries:
        w = float(e.get("interaction_weight", INTERACTION_WEIGHTS.get(e.get("interaction_type", "view"), 1.0)))
        it = e.get("interaction_type", "view")
        interaction[it] = interaction.get(it, 0) + 1
        total_dwell += float(e.get("dwell_time_seconds", 0) or 0)
        domains.add(e.get("domain", ""))
        if e.get("is_high_signal"):
            high_count += 1

        ef = e.get("extracted_features", {}) or {}
        brand = str(ef.get("brand", "") or "").strip().lower()
        page_heading = ef.get("page_heading", "") or ""
        image_signals = ef.get("image_signals", []) or []
        raw_categories = ef.get("categories", []) or []
        raw_colors = ef.get("colors", []) or []
        has_price = ef.get("price") is not None

        norm = normalize_categories(
            raw_categories=raw_categories,
            page_heading=page_heading,
            image_signals=image_signals,
            brand=brand
        )

        relevance = fashion_relevance_score(
            raw_categories=raw_categories,
            normalized_categories=norm["normalized_categories"],
            style_clusters=norm["style_clusters"],
            brand=brand,
            domain=e.get("domain", ""),
            page_heading=page_heading,
            has_price=has_price,
        )

        if relevance < 0.35:
            excluded_entries += 1
            continue

        fashion_entries += 1
        raw_category_count += norm["raw_count"]
        normalized_coverage_values.append(norm["normalized_coverage"])

        for c in raw_categories:
            cleaned = str(c).strip().lower()
            if cleaned:
                raw_cats[cleaned] += w * relevance

        for c in norm["normalized_categories"]:
            norm_cats[c] += w * relevance
        for sc in norm["style_clusters"]:
            style_clusters[sc] += w * relevance

        color_info = normalize_colors(raw_colors)
        for c in color_info["normalized_colors"]:
            colors[c] += w * relevance
        for fam in color_info["color_families"]:
            color_families[fam] += w * relevance

        if brand:
            brands[brand] += w * relevance

        price = ef.get("price")
        try:
            price_val = float(price) if price is not None else None
        except Exception:
            price_val = None
        if price_val and 0 < price_val < 10000:
            prices.append({"value": price_val, "weight": w * relevance})

    dominant_categories = dict(sorted(norm_cats.items(), key=lambda x: x[1], reverse=True)[:12])
    raw_top_categories = dict(sorted(raw_cats.items(), key=lambda x: x[1], reverse=True)[:12])
    top_style_clusters = dict(sorted(style_clusters.items(), key=lambda x: x[1], reverse=True)[:8])
    top_brands = dict(sorted(brands.items(), key=lambda x: x[1], reverse=True)[:10])

    price_range = None
    if prices:
        vals = [p["value"] for p in prices]
        wsum = sum(p["value"] * p["weight"] for p in prices)
        wtot = sum(p["weight"] for p in prices)
        avg = round(wsum / wtot, 2) if wtot else 0
        price_range = {
            "min": min(vals),
            "max": max(vals),
            "avg": avg,
            "median": sorted(vals)[len(vals) // 2],
            "tier": detect_price_tier(avg)
        }

    top_colors = [{"color": c, "count": round(n, 1)} for c, n in sorted(colors.items(), key=lambda x: x[1], reverse=True)[:8]]
    top_color_families = [{"family": c, "count": round(n, 1)} for c, n in sorted(color_families.items(), key=lambda x: x[1], reverse=True)[:5]]

    avg_norm_coverage = round(sum(normalized_coverage_values) / len(normalized_coverage_values), 3) if normalized_coverage_values else 0.0
    fashion_ratio = round(fashion_entries / max(len(entries), 1), 3)

    return {
        "dominant_categories": dominant_categories,
        "raw_top_categories": raw_top_categories,
        "style_clusters": top_style_clusters,
        "price_range": price_range,
        "top_colors": top_colors,
        "color_families": top_color_families,
        "brand_signals": top_brands,
        "interaction_breakdown": interaction,
        "avg_dwell_time": round(total_dwell / len(entries), 1) if entries else 0,
        "domain_diversity": len(domains),
        "high_signal_ratio": round(high_count / len(entries), 2) if entries else 0,
        "raw_category_count": raw_category_count,
        "normalized_category_coverage": avg_norm_coverage,
        "fashion_relevant_entry_count": fashion_entries,
        "excluded_entry_count": excluded_entries,
        "fashion_relevance_ratio": fashion_ratio,
    }


def _compute_state_confidence(entries: List[dict], features: dict) -> float:
    n = len(entries)
    high_ratio = float(features.get("high_signal_ratio", 0))
    avg_dwell = float(features.get("avg_dwell_time", 0))
    domain_diversity = float(features.get("domain_diversity", 0))
    norm_cov = float(features.get("normalized_category_coverage", 0))
    fashion_ratio = float(features.get("fashion_relevance_ratio", 0))

    interaction = features.get("interaction_breakdown", {})
    signal_actions = interaction.get("save", 0) + interaction.get("cart", 0) + interaction.get("purchase", 0)
    signal_ratio = signal_actions / max(sum(interaction.values()), 1)

    volume_score = min(n / 8.0, 1.0)
    dwell_score = min(avg_dwell / 45.0, 1.0)
    diversity_score = min(domain_diversity / 5.0, 1.0)

    confidence = (
        0.20 * volume_score +
        0.15 * high_ratio +
        0.15 * dwell_score +
        0.10 * signal_ratio +
        0.05 * diversity_score +
        0.15 * norm_cov +
        0.20 * fashion_ratio
    )
    return round(min(max(confidence, 0.0), 1.0), 3)


def _detect_direction(timeline: List[dict]) -> dict:
    if len(timeline) < 2:
        return {"status": "insufficient_data"}

    ws = max(2, int(round(len(timeline) * 0.35)))
    older = timeline[:ws]
    recent = timeline[-ws:]

    def merge_weighted(tl: List[dict], feature_key: str) -> Dict[str, float]:
        acc = defaultdict(float)
        total_weight = 0.0
        for t in tl:
            conf = max(float(t.get("state_confidence", 0.1)), 0.1)
            total_weight += conf
            for k, v in t["features"].get(feature_key, {}).items():
                acc[k] += float(v) * conf
        if total_weight <= 0:
            return {}
        return {k: round(v / total_weight, 3) for k, v in acc.items()}

    old_cats = merge_weighted(older, "dominant_categories")
    new_cats = merge_weighted(recent, "dominant_categories")
    old_clusters = merge_weighted(older, "style_clusters")
    new_clusters = merge_weighted(recent, "style_clusters")

    emerging = {}
    declining = {}
    stable = {}

    recent_support = Counter()
    for t in recent:
        for c in t["features"].get("dominant_categories", {}):
            recent_support[c] += 1

    keys = set(old_cats.keys()) | set(new_cats.keys())
    for cat in keys:
        old_v = old_cats.get(cat, 0.0)
        new_v = new_cats.get(cat, 0.0)
        delta = new_v - old_v
        threshold = max(0.6, (old_v + new_v) * 0.18)

        if delta > threshold and recent_support.get(cat, 0) >= 1:
            emerging[cat] = round(delta, 3)
        elif delta < -threshold:
            declining[cat] = round(abs(delta), 3)
        elif max(old_v, new_v) > 0.5:
            stable[cat] = round((old_v + new_v) / 2.0, 3)

    emerging_clusters = {}
    for sc in set(old_clusters.keys()) | set(new_clusters.keys()):
        old_v = old_clusters.get(sc, 0.0)
        new_v = new_clusters.get(sc, 0.0)
        delta = new_v - old_v
        if delta > 0.25:
            emerging_clusters[sc] = round(delta, 3)

    old_prices = [t["features"]["price_range"]["avg"] for t in older if t["features"].get("price_range")]
    new_prices = [t["features"]["price_range"]["avg"] for t in recent if t["features"].get("price_range")]
    price_direction = "unknown"
    if old_prices and new_prices:
        old_avg = _avg(old_prices)
        new_avg = _avg(new_prices)
        if old_avg > 0:
            pct = (new_avg - old_avg) / old_avg
            if pct > 0.12:
                price_direction = "upgrading"
            elif pct < -0.12:
                price_direction = "economizing"
            else:
                price_direction = "stable"

    old_brands = set(b for t in older for b in t["features"].get("brand_signals", {}))
    new_brands = set(b for t in recent for b in t["features"].get("brand_signals", {}))
    if len(new_brands) > len(old_brands) + 1:
        brand_direction = "diversifying"
    elif len(new_brands) + 1 < len(old_brands):
        brand_direction = "consolidating"
    else:
        brand_direction = "stable"

    direction_confidence = round(
        min(
            1.0,
            (
                _avg([t.get("state_confidence", 0.0) for t in recent]) * 0.55 +
                min(len(emerging) / 3.0, 1.0) * 0.25 +
                min(len(emerging_clusters) / 2.0, 1.0) * 0.20
            )
        ),
        3
    )

    return {
        "status": "analyzed",
        "emerging_interests": dict(sorted(emerging.items(), key=lambda x: x[1], reverse=True)[:8]),
        "declining_interests": dict(sorted(declining.items(), key=lambda x: x[1], reverse=True)[:8]),
        "stable_interests": dict(sorted(stable.items(), key=lambda x: x[1], reverse=True)[:8]),
        "emerging_style_clusters": dict(sorted(emerging_clusters.items(), key=lambda x: x[1], reverse=True)[:5]),
        "price_direction": price_direction,
        "brand_direction": brand_direction,
        "direction_confidence": direction_confidence
    }


def _calculate_velocity(timeline: List[dict], direction: dict) -> dict:
    if len(timeline) < 2:
        return {"score": 0.5, "label": "unknown", "trend": "unknown"}

    changes = []
    coherences = []

    target_cats = set(direction.get("emerging_interests", {}).keys())

    for i in range(1, len(timeline)):
        prev = timeline[i - 1]
        curr = timeline[i]

        prev_cats = prev["features"].get("dominant_categories", {})
        curr_cats = curr["features"].get("dominant_categories", {})
        keys = set(prev_cats.keys()) | set(curr_cats.keys())

        magnitude = sum(abs(curr_cats.get(k, 0) - prev_cats.get(k, 0)) for k in keys)

        if target_cats:
            changed_toward_target = sum(
                max(curr_cats.get(k, 0) - prev_cats.get(k, 0), 0)
                for k in target_cats
            )
            coherence = min(changed_toward_target / max(magnitude, 0.001), 1.0)
        else:
            coherence = 0.5

        conf = (prev.get("state_confidence", 0.5) + curr.get("state_confidence", 0.5)) / 2.0
        adjusted = magnitude * (0.55 + 0.45 * coherence) * (0.7 + 0.3 * conf)

        changes.append(adjusted)
        coherences.append(coherence)

    avg_change = _avg(changes)
    avg_coherence = _avg(coherences)

    raw_score = min(1.0, avg_change / 5.0)
    # stronger penalty when coherence is weak
    score = round(min(1.0, raw_score * (0.45 + 0.55 * avg_coherence)), 3)

    trend = "stable"
    if len(changes) >= 4:
        first_half = _avg(changes[:len(changes)//2])
        second_half = _avg(changes[len(changes)//2:])
        if second_half > first_half * 1.2:
            trend = "accelerating"
        elif second_half < first_half * 0.8:
            trend = "decelerating"

    if score < 0.15:
        label = "anchored"
    elif score < 0.35:
        label = "steady"
    elif score < 0.55:
        label = "flowing"
    elif score < 0.75:
        label = "shifting"
    else:
        label = "transforming"

    return {
        "score": score,
        "label": label,
        "trend": trend,
        "avg_weekly_change": round(avg_change, 3),
        "coherence": round(avg_coherence, 3),
        "data_points": len(changes)
    }


def _detect_phases(timeline: List[dict]) -> List[dict]:
    if len(timeline) < 4:
        return []

    phases = []

    for i in range(2, len(timeline) - 1):
        before = timeline[max(0, i - 2):i]
        after = timeline[i:min(len(timeline), i + 2)]

        before_cats = set()
        after_cats = set()
        before_clusters = set()
        after_clusters = set()

        before_conf = _avg([t.get("state_confidence", 0.0) for t in before])
        after_conf = _avg([t.get("state_confidence", 0.0) for t in after])

        for t in before:
            before_cats.update(t["features"].get("dominant_categories", {}).keys())
            before_clusters.update(t["features"].get("style_clusters", {}).keys())
        for t in after:
            after_cats.update(t["features"].get("dominant_categories", {}).keys())
            after_clusters.update(t["features"].get("style_clusters", {}).keys())

        new_cats = list(after_cats - before_cats)
        dropped_cats = list(before_cats - after_cats)

        cat_union = before_cats | after_cats
        change_ratio = (len(new_cats) + len(dropped_cats)) / max(len(cat_union), 1)

        old_price = _avg([t["features"]["price_range"]["avg"] for t in before if t["features"].get("price_range")])
        new_price = _avg([t["features"]["price_range"]["avg"] for t in after if t["features"].get("price_range")])

        phase_type = "style_shift"
        if old_price and new_price and new_price > old_price * 1.18:
            phase_type = "price_upgrade"
        elif old_price and new_price and new_price < old_price * 0.82:
            phase_type = "price_drop"
        elif before_clusters != after_clusters:
            phase_type = "cluster_shift"

        sustained = False
        if i + 1 < len(timeline):
            next_cats = set(timeline[i + 1]["features"].get("dominant_categories", {}).keys())
            sustained = len(next_cats & after_cats) >= max(1, len(after_cats) // 3)

        if change_ratio > 0.35 and before_conf >= 0.35 and after_conf >= 0.35 and sustained:
            phase_conf = round(min(1.0, (change_ratio * 0.6) + ((before_conf + after_conf) / 2.0) * 0.4), 3)
            phases.append({
                "week": timeline[i]["week"],
                "magnitude": round(change_ratio, 3),
                "phase_type": phase_type,
                "phase_confidence": phase_conf,
                "new_categories": new_cats[:6],
                "dropped_categories": dropped_cats[:6],
                "description": f"Shift from {', '.join(dropped_cats[:2]) or 'older preferences'} toward {', '.join(new_cats[:2]) or 'newer preferences'}"
            })

    return phases[-6:]


def _avg(values: List[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _days_between(a: str, b: str) -> int:
    try:
        da = datetime.fromisoformat(a.replace("Z", ""))
        db = datetime.fromisoformat(b.replace("Z", ""))
        return abs((db - da).days)
    except Exception:
        return 0