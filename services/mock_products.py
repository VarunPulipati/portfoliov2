"""
UNLOOP — Mock Product Seeder
Generates realistic fashion products tagged with trajectory signals.
Each product is tagged with what trajectory direction it aligns with.
"""

from services.database import insert_products
import uuid
from datetime import datetime


def seed_products():
    """Seed database with mock products across different trajectory directions."""
    products = []

    # ---- Streetwear (starting point for many trajectories) ----
    products.extend([
        _p(
            "Nike Dunk Low Retro", "Nike", 110, 110, "sneakers",
            ["black", "white"],
            ["streetwear", "sneakers", "casual"],
            ["streetwear-base"],
            "Classic low-top sneaker. Leather upper, rubber sole."
        ),
        _p(
            "Stussy Basic Logo Tee", "Stussy", 45, 45, "graphic tees",
            ["black", "white", "grey"],
            ["streetwear", "graphic", "casual"],
            ["streetwear-base"],
            "Heavyweight cotton tee with chest logo print."
        ),
        _p(
            "Nike Tech Fleece Joggers", "Nike", 115, 115, "joggers",
            ["black", "grey"],
            ["streetwear", "athletic", "casual"],
            ["streetwear-base"],
            "Tapered fleece joggers with zippered pockets."
        ),
        _p(
            "Supreme Box Logo Hoodie", "Supreme", 168, 168, "hoodies",
            ["red", "black", "navy"],
            ["streetwear", "hoodies", "hype"],
            ["streetwear-base"],
            "Heavyweight cross-grain hooded sweatshirt with box logo."
        ),
    ])

    # ---- Bridge: Streetwear → Minimalism (transition products) ----
    products.extend([
        _p(
            "Nike Sportswear Tech Pack Jacket", "Nike", 185, 185, "jackets",
            ["black", "khaki"],
            ["streetwear", "structured", "technical"],
            ["streetwear-to-minimalist", "bridge"],
            "Woven jacket blending athletic heritage with clean structure."
        ),
        _p(
            "Zara Structured Overshirt", "Zara", 49.90, 79.90, "jackets",
            ["navy", "charcoal", "olive"],
            ["casual", "structured", "layering"],
            ["streetwear-to-minimalist", "bridge"],
            "Relaxed overshirt in brushed cotton. Clean lines, no logos."
        ),
        _p(
            "Uniqlo U Crew Neck T-Shirt", "Uniqlo", 19.90, 19.90, "basics",
            ["white", "black", "beige"],
            ["minimalist", "basics", "essentials"],
            ["streetwear-to-minimalist", "bridge"],
            "Heavy gauge cotton tee. Boxy fit, no branding. Christophe Lemaire design."
        ),
        _p(
            "COS Clean-Cut Chinos", "COS", 89, 89, "pants",
            ["black", "navy", "cream"],
            ["minimalist", "structured", "clean"],
            ["streetwear-to-minimalist", "bridge"],
            "Tapered chinos in organic cotton. Clean front, hidden pocket details."
        ),
    ])

    # ---- Minimalist Destination ----
    products.extend([
        _p(
            "Everlane The Organic Cotton Crew", "Everlane", 35, 35, "basics",
            ["white", "black", "heather grey"],
            ["minimalist", "basics", "quality fabrics"],
            ["minimalist-destination"],
            "100% organic cotton. Factory transparency. Essential crew neck."
        ),
        _p(
            "Arket Wool Overshirt", "Arket", 149, 149, "jackets",
            ["charcoal", "camel"],
            ["minimalist", "structured", "quality fabrics", "earth tones"],
            ["minimalist-destination"],
            "Brushed wool blend. Scandinavian design ethos. Understated luxury."
        ),
        _p(
            "COS Leather Chelsea Boots", "COS", 225, 225, "footwear",
            ["black", "brown"],
            ["minimalist", "structured", "quality fabrics"],
            ["minimalist-destination"],
            "Smooth leather with elastic side panels. Clean silhouette."
        ),
        _p(
            "A.P.C. Petit New Standard Jeans", "A.P.C.", 235, 235, "denim",
            ["indigo", "black"],
            ["minimalist", "quality fabrics", "denim"],
            ["minimalist-destination"],
            "Japanese selvedge denim. Slim straight fit. Raw, unwashed."
        ),
        _p(
            "Everlane The Italian Leather Tote", "Everlane", 125, 175, "accessories",
            ["black", "cognac"],
            ["minimalist", "quality fabrics", "accessories"],
            ["minimalist-destination"],
            "Full-grain Italian leather. Unlined. Minimal hardware."
        ),
        _p(
            "Norse Projects Aros Regular Light Stretch", "Norse Projects", 160, 160, "pants",
            ["beige", "navy"],
            ["minimalist", "structured", "scandinavian"],
            ["minimalist-destination"],
            "Light stretch cotton. Clean Scandinavian fit."
        ),
        _p(
            "Ray-Ban Wayfarer Classic", "Ray-Ban", 129, 179, "accessories",
            ["black"],
            ["minimalist", "accessories", "classic"],
            ["minimalist-destination"],
            "Timeless acetate sunglasses with a clean everyday profile."
        ),
        _p(
            "Daniel Wellington Classic Watch", "Daniel Wellington", 99, 149, "accessories",
            ["black", "brown"],
            ["minimalist", "accessories", "classic"],
            ["minimalist-destination"],
            "Simple dial and slim case for understated daily wear."
        ),
    ])

    # ---- Smart Casual Direction ----
    products.extend([
        _p(
            "J.Crew Garment-Dyed Oxford Shirt", "J.Crew", 59.50, 98, "shirts",
            ["white", "blue", "pink"],
            ["smart casual", "classic", "shirts"],
            ["smart-casual-destination"],
            "Broken-in oxford cloth. Button-down collar. Garment dyed for softness."
        ),
        _p(
            "Bonobos Stretch Chinos", "Bonobos", 99, 99, "pants",
            ["khaki", "navy", "grey"],
            ["smart casual", "structured", "pants"],
            ["smart-casual-destination"],
            "Athletic fit with hidden flex. Perfect for office-to-dinner."
        ),
        _p(
            "Common Projects Original Achilles Low", "Common Projects", 425, 425, "sneakers",
            ["white"],
            ["smart casual", "minimalist", "premium sneakers"],
            ["smart-casual-destination", "minimalist-destination"],
            "Handmade in Italy. Gold serial number stamp. The elevated sneaker."
        ),
        _p(
            "Todd Snyder Unconstructed Blazer", "Todd Snyder", 298, 498, "blazers",
            ["navy", "charcoal"],
            ["smart casual", "structured", "blazers"],
            ["smart-casual-destination"],
            "Unlined, unstructured. Pairs with tees as easily as dress shirts."
        ),
        _p(
            "Polo Ralph Lauren Leather Belt", "Polo Ralph Lauren", 68, 88, "accessories",
            ["brown", "black"],
            ["smart casual", "accessories", "classic"],
            ["smart-casual-destination"],
            "Classic leather belt that sharpens up chinos and tailored trousers."
        ),
        _p(
            "Seiko 5 Automatic", "Seiko", 225, 275, "accessories",
            ["silver", "black"],
            ["smart casual", "accessories", "classic"],
            ["smart-casual-destination"],
            "Reliable everyday watch with enough polish for smart casual outfits."
        ),
    ])

    # ---- Techwear / Gorpcore Direction ----
    products.extend([
        _p(
            "Arc'teryx Atom LT Hoody", "Arc'teryx", 280, 280, "jackets",
            ["black", "grey"],
            ["techwear", "technical", "outdoor", "gorpcore"],
            ["techwear-destination"],
            "Coreloft synthetic insulation. DWR treated. Performance meets urban."
        ),
        _p(
            "Salomon XT-6 Advanced", "Salomon", 190, 190, "sneakers",
            ["black", "white", "olive"],
            ["techwear", "trail", "gorpcore", "sneakers"],
            ["techwear-destination"],
            "Trail running tech adapted for streets. Anti-debris mesh."
        ),
        _p(
            "Acronym J1A-GTKP Jacket", "Acronym", 1650, 1650, "jackets",
            ["black"],
            ["techwear", "technical", "modular", "avant-garde"],
            ["techwear-destination"],
            "Gore-Tex Pro shell. Gravity pocket system. The techwear grail."
        ),
        _p(
            "And Wander Pertex Wind Jacket", "And Wander", 320, 320, "jackets",
            ["khaki", "navy"],
            ["techwear", "outdoor", "gorpcore", "layering"],
            ["techwear-destination"],
            "Ultralight Pertex ripstop. Japanese outdoor design philosophy."
        ),
        _p(
            "Oakley Half Jacket 2.0 XL", "Oakley", 145, 175, "accessories",
            ["black"],
            ["techwear", "accessories", "performance"],
            ["techwear-destination"],
            "Sport-driven eyewear that fits technical and outdoor-leaning wardrobes."
        ),
        _p(
            "Patagonia Black Hole Sling", "Patagonia", 55, 69, "accessories",
            ["black", "olive"],
            ["techwear", "outdoor", "accessories"],
            ["techwear-destination"],
            "Compact technical sling bag for everyday carry and travel."
        ),
    ])

    # ---- Earth Tones / Quiet Luxury Trend ----
    products.extend([
        _p(
            "Auralee Super Milled Sweat", "Auralee", 280, 280, "sweatshirts",
            ["oatmeal", "brown"],
            ["quiet luxury", "earth tones", "quality fabrics"],
            ["earth-tones-trend"],
            "Japanese-milled cotton. Heavy drape. Tonal sophistication."
        ),
        _p(
            "Lemaire Twisted Shirt", "Lemaire", 490, 490, "shirts",
            ["cream", "sage"],
            ["quiet luxury", "earth tones", "structured"],
            ["earth-tones-trend"],
            "Asymmetric twist detail. Muted palette. Parisian minimalism."
        ),
        _p(
            "Studio Nicholson Korda Pants", "Studio Nicholson", 340, 340, "pants",
            ["taupe", "charcoal"],
            ["quiet luxury", "structured", "earth tones"],
            ["earth-tones-trend"],
            "Wide leg with sharp pleat. Japanese fabric, British cut."
        ),
        _p(
            "Cuyana Double Loop Bag", "Cuyana", 198, 248, "accessories",
            ["taupe", "camel"],
            ["quiet luxury", "earth tones", "accessories"],
            ["earth-tones-trend"],
            "Soft structured leather bag in muted tones for refined everyday styling."
        ),
        _p(
            "Mejuri Slim Signet Ring", "Mejuri", 78, 98, "accessories",
            ["gold"],
            ["quiet luxury", "accessories", "minimalist"],
            ["earth-tones-trend", "minimalist-destination"],
            "Understated jewelry that complements a softer, refined wardrobe."
        ),
    ])

    insert_products(products)
    return len(products)


def _p(title, brand, price, orig_price, main_cat, colors, style_tags, traj_tags, desc):
    return {
        "id": f"prod_{uuid.uuid4().hex[:10]}",
        "title": title,
        "brand": brand,
        "price": price,
        "original_price": orig_price,
        "image_url": f"https://placehold.co/400x500/18181b/a78bfa?text={brand.replace(' ', '+')}",
        "product_url": f"https://example.com/products/{title.lower().replace(' ', '-')}",
        "affiliate_url": f"https://unloop.ai/go/{uuid.uuid4().hex[:8]}",
        "categories": [main_cat],
        "colors": colors,
        "style_tags": style_tags,
        "trajectory_tags": traj_tags,
        "description": desc,
        "source": "mock",
        "created_at": datetime.utcnow().isoformat()
    }