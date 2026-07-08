from dependencies import SessionLocal
from models.user import User
from utils.password_handler import hash_password


def create_test_user():
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.username == "test").first()
        if existing:
            print(f"Test user already exists (id={existing.id}). Skipping.")
            return

        user = User(
            username="test",
            password_hash=hash_password("123456"),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        print(f"Test user created: id={user.id}, username={user.username}")
    finally:
        db.close()


if __name__ == "__main__":
    create_test_user()
