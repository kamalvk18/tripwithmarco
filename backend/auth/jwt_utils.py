import os
from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError  # noqa: F401 — re-exported for callers

ALGORITHM = "HS256"
EXPIRES_DAYS = 7


def _secret() -> str:
    s = os.getenv("JWT_SECRET", "")
    if not s:
        raise RuntimeError("JWT_SECRET environment variable must be set before starting the server")
    return s


def create_token(user_id: int, email: str, name: str, picture: str = "") -> str:
    payload = {
        "sub":     str(user_id),
        "email":   email,
        "name":    name,
        "picture": picture,
        "exp":     datetime.now(timezone.utc) + timedelta(days=EXPIRES_DAYS),
    }
    return jwt.encode(payload, _secret(), algorithm=ALGORITHM)


def verify_token(token: str) -> dict:
    """Decode and verify JWT. Raises JWTError on failure."""
    return jwt.decode(token, _secret(), algorithms=[ALGORITHM])
