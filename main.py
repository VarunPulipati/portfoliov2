"""
UNLOOP — Backend API (v3 — SQLite + Google OAuth + Products)
"""

from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse, HTMLResponse
from datetime import datetime
import uuid
import os
import json

from services.database import (
    init_db, create_user, get_user, update_user, delete_user,
    insert_entries, get_entries, get_entry_count, get_domain_counts,
    get_insights, save_insights, get_all_products
)
from services.trajectory_service import analyze_trajectory
from services.path_matcher import find_path_matches
from services.product_recommender import get_recommendations_for_user, get_general_recommendations
from services.mock_products import seed_products
from services.auth import (
    create_jwt, verify_jwt, get_google_auth_url, get_extension_auth_url,
    GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_TOKEN_URL, 
    GOOGLE_USERINFO_URL, REDIRECT_URI, BACKEND_URL
)
from services.auth_db import init_auth_tables, create_or_link_google_user, get_user_by_google_id
from models.schemas import TrajectorySync, PathMatchRequest, UserUpdate, ProductClick

app = FastAPI(title="Unloop", version="0.3.0",
              description="Trajectory-based recommendation intelligence")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- Startup ----
@app.on_event("startup")
def startup():
    init_db()
    init_auth_tables()
    if not get_all_products(1):
        count = seed_products()
        print(f"[Unloop] Seeded {count} mock products")
    print("[Unloop] Backend ready — SQLite + Auth initialized")


# ---- Auth Helper ----
async def get_current_user(request: Request) -> dict:
    """Extract and verify JWT from Authorization header. Raises 401 if invalid."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Missing or invalid Authorization header")
    token = auth[7:]
    payload = verify_jwt(token)
    if not payload:
        raise HTTPException(401, "Invalid or expired token")
    user = get_user(payload.get("user_id", ""))
    if not user:
        raise HTTPException(401, "User not found")
    return {**user, "email": payload.get("email", ""), "picture": payload.get("picture", "")}


async def get_optional_user(request: Request) -> dict:
    """
    Try to extract user from JWT. Returns None if no auth header.
    Used for routes that work both anonymously and authenticated.
    """
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    token = auth[7:]
    payload = verify_jwt(token)
    if not payload:
        return None
    user = get_user(payload.get("user_id", ""))
    if not user:
        return None
    return {**user, "email": payload.get("email", ""), "picture": payload.get("picture", "")}


# ======== AUTH (Google OAuth) ========

@app.get("/auth/google")
def auth_google_redirect(source: str = "web", anonymous_id: str = ""):
    """
    Step 1: Redirect user to Google's OAuth consent screen.
    
    source: "web" (website login) or "extension" (Chrome extension login)
    anonymous_id: existing anonymous user_id to link after auth
    """
    state = json.dumps({"source": source, "anonymous_id": anonymous_id})
    # URL-safe base64 encode the state
    import base64
    state_encoded = base64.urlsafe_b64encode(state.encode()).decode()
    url = get_google_auth_url(state=state_encoded)
    return RedirectResponse(url)


@app.get("/auth/callback")
async def auth_callback(code: str = "", state: str = "", error: str = ""):
    """
    Step 2: Google redirects here after user consents.
    We exchange the code for tokens, get user info, create/link account, issue JWT.
    """
    if error:
        return HTMLResponse(f"<h2>Auth Error</h2><p>{error}</p><a href='/'>Go home</a>")
    
    if not code:
        return HTMLResponse("<h2>Missing auth code</h2><a href='/'>Go home</a>")
    
    # Decode state
    source = "web"
    anonymous_id = ""
    try:
        import base64
        state_json = base64.urlsafe_b64decode(state + "==").decode()
        state_data = json.loads(state_json)
        source = state_data.get("source", "web")
        anonymous_id = state_data.get("anonymous_id", "")
    except:
        pass
    
    # Exchange code for tokens
    try:
        import urllib.request
        import urllib.parse
        
        token_data = urllib.parse.urlencode({
            "code": code,
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uri": REDIRECT_URI,
            "grant_type": "authorization_code"
        }).encode()
        
        req = urllib.request.Request(GOOGLE_TOKEN_URL, data=token_data, 
                                      headers={"Content-Type": "application/x-www-form-urlencoded"})
        with urllib.request.urlopen(req) as resp:
            tokens = json.loads(resp.read())
        
        access_token = tokens.get("access_token", "")
        refresh_token = tokens.get("refresh_token", "")
        
        # Get user info from Google
        req2 = urllib.request.Request(GOOGLE_USERINFO_URL,
                                       headers={"Authorization": f"Bearer {access_token}"})
        with urllib.request.urlopen(req2) as resp:
            google_user = json.loads(resp.read())
        
    except Exception as e:
        return HTMLResponse(f"<h2>Token exchange failed</h2><p>{str(e)}</p>"
                          f"<p>Make sure GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET are set correctly.</p>"
                          f"<a href='/'>Go home</a>")
    
    # Create or link user
    user_data = create_or_link_google_user(
        google_id=google_user.get("id", ""),
        email=google_user.get("email", ""),
        name=google_user.get("name", ""),
        picture=google_user.get("picture", ""),
        access_token=access_token,
        refresh_token=refresh_token,
        existing_user_id=anonymous_id or None
    )
    
    # Issue JWT
    jwt_token = create_jwt({
        "user_id": user_data["user_id"],
        "email": user_data["email"],
        "name": user_data["name"],
        "picture": user_data.get("picture", ""),
        "google_id": user_data["google_id"]
    })
    
    # Redirect based on source
    if source == "extension":
        # Return a page that sends the token back to the extension via postMessage
        return HTMLResponse(f"""
        <!DOCTYPE html>
        <html>
        <head><title>Unloop — Login Successful</title>
        <style>body{{font-family:-apple-system,sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh;background:#0a0a0b;color:#e4e4e7;text-align:center}}
        .card{{background:#111;padding:40px;border-radius:16px;border:1px solid rgba(255,255,255,.08)}}
        h2{{color:#a78bfa;margin-bottom:8px}}p{{color:#71717a;font-size:14px}}</style>
        </head>
        <body>
        <div class="card">
            <h2>Logged in!</h2>
            <p>Welcome, {user_data['name']}. You can close this tab.</p>
            <p style="font-size:11px;margin-top:16px;color:#3f3f46">Token sent to extension.</p>
        </div>
        <script>
        // Send token to extension via multiple methods
        const token = "{jwt_token}";
        const userData = {json.dumps({"user_id": user_data["user_id"], "name": user_data["name"], "email": user_data["email"], "picture": user_data.get("picture", "")})};
        
        // Method 1: localStorage (extension popup can read this)
        try {{ localStorage.setItem('unloop_jwt', token); localStorage.setItem('unloop_user', JSON.stringify(userData)); }} catch(e) {{}}
        
        // Method 2: postMessage to opener
        if (window.opener) {{ window.opener.postMessage({{ type: 'UNLOOP_AUTH', token, user: userData }}, '*'); }}
        
        // Method 3: URL fragment for extension to read
        // The extension can poll for this via chrome.tabs
        document.title = 'UNLOOP_AUTH:' + token;
        
        // Auto-close after 3 seconds
        setTimeout(() => window.close(), 3000);
        </script>
        </body></html>
        """)
    else:
        # Web login — redirect to profile with token in URL fragment
        return RedirectResponse(f"/?auth_token={jwt_token}#profile")


@app.get("/auth/me")
async def get_me(user: dict = Depends(get_current_user)):
    """Get current authenticated user info."""
    return {
        "user_id": user.get("id") or user.get("user_id"),
        "name": user.get("name", ""),
        "email": user.get("email", ""),
        "picture": user.get("picture", ""),
        "tier": user.get("tier", "general"),
        "created_at": user.get("created_at", "")
    }


@app.get("/auth/verify")
async def verify_token(token: str):
    """Verify a JWT token and return user info. Used by extension."""
    payload = verify_jwt(token)
    if not payload:
        raise HTTPException(401, "Invalid or expired token")
    return {"valid": True, "user_id": payload.get("user_id"),
            "email": payload.get("email"), "name": payload.get("name")}


# ---- Health ----
@app.get("/api/health")
def health():
    return {"status": "alive", "version": "0.3.0", "db": "sqlite",
            "timestamp": datetime.utcnow().isoformat()}


# ======== USER ========

@app.post("/api/v1/users/register")
def register_user():
    """Anonymous registration — extension calls this on install."""
    uid = f"u_{uuid.uuid4().hex[:12]}"
    user = create_user(uid)
    return {"user_id": uid, "created_at": user["created_at"]}

@app.get("/api/v1/users/me")
async def get_my_profile(user: dict = Depends(get_current_user)):
    """Get authenticated user's own profile. Requires login."""
    user_id = user.get("id", user.get("user_id", ""))
    insights = get_insights(user_id)
    count = get_entry_count(user_id)
    return {
        **user,
        "items_tracked": count,
        "has_insights": insights is not None,
        "insights": insights
    }

@app.get("/api/v1/users/{user_id}")
def get_user_profile(user_id: str):
    """Get any user profile by ID. Public — used by extension before auth."""
    user = get_user(user_id)
    if not user:
        raise HTTPException(404, "User not found")
    insights = get_insights(user_id)
    count = get_entry_count(user_id)
    return {
        **user,
        "items_tracked": count,
        "has_insights": insights is not None,
        "insights": insights
    }

@app.patch("/api/v1/users/me")
async def update_my_profile(body: UserUpdate, user: dict = Depends(get_current_user)):
    """Update authenticated user's own profile. Requires login."""
    user_id = user.get("id", user.get("user_id", ""))
    updates = {k: v for k, v in body.dict().items() if v is not None}
    if updates:
        return update_user(user_id, **updates)
    return get_user(user_id)

@app.patch("/api/v1/users/{user_id}")
def update_user_profile(user_id: str, body: UserUpdate):
    """Update user by ID — used by extension before auth."""
    if not get_user(user_id):
        raise HTTPException(404, "User not found")
    updates = {k: v for k, v in body.dict().items() if v is not None}
    if updates:
        return update_user(user_id, **updates)
    return get_user(user_id)

@app.delete("/api/v1/users/me")
async def delete_my_account(user: dict = Depends(get_current_user)):
    """Delete authenticated user's account and all data. Requires login."""
    user_id = user.get("id", user.get("user_id", ""))
    delete_user(user_id)
    return {"status": "deleted", "user_id": user_id}


# ======== TRAJECTORY SYNC ========

@app.post("/api/v1/trajectory/sync")
def sync_trajectory(body: TrajectorySync):
    """Extension sends tracked entries here. Creates user if needed."""
    if not get_user(body.user_id):
        create_user(body.user_id)
    entries = [e.dict() for e in body.entries]
    inserted = insert_entries(body.user_id, entries)
    total = get_entry_count(body.user_id)
    return {
        "status": "synced",
        "entries_received": len(entries),
        "entries_inserted": inserted,
        "total_entries": total,
        "synced_at": datetime.utcnow().isoformat()
    }


# ======== ANALYSIS ========

@app.post("/api/v1/trajectory/{user_id}/analyze")
def run_analysis(user_id: str):
    """Run trajectory analysis and cache insights."""
    if not get_user(user_id):
        raise HTTPException(404, "User not found")
    result = analyze_trajectory(user_id)
    return result

@app.get("/api/v1/trajectory/{user_id}/insights")
def get_user_insights(user_id: str):
    insights = get_insights(user_id)
    if not insights:
        raise HTTPException(404, "No insights yet — sync data and run analysis first")
    return insights

@app.get("/api/v1/trajectory/{user_id}")
def get_user_trajectory(user_id: str):
    """Get user's trajectory data. Used for syncing across devices."""
    user = get_user(user_id)
    if not user:
        raise HTTPException(404, "User not found")
    entries = get_entries(user_id)
    return {
        "user_id": user_id,
        "entries": entries,
        "total_entries": len(entries)
    }


# ======== PATH MATCHING ========

@app.post("/api/v1/match")
def match_paths(body: PathMatchRequest):
    """Find evolution paths from other users."""
    matches = find_path_matches(
        current_features=body.current_features,
        velocity_score=body.velocity_score,
        num_matches=body.num_matches,
        lookahead_weeks=body.lookahead_weeks,
        exclude_user=body.user_id
    )
    return {"status": "matched" if matches else "no_matches",
            "count": len(matches), "matches": matches}


# ======== PRODUCTS ========

@app.get("/api/v1/products/recommendations/general")
def get_general_product_recommendations(limit: int = 16):
    """Get general trend-based recommendations when no personal data exists yet."""
    return get_general_recommendations(limit)

@app.get("/api/v1/products/recommendations/{user_id}")
def get_product_recommendations(user_id: str, limit: int = 12):
    """Get trajectory-aligned product recommendations."""
    if not get_user(user_id):
        raise HTTPException(404, "User not found")
    return get_recommendations_for_user(user_id, limit)


@app.get("/api/v1/products")
def list_products(limit: int = 50):
    """List all available products."""
    return {"products": get_all_products(limit)}

@app.post("/api/v1/products/click")
def track_product_click(body: ProductClick):
    """Track when user clicks a product recommendation."""
    # In production: update user_product_recs table, feed into ranking
    return {"status": "tracked", "user_id": body.user_id, "product_id": body.product_id}


# ======== TRENDS (Day 1 value) ========

@app.get("/api/v1/trends")
def get_trends():
    """General fashion trend intelligence — no user data needed."""
    return {
        "updated": datetime.utcnow().isoformat(),
        "trends": [
            {"title": "Quiet luxury gives way to 'loud softness'",
             "direction": "up", "category": "Aesthetic shift",
             "detail": "Texture and subtle pattern replacing plain minimalism."},
            {"title": "Gorpcore peaks, techwear inherits",
             "direction": "up", "category": "Streetwear evolution",
             "detail": "Technical fabrics moving from trail to office."},
            {"title": "Fast fashion dwell time dropping",
             "direction": "down", "category": "Consumer behavior",
             "detail": "Shoppers migrating toward fewer, considered purchases."},
            {"title": "Earth tones expanding beyond neutrals",
             "direction": "up", "category": "Color",
             "detail": "Terracotta, sage, rust displacing grey and black as defaults."},
            {"title": "Resale-first shopping is mainstream",
             "direction": "up", "category": "Sustainability",
             "detail": "34% of fashion purchases started on resale platforms in Q1 2026."},
            {"title": "Logo fatigue accelerating",
             "direction": "down", "category": "Branding",
             "detail": "Unbranded quality pieces gaining premium positioning."},
        ]
    }


# ======== SERVE WEBSITE ========

WEB_DIR = os.path.join(os.path.dirname(__file__), "..", "web")
if os.path.exists(WEB_DIR):
    app.mount("/css", StaticFiles(directory=os.path.join(WEB_DIR, "css")), name="css")
    app.mount("/js", StaticFiles(directory=os.path.join(WEB_DIR, "js")), name="js")
    if os.path.exists(os.path.join(WEB_DIR, "pages")):
        app.mount("/pages", StaticFiles(directory=os.path.join(WEB_DIR, "pages")), name="pages")
    
    @app.get("/")
    def serve_home():
        return FileResponse(os.path.join(WEB_DIR, "index.html"))


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
