"""
UNLOOP — Style Taxonomy / Relevance Layer (Phase 1 v2)
"""

from __future__ import annotations

import re
from typing import Dict, List, Set

CATEGORY_STOPWORDS = {
    "sale", "shop", "shopping", "product", "products", "item", "items", "collection",
    "collections", "new", "new arrivals", "arrival", "arrivals", "featured", "home",
    "homepage", "clothing", "apparel", "fashion", "wear", "browse", "catalog",
    "gift", "gifts", "women", "woman", "mens", "men", "kids", "boys", "girls",
    "all", "view all", "category", "categories", "store", "stores", "online",
    "official", "brand", "size", "sizes", "profile", "dashboard", "project",
    "recommendations", "show", "where", "going", "you", "your", "youre", "should",
    "apply", "application", "careers", "career", "job", "jobs", "scientist",
    "engineer", "developer", "resume", "interview", "salary", "hiring",
    "iphone", "apple", "cell phones", "cell phone", "phones", "phone", "unlocked",
    "128gb", "256gb", "512gb", "plus", "pro max", "best buy", "electronics",
}

NON_FASHION_DOMAIN_HINTS = {
    "chatgpt.com", "claude.ai", "railway.app", "railway.com", "127.0.0.1",
    "localhost", "workdayjobs.com", "myworkdayjobs.com", "taleo.net",
    "dice.com", "linkedin.com", "indeed.com", "glassdoor.com",
    "bestbuy.com", "apple.com",
}

FASHION_DOMAIN_HINTS = {
    "zara", "uniqlo", "cos", "arket", "everlane", "ssense", "farfetch",
    "matchesfashion", "net-a-porter", "mrporter", "asos", "hm", "h&m",
    "nordstrom", "mango", "aime", "stussy", "supreme", "nike", "adidas",
    "lululemon", "patagonia", "arcteryx", "carhartt",
}

CATEGORY_NORMALIZATION_MAP = {
    "t shirt": "tee",
    "t-shirt": "tee",
    "tee shirt": "tee",
    "graphic tee": "graphic tee",
    "graphic t shirt": "graphic tee",
    "shirt": "shirt",
    "button up": "button-up shirt",
    "button-down": "button-up shirt",
    "button down": "button-up shirt",
    "dress shirt": "button-up shirt",
    "oxford shirt": "button-up shirt",
    "overshirt": "overshirt",
    "polo": "polo",
    "tank": "tank top",
    "tank top": "tank top",
    "blouse": "blouse",
    "sweatshirt": "sweatshirt",
    "crewneck": "sweatshirt",
    "crew neck": "sweatshirt",
    "hoodie": "hoodie",
    "pullover hoodie": "hoodie",
    "zip hoodie": "hoodie",
    "sweater": "sweater",
    "cardigan": "cardigan",
    "knit": "knitwear",
    "knitwear": "knitwear",
    "jacket": "jacket",
    "jackets": "jacket",
    "coat": "coat",
    "blazer": "blazer",
    "blazers": "blazer",
    "trench": "trench coat",
    "trench coat": "trench coat",
    "parka": "parka",
    "puffer": "puffer jacket",
    "puffer jacket": "puffer jacket",
    "bomber": "bomber jacket",
    "windbreaker": "windbreaker",
    "fleece": "fleece",
    "anorak": "anorak",
    "pants": "pants",
    "trousers": "trousers",
    "slacks": "trousers",
    "jeans": "jeans",
    "denim": "jeans",
    "cargo": "cargo pants",
    "cargo pants": "cargo pants",
    "chinos": "chinos",
    "joggers": "joggers",
    "sweatpants": "sweatpants",
    "leggings": "leggings",
    "shorts": "shorts",
    "skirt": "skirt",
    "dress": "dress",
    "maxi dress": "maxi dress",
    "mini dress": "mini dress",
    "midi dress": "midi dress",
    "jumpsuit": "jumpsuit",
    "romper": "romper",
    "sneakers": "sneakers",
    "sneaker": "sneakers",
    "running shoes": "running shoes",
    "boots": "boots",
    "loafers": "loafers",
    "heels": "heels",
    "sandals": "sandals",
    "mules": "mules",
    "streetwear": "streetwear",
    "minimal": "minimalist",
    "minimalist": "minimalist",
    "basics": "basics",
    "basic": "basics",
    "classic": "classic",
    "timeless": "classic",
    "tailored": "tailored",
    "structured": "structured",
    "smart casual": "smart casual",
    "business casual": "smart casual",
    "quiet luxury": "quiet luxury",
    "gorpcore": "gorpcore",
    "techwear": "techwear",
    "technical": "technical",
    "athleisure": "athleisure",
    "outdoor": "outdoor",
    "workwear": "workwear",
    "scandinavian": "scandinavian",
    "earth tones": "earth tones",
    "neutral": "neutrals",
    "neutrals": "neutrals",
    "linen": "linen",
    "wool": "wool",
    "cashmere": "cashmere",
    "cotton": "cotton",
    "leather": "leather",
    "suede": "suede",
    "quality fabrics": "quality fabrics",
    "accessories": "accessories",
    "accessory": "accessories",
    "footwear": "footwear",
    "casual": "casual",
}

COLOR_FAMILY_MAP = {
    "black": "dark_neutral",
    "charcoal": "dark_neutral",
    "gray": "dark_neutral",
    "grey": "dark_neutral",
    "white": "light_neutral",
    "ivory": "light_neutral",
    "cream": "light_neutral",
    "oatmeal": "light_neutral",
    "beige": "earth_tone",
    "camel": "earth_tone",
    "tan": "earth_tone",
    "taupe": "earth_tone",
    "brown": "earth_tone",
    "olive": "earth_tone",
    "sage": "earth_tone",
    "khaki": "earth_tone",
    "rust": "earth_tone",
    "terracotta": "earth_tone",
    "navy": "cool_dark",
    "blue": "cool",
    "indigo": "cool",
    "teal": "cool",
    "mint": "cool",
    "green": "cool",
    "red": "warm",
    "burgundy": "warm",
    "maroon": "warm",
    "coral": "warm",
    "pink": "warm",
    "orange": "warm",
    "yellow": "warm",
    "mustard": "warm",
    "purple": "accent",
    "lavender": "accent",
    "peach": "warm",
    "rose": "warm",
    "slate": "cool_dark",
}

STYLE_KEYWORD_RULES = {
    "streetwear": {"hoodie", "graphic tee", "cargo pants", "sneakers", "streetwear", "casual"},
    "minimalist": {"minimalist", "basics", "neutrals", "tee", "shirt", "trousers", "blazer", "structured"},
    "smart_casual": {"smart casual", "button-up shirt", "trousers", "blazer", "loafers", "polo"},
    "tailored": {"tailored", "structured", "blazer", "trousers", "coat"},
    "techwear": {"techwear", "technical", "gorpcore", "outdoor", "parka", "anorak", "windbreaker", "fleece"},
    "athleisure": {"athleisure", "joggers", "leggings", "running shoes", "hoodie", "sweatpants", "sneakers"},
    "earth_minimal": {"earth tones", "linen", "wool", "quality fabrics", "neutrals"},
    "quiet_luxury": {"quiet luxury", "tailored", "wool", "cashmere", "leather", "quality fabrics"},
}

BRAND_STYLE_HINTS = {
    "uniqlo": {"minimalist", "basics"},
    "cos": {"minimalist", "tailored"},
    "arket": {"minimalist", "classic"},
    "zara": {"smart_casual"},
    "h&m": {"trend"},
    "nike": {"athleisure"},
    "adidas": {"athleisure"},
    "lululemon": {"athleisure"},
    "patagonia": {"outdoor", "techwear"},
    "arcteryx": {"techwear", "outdoor"},
    "carhartt": {"workwear"},
    "aime leon dore": {"streetwear", "classic"},
    "everlane": {"minimalist", "basics"},
    "apc": {"minimalist"},
    "common projects": {"minimalist", "smart_casual"},
}

FASHION_TERMS = {
    *CATEGORY_NORMALIZATION_MAP.values(),
    "streetwear", "minimalist", "structured", "basics", "smart casual",
    "tailored", "quiet luxury", "techwear", "athleisure", "earth tones",
    "neutrals", "jacket", "coat", "blazer", "pants", "trousers", "jeans",
    "dress", "shirt", "tee", "sneakers", "boots", "loafers", "accessories",
    "footwear", "linen", "wool", "cashmere", "leather", "suede",
}

UUIDISH_RE = re.compile(r"\b[a-f0-9]{8,}\b", re.I)
NUM_HEAVY_RE = re.compile(r".*\d{2,}.*")


def _clean_text(text: str) -> str:
    text = (text or "").strip().lower()
    text = text.replace("&", " and ")
    text = re.sub(r"[_/]+", " ", text)
    text = re.sub(r"[-]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^a-z0-9\s]", "", text)
    return text.strip()


def _is_junk_token(token: str) -> bool:
    if not token:
        return True
    if len(token) < 3:
        return True
    if len(token) > 40:
        return True
    if UUIDISH_RE.search(token):
        return True
    if NUM_HEAVY_RE.match(token) and token not in {"90s"}:
        return True
    if token in CATEGORY_STOPWORDS:
        return True
    return False


def _maybe_phrase_map(token: str) -> str:
    if token in CATEGORY_NORMALIZATION_MAP:
        return CATEGORY_NORMALIZATION_MAP[token]
    for key, value in CATEGORY_NORMALIZATION_MAP.items():
        if key in token:
            return value
    if token.endswith("s") and token[:-1] in CATEGORY_NORMALIZATION_MAP:
        return CATEGORY_NORMALIZATION_MAP[token[:-1]]
    return token


def normalize_categories(
    raw_categories: List[str],
    page_heading: str = "",
    image_signals: List[str] | None = None,
    brand: str = ""
) -> Dict[str, any]:
    image_signals = image_signals or []
    candidates = list(raw_categories or [])

    if page_heading:
        candidates.extend(re.split(r"[\s,|]+", page_heading))
    candidates.extend(image_signals)

    raw_count = len([c for c in candidates if c and str(c).strip()])
    normalized: List[str] = []
    kept: Set[str] = set()

    for token in candidates:
        cleaned = _clean_text(str(token))
        if _is_junk_token(cleaned):
            continue
        mapped = _maybe_phrase_map(cleaned)
        if _is_junk_token(mapped):
            continue
        if mapped not in kept:
            kept.add(mapped)
            normalized.append(mapped)

    style_clusters = infer_style_clusters(
        normalized_categories=normalized,
        raw_colors=[],
        page_heading=page_heading,
        brand=brand
    )

    coverage = round(len(normalized) / raw_count, 3) if raw_count else 0.0

    return {
        "normalized_categories": normalized[:18],
        "style_clusters": style_clusters[:8],
        "raw_count": raw_count,
        "normalized_coverage": coverage,
    }


def normalize_colors(raw_colors: List[str]) -> Dict[str, List[str]]:
    color_tokens: List[str] = []
    families: Set[str] = set()

    for color in raw_colors or []:
        c = _clean_text(color)
        if not c:
            continue
        mapped = None
        for k in COLOR_FAMILY_MAP.keys():
            if k in c:
                mapped = k
                break
        if mapped:
            color_tokens.append(mapped)
            families.add(COLOR_FAMILY_MAP[mapped])

    unique_colors = list(dict.fromkeys(color_tokens))
    return {
        "normalized_colors": unique_colors[:10],
        "color_families": list(families)[:6],
    }


def infer_style_clusters(
    normalized_categories: List[str],
    raw_colors: List[str],
    page_heading: str = "",
    brand: str = ""
) -> List[str]:
    heading = _clean_text(page_heading)
    color_info = normalize_colors(raw_colors or [])
    family_tokens = set(color_info["color_families"])

    tokens = set(normalized_categories or [])
    tokens.update(heading.split())
    tokens.update(family_tokens)

    brand_key = _clean_text(brand)
    if brand_key in BRAND_STYLE_HINTS:
        tokens.update(BRAND_STYLE_HINTS[brand_key])

    clusters: List[str] = []

    for cluster, rule_tokens in STYLE_KEYWORD_RULES.items():
        if tokens.intersection(rule_tokens):
            clusters.append(cluster)

    if "earth_tone" in family_tokens and "minimalist" in tokens:
        clusters.append("earth_minimal")
    if "dark_neutral" in family_tokens and ("structured" in tokens or "tailored" in tokens):
        clusters.append("tailored")
    if "light_neutral" in family_tokens and "basics" in tokens:
        clusters.append("minimalist")

    return list(dict.fromkeys(clusters))


def detect_price_tier(avg_price: float | None) -> str:
    if avg_price is None:
        return "unknown"
    if avg_price < 35:
        return "budget"
    if avg_price < 90:
        return "mid"
    if avg_price < 220:
        return "premium"
    return "luxury"


def fashion_relevance_score(
    raw_categories: List[str],
    normalized_categories: List[str],
    style_clusters: List[str],
    brand: str = "",
    domain: str = "",
    page_heading: str = "",
    has_price: bool = False,
) -> float:
    score = 0.0
    domain_l = (domain or "").lower()
    brand_l = _clean_text(brand)
    heading_l = _clean_text(page_heading)

    if any(h in domain_l for h in FASHION_DOMAIN_HINTS):
        score += 0.30
    if any(h in domain_l for h in NON_FASHION_DOMAIN_HINTS):
        score -= 0.45

    if brand_l in BRAND_STYLE_HINTS:
        score += 0.20

    norm_hits = len([c for c in normalized_categories if c in FASHION_TERMS])
    score += min(norm_hits * 0.08, 0.35)

    style_hits = len(style_clusters)
    score += min(style_hits * 0.10, 0.25)

    if has_price:
        score += 0.08

    if any(t in heading_l for t in FASHION_TERMS):
        score += 0.15

    raw_joined = " ".join(_clean_text(c) for c in (raw_categories or []))
    if any(t in raw_joined for t in {"job", "career", "iphone", "phone", "resume", "interview"}):
        score -= 0.35

    return round(max(0.0, min(score, 1.0)), 3)


def is_fashion_relevant(
    raw_categories: List[str],
    normalized_categories: List[str],
    style_clusters: List[str],
    brand: str = "",
    domain: str = "",
    page_heading: str = "",
    has_price: bool = False,
    threshold: float = 0.35,
) -> bool:
    return fashion_relevance_score(
        raw_categories=raw_categories,
        normalized_categories=normalized_categories,
        style_clusters=style_clusters,
        brand=brand,
        domain=domain,
        page_heading=page_heading,
        has_price=has_price,
    ) >= threshold