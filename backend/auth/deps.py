from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError

from backend.auth.jwt_utils import verify_token
from backend.db.database import SessionLocal
from backend.db.models import User

_bearer = HTTPBearer(auto_error=True)


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
        }
