"""
UNLOOP — Source registry for seeded trend intelligence (Phase 1)
"""

SOURCE_REGISTRY = [
    {
        "source_id": "vogue_editorial",
        "name": "Vogue",
        "type": "editorial",
        "weight": 0.95,
    },
    {
        "source_id": "bazaar_editorial",
        "name": "Harper's Bazaar",
        "type": "editorial",
        "weight": 0.90,
    },
    {
        "source_id": "who_what_wear",
        "name": "Who What Wear",
        "type": "shopping_editorial",
        "weight": 0.85,
    },
    {
        "source_id": "highsnobiety",
        "name": "Highsnobiety",
        "type": "culture_style",
        "weight": 0.82,
    },
    {
        "source_id": "creator_signal",
        "name": "Creator Trend Signals",
        "type": "creator",
        "weight": 0.72,
    },
]