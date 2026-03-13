"""Authentication - Token-based API/WebSocket authentication.

Provides:
- API key validation via header or query parameter
- WebSocket token validation
- Configurable via MADO_API_KEY environment variable
- Disabled by default for local development (when MADO_API_KEY is not set)
"""

import os
import secrets
from typing import Optional

from fastapi import HTTPException, Request, WebSocket

# API key from environment. When not set, authentication is disabled (local dev mode).
_API_KEY: Optional[str] = os.environ.get("MADO_API_KEY")


def is_auth_enabled() -> bool:
    """Check if authentication is enabled (MADO_API_KEY is set)."""
    return _API_KEY is not None and len(_API_KEY) > 0


def generate_api_key() -> str:
    """Generate a secure random API key."""
    return secrets.token_urlsafe(32)


def validate_api_key(key: str) -> bool:
    """Validate an API key against the configured key."""
    if not is_auth_enabled():
        return True
    return secrets.compare_digest(key, _API_KEY)


async def require_auth(request: Request) -> None:
    """FastAPI dependency: require valid API key in Authorization header.

    Accepts:
    - Authorization: Bearer <key>
    - X-API-Key: <key>
    - ?api_key=<key> query parameter

    Skips validation when MADO_API_KEY is not set (local dev mode).
    """
    if not is_auth_enabled():
        return

    # Try Authorization header
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        if validate_api_key(token):
            return

    # Try X-API-Key header
    api_key_header = request.headers.get("X-API-Key", "")
    if api_key_header and validate_api_key(api_key_header):
        return

    # Try query parameter
    api_key_param = request.query_params.get("api_key", "")
    if api_key_param and validate_api_key(api_key_param):
        return

    raise HTTPException(status_code=401, detail="Invalid or missing API key")


async def validate_ws_token(websocket: WebSocket) -> bool:
    """Validate WebSocket connection token.

    Accepts token via query parameter: ws://host/path?token=<key>

    Returns True if valid, False if invalid.
    Skips validation when MADO_API_KEY is not set.
    """
    if not is_auth_enabled():
        return True

    token = websocket.query_params.get("token", "")
    return validate_api_key(token)
