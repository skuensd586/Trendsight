# 导入所有模型确保表注册
from models import Base, User, UserPreference, Event, EventTrendDaily, EventKeyword, EventPlatform, Conversation, Message
from dependencies import engine


def init_database():
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("Done.")


if __name__ == "__main__":
    init_database()
