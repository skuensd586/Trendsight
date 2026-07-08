from models import Base
from models.user import User, UserPreference
from dependencies import engine


def init_database():
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("Done.")


if __name__ == "__main__":
    init_database()