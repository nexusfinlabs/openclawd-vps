"""Bearer-token authentication dependency for FastAPI."""

import os
from fastapi import Header, HTTPException

EXPORTER_TOKEN = os.getenv("EXPORTER_TOKEN", "")


def require_token(authorization: str = Header(...)):
    """Validate Authorization: Bearer <token> header."""
    if not EXPORTER_TOKEN:
        raise HTTPException(status_code=500, detail="EXPORTER_TOKEN not configured")

    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or parts[1] != EXPORTER_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid or missing token")
