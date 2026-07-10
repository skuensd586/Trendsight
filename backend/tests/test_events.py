from unittest.mock import patch
from models.event import Event, EventKeyword, EventPlatform, EventTrendDaily
from datetime import datetime, date
from services.event_service import save_event, get_events, get_event_detail

def _make_report(overrides=None):
    report = {
        "title": "测试事件",
        "heat": 85.5,
        "report_count": 100,
        "duplicate_count": 5,
        "time_range": [datetime(2026, 7, 8, 8, 0, 0), datetime(2026, 7, 9, 12, 0, 0)],
        "sentiment": {"positive": 50, "neutral": 30, "negative": 20},
        "keywords": [{"word": "测试", "weight": 0.95}, {"word": "舆情", "weight": 0.80}],
        "platform_distribution": [{"platform_name": "微博", "ratio": 45}, {"platform_name": "新闻", "ratio": 55}],
        "trend": [{"date": date(2026, 7, 8), "count": 50}, {"date": date(2026, 7, 9), "count": 100}],
        "stage": "growth",
        "confidence": 0.85,
        "stage_probability": {"latent": 0.1, "growth": 0.7, "peak": 0.15, "decline": 0.05},
        "analysis": "处于成长期",
        "future_trend": [{"date": date(2026, 7, 10), "predict_heat": 80, "predict_count": 120}],
        "sources": ["新华社"],
        "risk_level": "high",
        "event_time": datetime(2026, 7, 8, 10, 0, 0),
    }
    if overrides:
        report.update(overrides)
    return report


class TestSaveEvent:
    def test_creates_event_and_all_sub_tables(self, db_session):
        event = save_event(db_session, _make_report())
        assert event.event_id > 0
        assert event.title == "测试事件"
        assert event.heat == 85.5
        assert event.report_count == 100
        assert event.risk_level == "high"
        assert event.stage == "growth"
        kws = db_session.query(EventKeyword).filter_by(event_id=event.event_id).order_by(EventKeyword.rank).all()
        assert len(kws) == 2
        assert kws[0].word == "测试"

    def test_empty_uses_defaults(self, db_session):
        event = save_event(db_session, {"title": "min"})
        assert event.heat == 0.0
        assert event.report_count == 0

    def test_nested_lifecycle(self, db_session):
        r = _make_report()
        r["lifecycle"] = {"stage": "peak", "confidence": 0.9, "analysis": "x", "stage_probability": {"peak": 1, "latent": 0, "growth": 0, "decline": 0}}
        del r["stage"]; del r["confidence"]; del r["analysis"]
        e = save_event(db_session, r)
        assert e.stage == "peak"
        assert e.prob_peak == 1.0


class TestGetEvents:
    def test_empty(self, db_session):
        r = get_events(db_session)
        assert r["pagination"]["total"] == 0 and r["items"] == []

    def test_pagination(self, db_session):
        for i in range(5):
            db_session.add(Event(title="E" + str(i), heat=float(i)))
        db_session.commit()
        r1 = get_events(db_session, page=1, size=2)
        assert r1["pagination"]["total"] == 5 and len(r1["items"]) == 2
        assert r1["items"][0]["heat"] == 4.0


class TestGetEventDetail:
    def test_not_found(self, db_session):
        assert get_event_detail(db_session, 999) is None

    def test_full(self, db_session):
        e = save_event(db_session, _make_report())
        d = get_event_detail(db_session, e.event_id)
        assert d["sentiment"]["positive"] == 50
        assert len(d["keywords"]) == 2
        assert len(d["platform_distribution"]) == 2
        assert len(d["trend"]) == 2
        assert len(d["future_trend"]) == 1


class TestRouter:
    def test_list_empty(self, client):
        r = client.get("/api/events")
        assert r.status_code == 200
        assert r.json()["data"]["pagination"]["total"] == 0

    def test_detail_404(self, client):
        r = client.get("/api/events/999")
        assert r.status_code == 404

    @patch("routers.events.call_algo")
    def test_analyze(self, mc, client, db_session):
        mc.return_value = [_make_report()]
        r = client.post("/api/events/analyze", json={"documents": [{"doc_id": "t1"}], "comments": []})
        assert r.status_code == 200
        assert r.json()["data"]["count"] == 1

    @patch("routers.events.call_algo")
    def test_analyze_502(self, mc, client):
        mc.side_effect = RuntimeError("err")
        r = client.post("/api/events/analyze", json={"documents": []})
        assert r.status_code == 502