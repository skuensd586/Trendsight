"""Event analysis report persistence service.

Takes an Algo pipeline analysis report (dict) and persists the data
into the events table and its child tables (keywords, platforms, trend).
"""

from datetime import datetime

from sqlalchemy import or_
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

    event.time_start = report.get('time_start')
    event.time_end = report.get('time_end')

    # Authenticity
    authenticity_val = report.get("authenticity")
    if authenticity_val:
        event.authenticity = authenticity_val
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
    for day in lifecycle.get('future_trend', []):
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
    sort: str = "heat",
    risk_level: str | None = None,
    q: str | None = None,
) -> dict:
    query = db.query(Event)

    # Filter: risk_level
    if risk_level:
        query = query.filter(Event.risk_level == risk_level)

    # Filter: q title or keyword search
    if q:
        keyword = f"%{q}%"
        query = query.filter(
            or_(
                Event.title.like(keyword),
                Event.keywords.any(EventKeyword.word.like(keyword)),
            )
        )
    total = query.count()
    # Sort
    if sort == 'time':
        query = query.order_by(Event.event_time.is_(None).asc(), Event.event_time.desc())
    elif sort == 'negative':
        query = query.order_by(Event.negative.is_(None).asc(), Event.negative.desc())
    else:
        query = query.order_by(Event.heat.is_(None).asc(), Event.heat.desc())
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
                "summary": e.summary,
                "location": e.location,
                "analysis": e.analysis,
                "positive": e.positive,
                "neutral": e.neutral,
                "negative": e.negative,
                "keywords": [
                    keyword.word
                    for keyword in sorted(
                        e.keywords,
                        key=lambda item: item.rank if item.rank is not None else 9999,
                    )[:8]
                ],
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


    # Duplicate rate
    rc = event.report_count or 0
    dc = event.duplicate_count or 0
    total_val = rc + dc
    duplicate_rate = round(dc / total_val, 3) if total_val > 0 else 0.0
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
        'authenticity': event.authenticity,
        'duplicate_rate': duplicate_rate,
        'summary': event.summary,
        'location': event.location,
        'cause': event.cause,
        'people': event.people,
        "time_start": event.time_start.isoformat() if event.time_start else None,
        "time_end": event.time_end.isoformat() if event.time_end else None,
        "created_at": event.created_at.isoformat() if event.created_at else None,
        "keywords": [
            {"word": kw.word, "weight": kw.weight, "rank": kw.rank}
            for kw in keywords
        ],
        "platform_distribution": [
            {"platform_name": pf.platform_name, "ratio": pf.ratio, "rank": pf.rank}
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
        "trend_daily": [
            {
                "date": t.date.isoformat() if t.date else None,
                "count": t.count,
                "is_predicted": t.is_predicted,
                "predict_heat": t.predict_heat,
                "predict_count": t.predict_count,
            }
            for t in trend + future_trend
        ],
    }
