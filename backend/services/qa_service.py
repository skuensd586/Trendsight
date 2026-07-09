import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from models.chat import Conversation, Message
from utils.llm_client import ask_llm


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
    messages = [
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
