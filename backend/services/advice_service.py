"""Generate event response advice using LLM.

Uses the existing ask_llm() wrapper from utils.llm_client.
LLM failures are caught gracefully, returning empty strings.
"""

from __future__ import annotations

import json
from typing import Any

from utils.llm_client import ask_llm

_SYSTEM_PROMPT = (
    "你是一个舆情分析助手，需要根据事件信息生成处置建议。\n"
    "请以JSON格式输出，包含以下三个字段：\n"
    '{\n'
    '  "risk_assessment": "风险评估",\n'
    '  "verification": "信息核验建议",\n'
    '  "response_strategy": "响应策略建议"\n'
    '}\n'
    '不要输出JSON代码块标记，只输出纯JSON。'
)


def _build_message(event, similar_events: list[dict]) -> str:
    """Build user message text with event context for the LLM."""
    parts: list[str] = []
    parts.append(f"事件标题：{event.title or '未知'}")

    if event.summary:
        parts.append(f"事件概要：{event.summary}")
    if event.location:
        parts.append(f"发生地点：{event.location}")
    if event.cause:
        parts.append(f"可能原因：{event.cause}")
    if event.stage:
        parts.append(f"生命周期阶段：{event.stage}")
    if event.risk_level:
        parts.append(f"风险等级：{event.risk_level}")

    # Sentiment from individual columns
    parts.append(
        f"情感分布：正面{event.positive or 0} / 中性{event.neutral or 0} / "
        f"负面{event.negative or 0}"
    )

    # Authenticity info
    if event.authenticity and isinstance(event.authenticity, dict):
        auth = event.authenticity
        score = auth.get("credibility_score")
        if score is not None:
            parts.append(f"信源可信度分数：{score}")
        factors = auth.get("factors")
        if factors:
            parts.append("可信度信号：" + "、".join(factors))

    # Similar events context
    if similar_events:
        parts.append("相似历史事件：")
        for se in similar_events[:3]:
            parts.append(
                f"  - {se.get('title', '')}（相似度：{se.get('similarity', '')}）"
            )

    return "\n".join(parts)


def generate_event_advice(
    event,
    similar_events: list[dict[str, Any]],
) -> dict[str, str]:
    """Generate event response advice using LLM.

    Args:
        event: Event model instance (with fields accessed via attributes).
        similar_events: List of similar events from similarity_service.

    Returns:
        Dict with keys: risk_assessment, verification, response_strategy.
        All values default to empty string on failure.
    """
    try:
        user_text = _build_message(event, similar_events)
        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_text},
        ]

        result = ask_llm(messages)
        parsed = json.loads(result)

        return {
            "risk_assessment": parsed.get("risk_assessment", "") or "",
            "verification": parsed.get("verification", "") or "",
            "response_strategy": parsed.get("response_strategy", "") or "",
        }
    except Exception:
        return {
            "risk_assessment": "",
            "verification": "",
            "response_strategy": "",
        }
