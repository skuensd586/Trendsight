from unittest.mock import patch

import pytest

from models.event import Event
from services.qa_service import ask_question


def test_missing_event_does_not_call_llm(db_session):
    with patch("services.qa_service.ask_llm") as mock_ask_llm:
        with pytest.raises(ValueError, match="事件不存在"):
            ask_question(
                db=db_session,
                user_id=1,
                event_id=999,
                question="为什么会爆发",
            )

    mock_ask_llm.assert_not_called()


def test_system_prompt_contains_event_context(db_session):
    event = Event(
        title="阿里巴巴7月10日起全员禁用Claude",
        heat=12.45,
        report_count=38,
        stage="decline",
        confidence=0.9,
        analysis="当前事件报道数量持续下降，公众关注度减弱，处于衰退期。",
    )
    db_session.add(event)
    db_session.flush()

    captured_messages = []

    def fake_ask_llm(messages):
        captured_messages.extend(messages)
        return "基于当前事件资料，事件关注度正在下降。"

    with patch("services.qa_service.ask_llm", side_effect=fake_ask_llm):
        result = ask_question(
            db=db_session,
            user_id=1,
            event_id=event.event_id,
            question="为什么会爆发",
        )

    assert result["answer"] == "基于当前事件资料，事件关注度正在下降。"
    assert captured_messages[0]["role"] == "system"
    assert "阿里巴巴7月10日起全员禁用Claude" in captured_messages[0]["content"]
    assert "当前事件报道数量持续下降" in captured_messages[0]["content"]
    assert captured_messages[1]["role"] == "user"
