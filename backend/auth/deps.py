import os

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError

from backend.auth.jwt_utils import verify_token
from backend.db.database import SessionLocal
from backend.db.models import User

_bearer = HTTPBearer(auto_error=True)


def _is_admin_email(email: str) -> bool:
    admins = {e.strip().lower() for e in os.getenv("ADMIN_EMAILS", "").split(",") if e.strip()}
    return email.lower() in admins


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> dict:
    """FastAPI dependency — returns the authenticated user as a plain dict.

    Returns a plain dict (not ORM object) so it stays usable after the
    session closes.
    """
    try:
        payload = verify_token(credentials.credentials)
        user_id = int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    with SessionLocal() as session:
        user = session.get(User, user_id)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
            )
        return {
            "id":        user.id,
            "google_id": user.google_id,
            "email":     user.email,
            "name":      user.name,
            "picture":   user.picture,
            "is_admin":  _is_admin_email(user.email),
        }


def get_admin_user(current_user: dict = Depends(get_current_user)) -> dict:
    """FastAPI dependency — same as get_current_user but requires is_admin=True."""
    if not current_user.get("is_admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user
