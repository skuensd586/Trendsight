"""Event analysis report persistence service.

Takes an Algo pipeline analysis report (dict) and persists the data
into the events table and its child tables (keywords, platforms, trend).
"""

from datetime import datetime

from sqlalchemy.orm import Session

from models.event import Event, EventKeyword, EventPlatform, EventTrendDaily


def save_event(
    db: Session,
    report: dict,
) -> Event:
    now = datetime.now()

    # Support both nested lifecycle dict and flat report fields
    lifecycle = report.get("lifecycle", {})

    # === Event 主表 ===
    event = Event(
        title=report.get("title", ""),
        heat=report.get("heat", 0.0),
        report_count=report.get("report_count", 0),
        duplicate_count=report.get("duplicate_count", 0),
        event_time=report.get("event_time"),
        risk_level=report.get("risk_level"),
        stage=lifecycle.get("stage") or report.get("stage"),
        confidence=lifecycle.get("confidence") or report.get("confidence", 0.0),
        analysis=lifecycle.get("analysis") or report.get("analysis"),
        sources=report.get("sources"),
        created_at=now,
        updated_at=now,
    )

    # Sentiment
    sentiment = report.get("sentiment", {})
    event.positive = sentiment.get("positive", 0.0)
    event.neutral = sentiment.get("neutral", 0.0)
    event.negative = sentiment.get("negative", 0.0)

    # Stage probability
    stage_prob = lifecycle.get("stage_probability") or report.get("stage_probability", {})
    event.prob_latent = stage_prob.get("latent", 0.0)
    event.prob_growth = stage_prob.get("growth", 0.0)
    event.prob_peak = stage_prob.get("peak", 0.0)
    event.prob_decline = stage_prob.get("decline", 0.0)

    # Time range
    time_range = report.get("time_range")
    if isinstance(time_range, (list, tuple)) and len(time_range) >= 2:
        event.time_start = time_range[0]
        event.time_end = time_range[1]

    db.add(event)
    db.flush()

    # === Keywords 子表 ===
    for rank, kw in enumerate(report.get("keywords", [])):
        word = kw.get("word", "") or kw.get("keyword", "")
        if word:
            db.add(EventKeyword(
                event_id=event.event_id,
                word=word,
                weight=kw.get("weight", 0.0),
                rank=rank,
            ))

    # === Platform distribution 子表 ===
    for rank, pf in enumerate(report.get("platform_distribution", [])):
        name = pf.get("platform_name", "") or pf.get("platform", "")
        if name:
            db.add(EventPlatform(
                event_id=event.event_id,
                platform_name=name,
                ratio=pf.get("ratio", 0.0),
                rank=rank,
            ))

    # === Trend 子表（实际数据） ===
    for day in report.get("trend", []):
        db.add(EventTrendDaily(
            event_id=event.event_id,
            date=day.get("date"),
            count=day.get("count", 0),
            is_predicted=0,
        ))

    # === Trend 子表（预测数据） ===
    for day in report.get("future_trend", []):
        db.add(EventTrendDaily(
            event_id=event.event_id,
            date=day.get("date"),
            count=day.get("predict_count", 0),
            is_predicted=1,
            predict_heat=day.get("predict_heat"),
            predict_count=day.get("predict_count"),
        ))

    db.commit()
    db.refresh(event)
    return event


def get_events(
    db: Session,
    page: int = 1,
    size: int = 20,
) -> dict:
    total = db.query(Event).count()
    query = db.query(Event).order_by(Event.heat.is_(None).asc(), Event.heat.desc())
    items = query.offset((page - 1) * size).limit(size).all()
    total_pages = max(1, (total + size - 1) // size) if total > 0 else 0

    return {
        "items": [
            {
                "event_id": e.event_id,
                "title": e.title,
                "heat": e.heat,
                "report_count": e.report_count,
                "risk_level": e.risk_level,
                "stage": e.stage,
                "event_time": e.event_time.isoformat() if e.event_time else None,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in items
        ],
        "pagination": {
            "page": page,
            "page_size": size,
            "total": total,
            "total_pages": total_pages,
        },
    }


def get_event_detail(
    db: Session,
    event_id: int,
) -> dict | None:
    event = db.query(Event).filter(Event.event_id == event_id).first()
    if event is None:
        return None

    keywords = (
        db.query(EventKeyword)
        .filter(EventKeyword.event_id == event_id)
        .order_by(EventKeyword.rank)
        .all()
    )
    platforms = (
        db.query(EventPlatform)
        .filter(EventPlatform.event_id == event_id)
        .order_by(EventPlatform.rank)
        .all()
    )
    trend = (
        db.query(EventTrendDaily)
        .filter(
            EventTrendDaily.event_id == event_id,
            EventTrendDaily.is_predicted == 0,
        )
        .order_by(EventTrendDaily.date)
        .all()
    )
    future_trend = (
        db.query(EventTrendDaily)
        .filter(
            EventTrendDaily.event_id == event_id,
            EventTrendDaily.is_predicted == 1,
        )
        .order_by(EventTrendDaily.date)
        .all()
    )

    return {
        "event_id": event.event_id,
        "title": event.title,
        "heat": event.heat,
        "report_count": event.report_count,
        "duplicate_count": event.duplicate_count,
        "risk_level": event.risk_level,
        "event_time": event.event_time.isoformat() if event.event_time else None,
        "stage": event.stage,
        "confidence": event.confidence,
        "analysis": event.analysis,
        "sentiment": {
            "positive": event.positive,
            "neutral": event.neutral,
            "negative": event.negative,
        },
        "stage_probability": {
            "latent": event.prob_latent,
            "growth": event.prob_growth,
            "peak": event.prob_peak,
            "decline": event.prob_decline,
        },
        "sources": event.sources,
        "time_start": event.time_start.isoformat() if event.time_start else None,
        "time_end": event.time_end.isoformat() if event.time_end else None,
        "created_at": event.created_at.isoformat() if event.created_at else None,
        "keywords": [
            {"word": kw.word, "weight": kw.weight}
            for kw in keywords
        ],
        "platform_distribution": [
            {"platform_name": pf.platform_name, "ratio": pf.ratio}
            for pf in platforms
        ],
        "trend": [
            {"date": t.date.isoformat() if t.date else None, "count": t.count}
            for t in trend
        ],
        "future_trend": [
            {
                "date": ft.date.isoformat() if ft.date else None,
                "predict_heat": ft.predict_heat,
                "predict_count": ft.predict_count,
            }
            for ft in future_trend
        ],
    }
