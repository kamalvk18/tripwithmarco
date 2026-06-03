from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text

from backend.db.database import Base


class User(Base):
    __tablename__ = "users"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    google_id  = Column(String, unique=True, nullable=False, index=True)
    email      = Column(String, unique=True, nullable=False)
    name       = Column(String, default="")
    picture    = Column(String, default="")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Trip(Base):
    __tablename__ = "trips"

    trip_id     = Column(String, primary_key=True)
    user_id     = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    destination = Column(String, default="")
    start_date  = Column(String, default="", index=True)
    end_date    = Column(String, default="")
    dates       = Column(String, default="")
    saved_at    = Column(String, default="", index=True)
    budget      = Column(Float,  nullable=True)
    currency    = Column(String, nullable=True)
    data        = Column(Text,   nullable=False)


class UsageLog(Base):
    __tablename__ = "usage_logs"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    user_id     = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    endpoint    = Column(String,  nullable=False)
    method      = Column(String,  nullable=False)
    status_code = Column(Integer, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    created_at  = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
