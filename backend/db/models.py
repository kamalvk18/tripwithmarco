from sqlalchemy import Column, Float, String, Text

from backend.db.database import Base


class Trip(Base):
    __tablename__ = "trips"

    trip_id     = Column(String, primary_key=True)
    destination = Column(String, default="")
    start_date  = Column(String, default="", index=True)
    end_date    = Column(String, default="")
    dates       = Column(String, default="")
    saved_at    = Column(String, default="", index=True)
    budget      = Column(Float,  nullable=True)
    currency    = Column(String, nullable=True)
    data        = Column(Text,   nullable=False)  # full trip JSON blob
