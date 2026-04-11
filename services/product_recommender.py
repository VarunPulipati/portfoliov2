"""
UNLOOP — Product Recommendation Service (Phase 1 v4)
Grouped rows + row-level explanations + accessories + best value
Also supports general fallback without user data.
"""

from __future__ import annotations

from collections import Counter
from typing import Dict, List

from services.database import get_products_by_tags, get_insights
from services.path_matcher import find_path_matches
from services.trend_intelligence_service import get_fallback_tags, get_trend_summary


TRAJECTORY_TAG_MAP = {
    "minimalist": ["minimalist-destination", "bridge"],
    "structured": ["smart-casual-destination", "bridge"],
    "basics": ["minimalist-destination", "bridge"],
    "quality fabrics": ["minimalist-destination", "earth-tones-trend"],
    "earth tones": ["earth-tones-trend", "minimalist-destination", "bridge"],
    "smart casual": ["smart-casual-destination", "bridge"],
    "techwear": ["techwear-destination", "bridge"],
    "technical": ["techwear-destination", "bridge"],
    "gorpcore": ["techwear-destination", "bridge"],
    "outdoor": ["techwear-destination", "bridge"],
    "quiet luxury": ["earth-tones-trend", "smart-casual-destination"],
    "scandinavian": ["minimalist-destination", "bridge"],
    "tailored": ["smart-casual-destination", "bridge"],
    "streetwear": ["bridge"],
    "athleisure": ["bridge"],
    "smart_casual": ["smart-casual-destination", "bridge"],
    "quiet_luxury": ["smart-casual-destination", "earth-tones-trend"],
}

NON_FASHION_TERMS = {"apple", "iphone", "cell phones", "unlocked", "plus", "jobs", "job", "scientist"}

ACCESSORY_CATEGORIES = {"accessories", "bags", "jewelry", "watches", "belts", "sunglasses"}
FOOTWEAR_CATEGORIES = {"footwear", "sneakers", "boots", "loafers", "heels", "sandals", "mules"}


def get_general_recommendations(limit: int = 16) -> Dict[str, any]:
    return _trend_based_recommendations(limit)


def _get_current_features(insights: dict) -> dict:
    timeline = insights.get("fashion_feature_timeline") or insights.get("feature_timeline", [])
    if not timeline:
        return {}
    return timeline[-1].get("features", {})


def _tags_from_terms(terms):
    tags = set()
    for term in terms:
        t = str(term).lower()
        for key, mapped_tags in TRAJECTORY_TAG_MAP.items():
            if key in t or t in key:
                tags.update(mapped_tags)
    return tags


def _collect_match_tags(matches):
    future_terms = Counter()
    for match in matches:
        for cat in match.get("future_features", {}).get("top_categories", []):
            future_terms[str(cat).lower()] += 1
        for sc in match.get("future_features", {}).get("style_clusters", []):
            future_terms[str(sc).lower()] += 2
    top_terms = [term for term, _ in future_terms.most_common(8)]
    return _tags_from_terms(top_terms)


def _clean_terms(terms):
    return [t for t in terms if t not in NON_FASHION_TERMS]


def _trend_based_recommendations(limit: int) -> Dict[str, any]:
    tags = get_fallback_tags()
    products = get_products_by_tags(tags, max(limit, 24))
    trend_summary = get_trend_summary()

    scored = []
    for p in products:
        p = dict(p)
        p["role"] = "bridge"
        p["current_fit_score"] = 0.45
        p["future_fit_score"] = 0.60
        p["bridge_score"] = 0.65
        p["final_rank_score"] = 0.60
        p["deal_type"] = _deal_type(p)
        p["tile_badge"] = _tile_badge(p)
        scored.append(p)

    rows = _build_rows(
        products=scored,
        emerging={},
        emerging_clusters={},
        vel_label="steady",
        price_dir="stable",
    )

    top_signal = trend_summary["signals"][0]["trend"] if trend_summary["signals"] else "current trend signals"
    return {
        "tier": "general",
        "message": f"These are trend-based recommendations until your personal shopping profile is ready. Top signal: {top_signal}.",
        "trend_context": trend_summary,
        "rows": rows,
        "products": scored[:limit]
    }


def get_recommendations_for_user(user_id: str, limit: int = 16) -> Dict[str, any]:
    insights = get_insights(user_id)
    if not insights or not insights.get("direction"):
        return _trend_based_recommendations(limit)

    direction = insights.get("direction", {})
    velocity = insights.get("velocity", {})
    current_features = _get_current_features(insights)

    if not current_features:
        return _trend_based_recommendations(limit)

    vel_label = velocity.get("label", "flowing")
    velocity_score = velocity.get("score", 0.5)
    emerging = direction.get("emerging_interests", {})
    emerging_clusters = direction.get("emerging_style_clusters", {})
    declining = set(direction.get("declining_interests", {}).keys())
    price_dir = direction.get("price_direction", "unknown")

    matches = find_path_matches(
        current_features=current_features,
        velocity_score=velocity_score,
        num_matches=12,
        lookahead_weeks=8,
        exclude_user=user_id
    )

    target_terms = _clean_terms(list(emerging.keys()) + list(emerging_clusters.keys()))
    target_tags = _tags_from_terms(target_terms)
    target_tags.update(_collect_match_tags(matches))

    if not target_tags:
        target_tags = set(get_fallback_tags())

    products = get_products_by_tags(list(target_tags), limit * 5)
    if not products:
        return _trend_based_recommendations(limit)

    scored = []
    for p in products:
        scored_product = _score_product(
            product=p,
            current_features=current_features,
            emerging=emerging,
            emerging_clusters=emerging_clusters,
            declining=declining,
            vel_label=vel_label,
            price_dir=price_dir
        )
        scored.append(scored_product)

    scored.sort(key=lambda x: x["final_rank_score"], reverse=True)

    tier = "personal" if len(emerging) >= 2 else "emerging"
    summary = _generate_summary(emerging, emerging_clusters, vel_label, price_dir, len(matches))

    rows = _build_rows(
        products=scored,
        emerging=emerging,
        emerging_clusters=emerging_clusters,
        vel_label=vel_label,
        price_dir=price_dir,
    )

    return {
        "tier": tier,
        "message": summary,
        "velocity": vel_label,
        "emerging_interests": list(emerging.keys()),
        "rows": rows,
        "products": scored[:limit]
    }


def _score_product(product, current_features, emerging, emerging_clusters, declining, vel_label, price_dir):
    item_terms = set(str(t).lower() for t in (
        product.get("trajectory_tags", []) +
        product.get("style_tags", []) +
        product.get("categories", [])
    ))

    current_terms = set(current_features.get("dominant_categories", {}).keys()) | set(current_features.get("style_clusters", {}).keys())
    future_terms = set(_clean_terms(set(emerging.keys()) | set(emerging_clusters.keys())))

    current_fit = _term_overlap_score(item_terms, current_terms)
    future_fit = _term_overlap_score(item_terms, future_terms)

    bridge_signal = 0.0
    if "bridge" in item_terms:
        bridge_signal += 0.60
    if current_fit > 0 and future_fit > 0:
        bridge_signal += 0.40
    bridge_score = min(1.0, bridge_signal)

    role = _assign_role(current_fit, future_fit, bridge_score, item_terms)

    velocity_bonus = _velocity_role_bonus(vel_label, role)
    price_bonus = _price_alignment_bonus(price_dir, product.get("price"))
    decline_penalty = 0.15 if item_terms & set(map(str.lower, declining)) else 0.0
    value_bonus = _value_bonus(product)

    final_rank = (
        current_fit * 0.20 +
        future_fit * 0.30 +
        bridge_score * 0.22 +
        velocity_bonus * 0.12 +
        price_bonus * 0.08 +
        value_bonus * 0.08
    ) - decline_penalty

    product = dict(product)
    product["role"] = role
    product["current_fit_score"] = round(current_fit, 3)
    product["future_fit_score"] = round(future_fit, 3)
    product["bridge_score"] = round(bridge_score, 3)
    product["final_rank_score"] = round(max(final_rank, 0.0), 3)
    product["deal_type"] = _deal_type(product)
    product["tile_badge"] = _tile_badge(product)
    product["rec_reason"] = _generate_reason(product, emerging, emerging_clusters, vel_label, role)
    return product


def _build_rows(products, emerging, emerging_clusters, vel_label, price_dir):
    bridge = [p for p in products if p.get("role") == "bridge"]
    destination = [p for p in products if p.get("role") == "destination"]
    accessories = [
        p for p in products
        if set(map(str.lower, p.get("categories", []))) & (ACCESSORY_CATEGORIES | FOOTWEAR_CATEGORIES)
    ]
    best_value = sorted(products, key=lambda p: (_value_sort_key(p), -p.get("final_rank_score", 0)))

    rows = [
        {
            "row_type": "bridge",
            "title": "Best Bridge Picks",
            "ai_explanation": _row_explanation("bridge", emerging, emerging_clusters, vel_label, price_dir),
            "products": _dedupe_products(bridge)[:4],
            "see_more_query": "bridge"
        },
        {
            "row_type": "best_value",
            "title": "Best Value & Deals",
            "ai_explanation": _row_explanation("best_value", emerging, emerging_clusters, vel_label, price_dir),
            "products": _dedupe_products(best_value)[:4],
            "see_more_query": "best_value"
        },
        {
            "row_type": "destination",
            "title": "Destination Picks",
            "ai_explanation": _row_explanation("destination", emerging, emerging_clusters, vel_label, price_dir),
            "products": _dedupe_products(destination)[:4],
            "see_more_query": "destination"
        },
        {
            "row_type": "accessories",
            "title": "Accessories & Finishing Pieces",
            "ai_explanation": _row_explanation("accessories", emerging, emerging_clusters, vel_label, price_dir),
            "products": _dedupe_products(accessories)[:4],
            "see_more_query": "accessories"
        }
    ]

    return [r for r in rows if r["products"]][:4]


def _row_explanation(row_type, emerging, emerging_clusters, vel_label, price_dir):
    terms = _clean_terms(list(emerging.keys())[:2] + list(emerging_clusters.keys())[:2])
    joined = ", ".join(terms[:2]) if terms else "current trend signals"

    if row_type == "bridge":
        return f"Good next-step pieces for your move toward {joined} without changing too abruptly."
    if row_type == "best_value":
        return f"Lower-price and deal-focused options that still fit your shift toward {joined}."
    if row_type == "destination":
        return f"Stronger forward-looking pieces if you want to lean harder into {joined}."
    if row_type == "accessories":
        return f"Accessories and finishing pieces that support {joined} without rebuilding the whole wardrobe."
    return "Recommended products matched to your current trajectory."


def _value_bonus(product):
    dt = _deal_type(product)
    if dt == "clearance":
        return 1.0
    if dt == "sale":
        return 0.8
    price = product.get("price") or 0
    if 0 < price <= 60:
        return 0.7
    if 0 < price <= 100:
        return 0.55
    return 0.35


def _value_sort_key(product):
    dt = _deal_type(product)
    priority = {"clearance": 0, "sale": 1, "value": 2, "regular": 3}
    return (priority.get(dt, 3), product.get("price") or 999999)


def _deal_type(product):
    price = product.get("price") or 0
    orig = product.get("original_price") or 0
    if orig and price and orig > price:
        discount_pct = (orig - price) / orig
        if discount_pct >= 0.30:
            return "clearance"
        return "sale"
    if price and price <= 60:
        return "value"
    return "regular"


def _tile_badge(product):
    dt = _deal_type(product)
    if dt == "clearance":
        return "Clearance"
    if dt == "sale":
        return "Sale"
    if dt == "value":
        return "Best Value"
    role = product.get("role", "")
    return {"bridge": "Bridge", "destination": "Destination", "anchor": "Anchor"}.get(role, "")


def _dedupe_products(products):
    seen = set()
    out = []
    for p in products:
        if p["id"] in seen:
            continue
        seen.add(p["id"])
        out.append(p)
    return out


def _term_overlap_score(item_terms: set, target_terms: set) -> float:
    if not item_terms or not target_terms:
        return 0.0
    overlap = len(item_terms & set(map(str.lower, target_terms)))
    return min(1.0, overlap / max(min(len(target_terms), 4), 1))


def _assign_role(current_fit: float, future_fit: float, bridge_score: float, item_terms: set) -> str:
    if bridge_score >= 0.55 or "bridge" in item_terms:
        return "bridge"
    if future_fit >= current_fit + 0.15 or any("destination" in t for t in item_terms):
        return "destination"
    return "anchor"


def _velocity_role_bonus(vel_label: str, role: str) -> float:
    matrix = {
        "anchored": {"anchor": 0.95, "bridge": 0.85, "destination": 0.35},
        "steady": {"anchor": 0.80, "bridge": 0.95, "destination": 0.45},
        "flowing": {"anchor": 0.65, "bridge": 0.95, "destination": 0.70},
        "shifting": {"anchor": 0.45, "bridge": 0.80, "destination": 0.95},
        "transforming": {"anchor": 0.30, "bridge": 0.70, "destination": 1.00},
    }
    return matrix.get(vel_label, {}).get(role, 0.70)


def _price_alignment_bonus(price_dir: str, price):
    if not price:
        return 0.65
    if price_dir == "upgrading":
        if price >= 120:
            return 1.0
        if price >= 70:
            return 0.8
        return 0.5
    if price_dir == "economizing":
        if price <= 60:
            return 1.0
        if price <= 100:
            return 0.75
        return 0.45
    return 0.75


def _generate_reason(product, emerging, emerging_clusters, velocity, role):
    terms = set(str(t).lower() for t in (
        product.get("trajectory_tags", []) +
        product.get("style_tags", []) +
        product.get("categories", [])
    ))
    future_terms = set(k.lower() for k in list(emerging.keys()) + list(emerging_clusters.keys()))
    future_terms = {t for t in future_terms if t not in NON_FASHION_TERMS}
    matched = list(terms & future_terms)[:2]

    if role == "anchor":
        return "Close to your current taste and easy to add now."
    if role == "bridge":
        if matched:
            return f"Bridge pick aligned with your shift toward {', '.join(matched)}."
        return "Bridge pick that fits your current transition."
    if velocity in ("shifting", "transforming"):
        return "Stronger next-step piece if you want to lean into the new direction."
    return "Destination pick aligned with where your style is heading."


def _generate_summary(emerging, emerging_clusters, velocity, price_dir, match_count):
    terms = list(emerging.keys())[:2] + list(emerging_clusters.keys())[:2]
    terms = [t.replace("_", " ") for t in terms if t and t not in NON_FASHION_TERMS]
    if terms:
        head = f"Your taste is evolving toward {', '.join(terms[:3])}."
    else:
        head = "Your taste is showing a clearer next-step direction."

    vel_text = {
        "anchored": "We are prioritizing anchor and gentle bridge pieces.",
        "steady": "We are favoring realistic bridge products over sharp jumps.",
        "flowing": "You are in a balanced transition, so this is a mix of bridge and destination picks.",
        "shifting": "You are changing fast, so bolder forward-looking picks are included.",
        "transforming": "Your recent behavior supports a stronger move toward destination products."
    }.get(velocity, "")

    price_text = {
        "upgrading": "Your recent browsing also suggests a move toward higher-ticket items.",
        "economizing": "We are also keeping value sensitivity in mind.",
        "stable": "Price behavior looks relatively stable right now.",
        "unknown": ""
    }.get(price_dir, "")

    match_text = f" Pattern matched from {match_count} similar user journeys." if match_count else ""
    return " ".join(part for part in [head, vel_text, price_text]).strip() + match_text