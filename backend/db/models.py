from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint

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

    trip_id      = Column(String, primary_key=True)
    user_id      = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    destination  = Column(String, default="")
    start_date   = Column(String, default="", index=True)
    end_date     = Column(String, default="")
    dates        = Column(String, default="")
    saved_at     = Column(String, default="", index=True)
    budget       = Column(Float,  nullable=True)
    currency     = Column(String, nullable=True)
    data         = Column(Text,   nullable=False)
    invite_token = Column(String, nullable=True, unique=True, index=True)


class TripMember(Base):
    """Tracks users who have joined a trip via an invite link (not the owner)."""
    __tablename__ = "trip_members"

    id        = Column(Integer, primary_key=True, autoincrement=True)
    trip_id   = Column(String, ForeignKey("trips.trip_id", ondelete="CASCADE"), nullable=False, index=True)
    user_id   = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    joined_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (UniqueConstraint("trip_id", "user_id", name="uq_trip_member"),)


class UsageLog(Base):
    __tablename__ = "usage_logs"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    user_id     = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    endpoint    = Column(String,  nullable=False)
    method      = Column(String,  nullable=False)
    status_code = Column(Integer, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    created_at  = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)


class ToolCallLog(Base):
    """One row per external tool call (SerpApi flights/hotels/places, OpenWeather)."""
    __tablename__ = "tool_call_logs"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    tool_name   = Column(String,  nullable=False, index=True)
    cache_hit   = Column(Boolean, nullable=False, default=False)
    success     = Column(Boolean, nullable=False, default=True)
    duration_ms = Column(Integer, nullable=True)
    created_at  = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)


class EvalLog(Base):
    """One row per evaluated itinerary generation (planning turns that produced an itinerary)."""
    __tablename__ = "eval_logs"

    id                   = Column(Integer, primary_key=True, autoincrement=True)
    workflow             = Column(String,  nullable=True, index=True)   # extract_only | incremental | full_plan
    days_expected        = Column(Integer, nullable=True)
    days_found           = Column(Integer, nullable=True)
    format_passed        = Column(Boolean, nullable=False, default=True)
    eval_passed          = Column(Boolean, nullable=True)               # LLM structural check; null if skipped/errored
    issues               = Column(Text,    nullable=True)               # JSON array — blocking + advisory
    judge_scores         = Column(Text,    nullable=True)               # JSON object; null unless judge was sampled
    truncated            = Column(Boolean, nullable=False, default=False)
    repair_ran           = Column(Boolean, nullable=False, default=False)
    repair_format_passed = Column(Boolean, nullable=True)               # null if repair didn't run
    created_at           = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)


class ClaudeUsageLog(Base):
    """One row per Claude API response (streaming or sync)."""
    __tablename__ = "claude_usage_logs"

    id                    = Column(Integer, primary_key=True, autoincrement=True)
    model                 = Column(String,  nullable=False, index=True)
    input_tokens          = Column(Integer, nullable=False, default=0)
    output_tokens         = Column(Integer, nullable=False, default=0)
    cache_read_tokens     = Column(Integer, nullable=False, default=0)
    cache_creation_tokens = Column(Integer, nullable=False, default=0)
    created_at            = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
