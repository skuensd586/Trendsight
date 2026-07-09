from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Index
from sqlalchemy.orm import relationship

from models import Base


class Conversation(Base):
    __tablename__ = "conversations"

    conversation_id = Column(String(64), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    # event_id 作为预留字段，后期 events 表就绪后可恢复 FK 约束
    event_id = Column(Integer, nullable=True)
    title = Column(String(200), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.now)

    user = relationship("User", backref="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_conv_user", "user_id"),
        Index("idx_conv_event", "event_id"),
    )


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(String(64), ForeignKey("conversations.conversation_id"), nullable=False)
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.now)

    conversation = relationship("Conversation", back_populates="messages")

    __table_args__ = (
        Index("idx_msg_conv_time", "conversation_id", "created_at"),
    )
