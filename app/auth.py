from __future__ import annotations

import hmac
import os

from fastapi import Header, HTTPException

# Comma-separated list, e.g. "key-for-terminus,key-for-laptop-testing"
_raw_keys = os.environ.get("API_KEYS", "")
VALID_API_KEYS = {k.strip() for k in _raw_keys.split(",") if k.strip()}


def _matches_any(candidate: str) -> bool:
    # Constant-time compare against each configured key to avoid timing attacks.
    return any(hmac.compare_digest(candidate, valid) for valid in VALID_API_KEYS)


async def require_api_key(x_api_key: str = Header(default="", alias="X-API-Key")) -> str:
    """
    FastAPI dependency that protects an endpoint with a static API key,
    passed via the `X-API-Key` header.

    Configure valid keys with the API_KEYS env var (comma-separated for
    multiple clients/devices, so you can revoke one without affecting others).
    """
    if not VALID_API_KEYS:
        # Fail closed: if no keys are configured, nothing gets through.
        # This stops the service from accidentally running wide open.
        raise HTTPException(status_code=503, detail="No API keys configured on the server")

    if not x_api_key or not _matches_any(x_api_key):
        raise HTTPException(status_code=401, detail="Missing or invalid API key")

    return x_api_key
