"""
UNLOOP — Auth Configuration
Google OAuth + JWT token management.

SETUP INSTRUCTIONS:
1. Go to https://console.cloud.google.com/apis/credentials
2. Create OAuth 2.0 Client ID (type: Web application)
3. Add authorized redirect URI: http://localhost:8000/auth/callback
4. Copy Client ID and Client Secret below (or set as environment variables)
5. For Chrome extension: also add the extension's redirect URL

For production:
- Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET as environment variables
- Change BACKEND_URL to your production domain
- Add production redirect URIs in Google Console
"""

import os
import time
import hashlib
import hmac
import json
import base64
from typing import Optional
from datetime import datetime, timedelta

# ---- Google OAuth Config ----
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET")
BACKEND_URL = os.environ.get("BACKEND_URL", "https://unloopai-production.up.railway.app")
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"
REDIRECT_URI = f"{BACKEND_URL}/auth/callback"

# ---- JWT Config ----
JWT_SECRET = os.environ.get("JWT_SECRET", "unloop-dev-secret-change-in-production-" + str(hash("unloop")))
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 168  # 7 days


# ---- Simple JWT Implementation (no external deps) ----

def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode('utf-8')

def _b64decode(data: str) -> bytes:
    padding = 4 - len(data) % 4
    if padding != 4:
        data += '=' * padding
    return base64.urlsafe_b64decode(data)

def create_jwt(payload: dict) -> str:
    """Create a JWT token with HS256 signing."""
    header = {"alg": JWT_ALGORITHM, "typ": "JWT"}
    
    # Add expiry
    payload = {**payload, "exp": int(time.time()) + JWT_EXPIRY_HOURS * 3600,
               "iat": int(time.time())}
    
    header_b64 = _b64encode(json.dumps(header).encode())
    payload_b64 = _b64encode(json.dumps(payload).encode())
    
    signing_input = f"{header_b64}.{payload_b64}"
    signature = hmac.new(JWT_SECRET.encode(), signing_input.encode(), hashlib.sha256).digest()
    signature_b64 = _b64encode(signature)
    
    return f"{header_b64}.{payload_b64}.{signature_b64}"


def verify_jwt(token: str) -> Optional[dict]:
    """Verify and decode a JWT token. Returns payload or None."""
    try:
        parts = token.split('.')
        if len(parts) != 3:
            return None
        
        header_b64, payload_b64, signature_b64 = parts
        
        # Verify signature
        signing_input = f"{header_b64}.{payload_b64}"
        expected_sig = hmac.new(JWT_SECRET.encode(), signing_input.encode(), hashlib.sha256).digest()
        actual_sig = _b64decode(signature_b64)
        
        if not hmac.compare_digest(expected_sig, actual_sig):
            return None
        
        # Decode payload
        payload = json.loads(_b64decode(payload_b64))
        
        # Check expiry
        if payload.get("exp", 0) < time.time():
            return None
        
        return payload
    except Exception:
        return None


def get_google_auth_url(state: str = "") -> str:
    """Generate Google OAuth authorization URL."""
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "consent",
        "state": state
    }
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return f"{GOOGLE_AUTH_URL}?{query}"


def get_extension_auth_url(extension_id: str = "") -> str:
    """Generate auth URL that redirects back to extension."""
    # The state parameter tells our callback where to redirect after auth
    state = f"extension:{extension_id}"
    return get_google_auth_url(state=state)
