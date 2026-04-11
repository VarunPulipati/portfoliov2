"""
UNLOOP — Database Layer (SQLite)
Handles: user storage, trajectory entries, insights cache, products
"""

import sqlite3
import json
import os
from datetime import datetime
from typing import Optional, List, Dict, Any

DB_PATH = os.environ.get("UNLOOP_DB_PATH", "unloop.db")

def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def init_db():
    conn = get_db()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        name TEXT DEFAULT '',
        interests TEXT DEFAULT '',
        goal TEXT DEFAULT 'Let algorithm decide',
        tier TEXT DEFAULT 'general',
        created_at TEXT NOT NULL,
        last_synced TEXT
    );

    CREATE TABLE IF NOT EXISTS trajectory_entries (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        url TEXT,
        domain TEXT,
        page_title TEXT DEFAULT '',
        interaction_type TEXT DEFAULT 'view',
        interaction_weight REAL DEFAULT 1.0,
        dwell_time_seconds REAL DEFAULT 0,
        scroll_depth REAL DEFAULT 0,
        is_high_signal INTEGER DEFAULT 0,
        extracted_features TEXT DEFAULT '{}',
        meta TEXT DEFAULT '{}',
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );
    CREATE INDEX IF NOT EXISTS idx_traj_user ON trajectory_entries(user_id);
    CREATE INDEX IF NOT EXISTS idx_traj_ts ON trajectory_entries(user_id, timestamp);

    CREATE TABLE IF NOT EXISTS insights_cache (
        user_id TEXT PRIMARY KEY,
        direction TEXT DEFAULT '{}',
        velocity TEXT DEFAULT '{}',
        phase_transitions TEXT DEFAULT '[]',
        feature_timeline TEXT DEFAULT '[]',
        weekly_activity TEXT DEFAULT '[]',
        top_domains TEXT DEFAULT '[]',
        interaction_totals TEXT DEFAULT '{}',
        total_tracked INTEGER DEFAULT 0,
        tracking_days INTEGER DEFAULT 0,
        generated_at TEXT,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS products (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        brand TEXT,
        price REAL,
        original_price REAL,
        image_url TEXT,
        product_url TEXT,
        affiliate_url TEXT,
        categories TEXT DEFAULT '[]',
        colors TEXT DEFAULT '[]',
        style_tags TEXT DEFAULT '[]',
        trajectory_tags TEXT DEFAULT '[]',
        description TEXT DEFAULT '',
        source TEXT DEFAULT 'mock',
        created_at TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_prod_cats ON products(categories);

    CREATE TABLE IF NOT EXISTS user_product_recs (
        user_id TEXT NOT NULL,
        product_id TEXT NOT NULL,
        score REAL DEFAULT 0,
        reason TEXT DEFAULT '',
        trajectory_match TEXT DEFAULT '',
        shown_at TEXT,
        clicked INTEGER DEFAULT 0,
        PRIMARY KEY (user_id, product_id),
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS journeys (
        id TEXT PRIMARY KEY,
        source_user_id TEXT,
        label TEXT,
        feature_timeline TEXT DEFAULT '[]',
        velocity TEXT DEFAULT '{}',
        duration_weeks INTEGER DEFAULT 0,
        follower_count INTEGER DEFAULT 0,
        completion_count INTEGER DEFAULT 0,
        created_at TEXT
    );

    CREATE TABLE IF NOT EXISTS user_journey_follows (
        user_id TEXT NOT NULL,
        journey_id TEXT NOT NULL,
        current_step INTEGER DEFAULT 0,
        followed_at TEXT,
        PRIMARY KEY (user_id, journey_id)
    );
    """)
    conn.commit()
    conn.close()


# ---- User CRUD ----

def create_user(user_id: str) -> dict:
    conn = get_db()
    now = datetime.utcnow().isoformat()
    conn.execute("INSERT OR IGNORE INTO users (id, created_at) VALUES (?, ?)", (user_id, now))
    conn.commit()
    user = dict(conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone())
    conn.close()
    return user

def get_user(user_id: str) -> Optional[dict]:
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def update_user(user_id: str, **kwargs) -> dict:
    conn = get_db()
    sets = ", ".join(f"{k}=?" for k in kwargs)
    vals = list(kwargs.values()) + [user_id]
    conn.execute(f"UPDATE users SET {sets} WHERE id=?", vals)
    conn.commit()
    user = dict(conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone())
    conn.close()
    return user

def delete_user(user_id: str):
    conn = get_db()
    conn.execute("DELETE FROM users WHERE id=?", (user_id,))
    conn.commit()
    conn.close()


# ---- Trajectory CRUD ----

def insert_entries(user_id: str, entries: List[dict]) -> int:
    conn = get_db()
    inserted = 0
    for e in entries:
        try:
            conn.execute("""
                INSERT OR IGNORE INTO trajectory_entries
                (id, user_id, timestamp, url, domain, page_title, interaction_type,
                 interaction_weight, dwell_time_seconds, scroll_depth, is_high_signal,
                 extracted_features, meta)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                e.get("id", f"e_{datetime.utcnow().timestamp()}"),
                user_id,
                e.get("timestamp", datetime.utcnow().isoformat()),
                e.get("url", ""),
                e.get("domain", ""),
                e.get("page_title", ""),
                e.get("interaction_type", "view"),
                e.get("interaction_weight", 1.0),
                e.get("dwell_time_seconds", 0),
                e.get("scroll_depth", 0),
                1 if e.get("is_high_signal") else 0,
                json.dumps(e.get("extracted_features", {})),
                json.dumps(e.get("meta", {}))
            ))
            inserted += 1
        except sqlite3.IntegrityError:
            pass
    conn.commit()
    # Update last_synced
    conn.execute("UPDATE users SET last_synced=? WHERE id=?",
                 (datetime.utcnow().isoformat(), user_id))
    conn.commit()
    conn.close()
    return inserted

def get_entries(user_id: str, limit: int = 15000) -> List[dict]:
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM trajectory_entries WHERE user_id=? ORDER BY timestamp DESC LIMIT ?",
        (user_id, limit)
    ).fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        d["extracted_features"] = json.loads(d["extracted_features"])
        d["meta"] = json.loads(d["meta"])
        d["is_high_signal"] = bool(d["is_high_signal"])
        result.append(d)
    result.reverse()  # chronological order
    return result

def get_entry_count(user_id: str) -> int:
    conn = get_db()
    count = conn.execute("SELECT COUNT(*) FROM trajectory_entries WHERE user_id=?", (user_id,)).fetchone()[0]
    conn.close()
    return count

def get_domain_counts(user_id: str) -> Dict[str, int]:
    conn = get_db()
    rows = conn.execute(
        "SELECT domain, COUNT(*) as cnt FROM trajectory_entries WHERE user_id=? GROUP BY domain ORDER BY cnt DESC",
        (user_id,)
    ).fetchall()
    conn.close()
    return {r["domain"]: r["cnt"] for r in rows}


# ---- Insights Cache ----

def save_insights(user_id: str, insights: dict):
    conn = get_db()
    conn.execute("""
        INSERT OR REPLACE INTO insights_cache
        (user_id, direction, velocity, phase_transitions, feature_timeline,
         weekly_activity, top_domains, interaction_totals, total_tracked,
         tracking_days, generated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        user_id,
        json.dumps(insights.get("direction", {})),
        json.dumps(insights.get("velocity", {})),
        json.dumps(insights.get("phase_transitions", [])),
        json.dumps(insights.get("feature_timeline", [])),
        json.dumps(insights.get("weekly_activity", [])),
        json.dumps(insights.get("top_domains", [])),
        json.dumps(insights.get("interaction_totals", {})),
        insights.get("total_tracked", 0),
        insights.get("tracking_days", 0),
        insights.get("generated_at", datetime.utcnow().isoformat())
    ))
    conn.commit()
    conn.close()

def get_insights(user_id: str) -> Optional[dict]:
    conn = get_db()
    row = conn.execute("SELECT * FROM insights_cache WHERE user_id=?", (user_id,)).fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    for key in ["direction", "velocity", "phase_transitions", "feature_timeline",
                "weekly_activity", "top_domains", "interaction_totals"]:
        d[key] = json.loads(d[key])
    return d


# ---- Products ----

def insert_products(products: List[dict]):
    conn = get_db()
    for p in products:
        conn.execute("""
            INSERT OR REPLACE INTO products
            (id, title, brand, price, original_price, image_url, product_url,
             affiliate_url, categories, colors, style_tags, trajectory_tags,
             description, source, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            p["id"], p["title"], p.get("brand", ""),
            p.get("price", 0), p.get("original_price", 0),
            p.get("image_url", ""), p.get("product_url", ""),
            p.get("affiliate_url", ""),
            json.dumps(p.get("categories", [])),
            json.dumps(p.get("colors", [])),
            json.dumps(p.get("style_tags", [])),
            json.dumps(p.get("trajectory_tags", [])),
            p.get("description", ""), p.get("source", "mock"),
            p.get("created_at", datetime.utcnow().isoformat())
        ))
    conn.commit()
    conn.close()

def get_products_by_tags(tags: List[str], limit: int = 20) -> List[dict]:
    conn = get_db()
    # Simple tag matching — check if any tag appears in trajectory_tags or categories
    rows = conn.execute("SELECT * FROM products").fetchall()
    conn.close()
    results = []
    tag_set = set(t.lower() for t in tags)
    for r in rows:
        d = dict(r)
        d["categories"] = json.loads(d["categories"])
        d["colors"] = json.loads(d["colors"])
        d["style_tags"] = json.loads(d["style_tags"])
        d["trajectory_tags"] = json.loads(d["trajectory_tags"])
        item_tags = set(t.lower() for t in d["trajectory_tags"] + d["categories"] + d["style_tags"])
        overlap = len(tag_set & item_tags)
        if overlap > 0:
            d["_match_score"] = overlap
            results.append(d)
    results.sort(key=lambda x: x["_match_score"], reverse=True)
    for r in results:
        del r["_match_score"]
    return results[:limit]

def get_all_products(limit: int = 50) -> List[dict]:
    conn = get_db()
    rows = conn.execute("SELECT * FROM products LIMIT ?", (limit,)).fetchall()
    conn.close()
    results = []
    for r in rows:
        d = dict(r)
        for key in ["categories", "colors", "style_tags", "trajectory_tags"]:
            d[key] = json.loads(d[key])
        results.append(d)
    return results


# ---- All User Trajectories (for path matching) ----

def get_all_user_timelines() -> Dict[str, List[dict]]:
    """Get feature timelines for all users (for cross-user matching)."""
    conn = get_db()
    rows = conn.execute("SELECT user_id, feature_timeline FROM insights_cache WHERE feature_timeline != '[]'").fetchall()
    conn.close()
    result = {}
    for r in rows:
        result[r["user_id"]] = json.loads(r["feature_timeline"])
    return result
