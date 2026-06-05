import os
from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError  # noqa: F401 — re-exported for callers

_raw_secret = os.getenv("JWT_SECRET", "")
if not _raw_secret:
    raise RuntimeError("JWT_SECRET environment variable must be set before starting the server")
SECRET    = _raw_secret
ALGORITHM = "HS256"
EXPIRES_DAYS = 7


def create_token(user_id: int, email: str, name: str, picture: str = "") -> str:
    payload = {
        "sub":     str(user_id),
        "email":   email,
        "name":    name,
        "picture": picture,
        "exp":     datetime.now(timezone.utc) + timedelta(days=EXPIRES_DAYS),
    }
    return jwt.encode(payload, SECRET, algorithm=ALGORITHM)


def verify_token(token: str) -> dict:
    """Decode and verify JWT. Raises JWTError on failure."""
    return jwt.decode(token, SECRET, algorithms=[ALGORITHM])
