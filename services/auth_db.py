"""
UNLOOP — Auth Database Layer
Stores Google OAuth user data and links to trajectory profiles.
"""

import sqlite3
import json
from datetime import datetime
from typing import Optional
from services.database import get_db, get_user, create_user, update_user


def init_auth_tables():
    """Create auth-specific tables."""
    conn = get_db()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS auth_accounts (
        google_id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        email TEXT NOT NULL,
        name TEXT DEFAULT '',
        picture TEXT DEFAULT '',
        access_token TEXT,
        refresh_token TEXT,
        created_at TEXT NOT NULL,
        last_login TEXT,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );
    CREATE INDEX IF NOT EXISTS idx_auth_user ON auth_accounts(user_id);
    CREATE INDEX IF NOT EXISTS idx_auth_email ON auth_accounts(email);
    """)
    conn.commit()
    conn.close()


def get_user_by_google_id(google_id: str) -> Optional[dict]:
    """Find existing user by Google account."""
    conn = get_db()
    row = conn.execute("SELECT * FROM auth_accounts WHERE google_id=?", (google_id,)).fetchone()
    conn.close()
    if not row:
        return None
    return dict(row)


def get_user_by_email(email: str) -> Optional[dict]:
    """Find existing user by email."""
    conn = get_db()
    row = conn.execute("SELECT * FROM auth_accounts WHERE email=?", (email,)).fetchone()
    conn.close()
    if not row:
        return None
    return dict(row)


def create_or_link_google_user(google_id: str, email: str, name: str, 
                                picture: str, access_token: str = "",
                                refresh_token: str = "",
                                existing_user_id: str = None) -> dict:
    """
    Create a new user from Google auth, or link to an existing anonymous profile.
    
    If existing_user_id is provided (from extension's anonymous profile),
    we link the Google account to that existing profile instead of creating new.
    """
    # Check if this Google account already exists
    existing = get_user_by_google_id(google_id)
    if existing:
        # Update last login and tokens
        conn = get_db()
        conn.execute("""
            UPDATE auth_accounts SET last_login=?, access_token=?, name=?, picture=?
            WHERE google_id=?
        """, (datetime.utcnow().isoformat(), access_token, name, picture, google_id))
        conn.commit()
        conn.close()
        # Update user name
        update_user(existing["user_id"], name=name)
        return {**existing, "name": name, "is_new": False}
    
    # Determine user_id
    if existing_user_id and get_user(existing_user_id):
        # Link to existing anonymous profile
        user_id = existing_user_id
        update_user(user_id, name=name)
    else:
        # Create new user profile
        user_id = f"g_{google_id[:12]}"
        create_user(user_id)
        update_user(user_id, name=name)
    
    # Create auth account link
    now = datetime.utcnow().isoformat()
    conn = get_db()
    conn.execute("""
        INSERT INTO auth_accounts
        (google_id, user_id, email, name, picture, access_token, refresh_token, 
         created_at, last_login)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (google_id, user_id, email, name, picture, access_token, 
          refresh_token, now, now))
    conn.commit()
    conn.close()
    
    return {
        "google_id": google_id,
        "user_id": user_id,
        "email": email,
        "name": name,
        "picture": picture,
        "created_at": now,
        "is_new": True
    }
