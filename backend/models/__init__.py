from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


# 导入所有模型，确保 Base.metadata 注册所有表
from models.user import User, UserPreference
from models.event import Event, EventTrendDaily, EventKeyword, EventPlatform
from models.chat import Conversation, Message
