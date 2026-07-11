import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from models.chat import Conversation, Message
from models.event import Event
from utils.llm_client import ask_llm


def format_time(value) -> str:
    if not value:
        return "未提供"
    if hasattr(value, "isoformat"):
        return value.isoformat(sep=" ", timespec="minutes")
    return str(value)


def format_number(value) -> str:
    if value is None:
        return "未提供"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    return f"{number:g}"


def format_percent(value) -> str:
    if value is None:
        return "未提供"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if abs(number) <= 1:
        number *= 100
    return f"{number:.1f}%"


def normalize_sources(value) -> dict:
    if isinstance(value, dict):
        return value
    if isinstance(value, list):
        return {"source_names": [str(item) for item in value if item]}
    if isinstance(value, str):
        return {"source_names": [value]} if value else {}
    return {}


def build_event_context(db: Session, event_id: int | None) -> str:
    if event_id is None:
        return "【数据说明】本次请求未提供事件 ID，后端无法查询事件详情。"

    event = db.query(Event).filter(Event.event_id == event_id).first()
    if event is None:
        return f"【数据说明】后端事件库未查询到 event_id={event_id} 的事件详情。请基于用户问题谨慎回答，并说明缺少事件背景。"

    sources = normalize_sources(event.sources)
    keywords = sorted(event.keywords, key=lambda item: item.rank if item.rank is not None else 9999)
    platforms = sorted(event.platforms, key=lambda item: item.rank if item.rank is not None else 9999)
    trend = sorted(event.trend_daily, key=lambda item: item.date or datetime.min.date())
    path_nodes = sources.get("path_nodes") or []
    similar_events = sources.get("similar_events") or []
    source_names = sources.get("source_names") or []

    keyword_text = "、".join(f"{item.word}({format_number(item.weight)})" for item in keywords[:12]) or "未提供"
    platform_text = "、".join(f"{item.platform_name} {format_percent(item.ratio)}" for item in platforms[:8]) or "未提供"
    trend_text = "、".join(
        f"{item.date.isoformat() if item.date else '未知日期'}: {item.count}篇"
        + (f"/预测热度{format_number(item.predict_heat)}" if item.is_predicted and item.predict_heat is not None else "")
        for item in trend[-10:]
    ) or "未提供"

    lines = [
        "【数据说明】以下内容由后端事件库根据 event_id 查询得到，是本次问答的主要事实依据。",
        "【事件基础】",
        f"事件ID：{event.event_id}",
        f"标题：{event.title}",
        f"类别：{sources.get('category') or '未提供'}",
        f"地区：{sources.get('location') or '未提供'}",
        source_names and f"来源平台：{'、'.join(source_names[:8])}",
        f"开始时间：{format_time(event.time_start)}",
        f"结束时间：{format_time(event.time_end)}",
        sources.get("summary") and f"事件概述：{sources.get('summary')}",
        sources.get("cause") and f"直接起因：{sources.get('cause')}",
        sources.get("people") and f"涉事主体：{sources.get('people')}",
        event.analysis and f"算法分析摘要：{event.analysis}",
        "【风险与生命周期】",
        f"热度指数：{format_number(event.heat)}",
        f"累计报道量：{format_number(event.report_count)}",
        f"重复报道量：{format_number(event.duplicate_count)}",
        sources.get("duplicate_rate") and f"重复传播率：{sources.get('duplicate_rate')}",
        f"生命周期阶段：{event.stage or '未提供'}",
        f"阶段置信度：{format_percent(event.confidence)}",
        f"阶段概率：潜伏 {format_percent(event.prob_latent)} / 成长 {format_percent(event.prob_growth)} / 高潮 {format_percent(event.prob_peak)} / 衰退 {format_percent(event.prob_decline)}",
        "【舆情信号】",
        f"情绪分布：积极 {format_percent(event.positive)} / 中性 {format_percent(event.neutral)} / 消极 {format_percent(event.negative)}",
        f"关键词：{keyword_text}",
        f"平台分布：{platform_text}",
        f"趋势数据：{trend_text}",
        path_nodes and f"传播路径节点：{' -> '.join(path_nodes)}",
        similar_events and f"历史相似事件：{'；'.join(similar_events[:4])}",
        "【处置线索】",
        sources.get("advice") and f"当前处置建议：{sources.get('advice')}",
    ]
    return "\n".join(line for line in lines if line)


def build_system_prompt(event_context: str | None = None) -> str:
    context = event_context.strip() if event_context else "未提供当前事件资料。"
    return f"""
你是 Trendsight 舆情分析平台的智能问答助手，服务对象是舆情分析员、应急响应人员和传播研判人员。

你的任务：
1. 基于“当前事件资料”和对话历史回答用户问题。
2. 可以采用事件资料中的信息。
3. 回答要像分析报告里的研判结论，不要像通用聊天。

当前事件资料：
{context}

回答原则：
- 注意引用事件资料中的数据增加可靠性。
- 先把问题映射到当前事件资料，再给出研判。
- 不要把“当前事件”泛化成普通新闻；除非资料不足，否则不要只回答“我无法实时联网”。
- 如果资料不足以判断实时变化，要明确说“基于当前看板数据”，并指出还需要核对最新官方通报/预警/媒体报道。
- 不编造数据。
- 可以做合理推断，但要用“可能、倾向于、需要继续观察”等措辞标注不确定性。

回答结构：
- 简短直接回答用户问题。
- 用 2-4 个要点展开。
- 如果涉及处置，给出可执行建议，按优先级排列。
- 使用中文和 Markdown，不要输出表格，除非用户明确要求。
""".strip()


def ask_question(
    db: Session,
    user_id: int,
    event_id: int | None,
    question: str,
    conversation_id: str | None = None,
) -> dict:
    # Normalize: None, empty string, string "null" are all treated as new conversation
    if conversation_id and conversation_id.strip().lower() in ("null", ""):
        conversation_id = None
    # 1. 获取或创建对话
    if not conversation_id:
        conversation_id = uuid.uuid4().hex
        conv = Conversation(
            conversation_id=conversation_id,
            user_id=user_id,
            event_id=event_id,
            title=question[:100],
        )
        db.add(conv)
        db.flush()
    else:
        conv = db.query(Conversation).filter(
            Conversation.conversation_id == conversation_id
        ).first()
        if conv is None:
            raise ValueError("对话不存在")
        if conv.user_id != user_id:
            raise PermissionError("无权访问此对话")

    now = datetime.now()

    # 2. 保存用户消息
    user_msg = Message(
        conversation_id=conversation_id,
        role="user",
        content=question,
        created_at=now,
    )
    db.add(user_msg)
    db.flush()

    # 3. 查询历史消息
    history = db.query(Message).filter(
        Message.conversation_id == conversation_id
    ).order_by(Message.created_at).all()

    # 4. 组装 OpenAI 标准 messages
    event_context = build_event_context(db, event_id)
    messages = [{"role": "system", "content": build_system_prompt(event_context)}] + [
        {"role": msg.role, "content": msg.content}
        for msg in history
    ]

    # 5. 调用大模型
    answer = ask_llm(messages)

    # 6. 保存模型回复
    assistant_msg = Message(
        conversation_id=conversation_id,
        role="assistant",
        content=answer,
        created_at=datetime.now(),
    )
    db.add(assistant_msg)
    db.commit()

    return {
        "conversation_id": conversation_id,
        "answer": answer,
        "created_time": now.isoformat(sep=" ", timespec="seconds"),
    }


def get_history(
    db: Session,
    user_id: int,
    conversation_id: str,
) -> dict:
    conv = db.query(Conversation).filter(
        Conversation.conversation_id == conversation_id
    ).first()
    if conv is None:
        raise ValueError("对话不存在")
    if conv.user_id != user_id:
        raise PermissionError("无权访问此对话")

    rows = db.query(Message).filter(
        Message.conversation_id == conversation_id
    ).order_by(Message.created_at).all()

    messages = [
        {
            "role": msg.role,
            "content": msg.content,
            "created_time": msg.created_at.isoformat(sep=" ", timespec="seconds"),
        }
        for msg in rows
    ]

    return {
        "conversation_id": conversation_id,
        "messages": messages,
    }
