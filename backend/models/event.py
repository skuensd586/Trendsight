from datetime import datetime

from sqlalchemy import Column, Integer, String, Float, DateTime, Date, Text, JSON, ForeignKey, SmallInteger, Index
from sqlalchemy.orm import relationship
from sqlalchemy.schema import UniqueConstraint

from models import Base


class Event(Base):
    __tablename__ = "events"

    event_id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(500), nullable=False)
    heat = Column(Float, default=0.0)
    report_count = Column(Integer, default=0)
    duplicate_count = Column(Integer, default=0)
    time_start = Column(DateTime, nullable=True)
    time_end = Column(DateTime, nullable=True)
    positive = Column(Float, default=0.0)
    neutral = Column(Float, default=0.0)
    negative = Column(Float, default=0.0)
    stage = Column(String(20), nullable=True)
    confidence = Column(Float, default=0.0)
    prob_latent = Column(Float, default=0.0)
    prob_growth = Column(Float, default=0.0)
    prob_peak = Column(Float, default=0.0)
    prob_decline = Column(Float, default=0.0)
    analysis = Column(Text, nullable=True)
    sources = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.now)
    updated_at = Column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)

    trend_daily = relationship("EventTrendDaily", back_populates="event", cascade="all, delete-orphan")
    keywords = relationship("EventKeyword", back_populates="event", cascade="all, delete-orphan")
    platforms = relationship("EventPlatform", back_populates="event", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_events_heat", "heat"),
        Index("idx_events_time_start", "time_start"),
        Index("idx_events_stage", "stage"),
    )


class EventTrendDaily(Base):
    __tablename__ = "event_trend_daily"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(Integer, ForeignKey("events.event_id"), nullable=False)
    date = Column(Date, nullable=False)
    count = Column(Integer, default=0)
    is_predicted = Column(SmallInteger, default=0)
    predict_heat = Column(Float, nullable=True)
    predict_count = Column(Integer, nullable=True)

    event = relationship("Event", back_populates="trend_daily")

    __table_args__ = (
        UniqueConstraint("event_id", "date", "is_predicted", name="uq_event_trend"),
        Index("idx_trend_event_date", "event_id", "date"),
    )


class EventKeyword(Base):
    __tablename__ = "event_keywords"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(Integer, ForeignKey("events.event_id"), nullable=False)
    word = Column(String(50), nullable=False)
    weight = Column(Float, default=0.0)
    rank = Column(Integer, default=0)

    event = relationship("Event", back_populates="keywords")

    __table_args__ = (
        UniqueConstraint("event_id", "word", name="uq_event_keyword"),
        Index("idx_keyword_event_rank", "event_id", "rank"),
    )


class EventPlatform(Base):
    __tablename__ = "event_platforms"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(Integer, ForeignKey("events.event_id"), nullable=False)
    platform_name = Column(String(50), nullable=False)
    ratio = Column(Float, default=0.0)
    rank = Column(Integer, default=0)

    event = relationship("Event", back_populates="platforms")

    __table_args__ = (
        UniqueConstraint("event_id", "platform_name", name="uq_event_platform"),
        Index("idx_platform_event_rank", "event_id", "rank"),
    )
