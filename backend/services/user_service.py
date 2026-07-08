from sqlalchemy.orm import Session

from models.user import User, UserPreference
from schemas.user import PlatformUrl


def get_profile(db: Session, user_id: int) -> dict | None:
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        return None

    pref = db.query(UserPreference).filter(UserPreference.user_id == user_id).first()
    if pref is None:
        preferences = {
            "fields": [],
            "keywords": [],
            "platform_urls": [],
        }
    else:
        preferences = {
            "fields": pref.fields,
            "keywords": pref.keywords,
            "platform_urls": pref.platform_urls,
        }

    return {
        "user_id": user.id,
        "username": user.username,
        "preferences": preferences,
    }


def update_preferences(
    db: Session,
    user_id: int,
    fields: list[str],
    keywords: list[str],
    platform_urls: list[PlatformUrl],
) -> dict:
    pref = db.query(UserPreference).filter(UserPreference.user_id == user_id).first()

    urls_data = [p.model_dump() for p in platform_urls]

    if pref is None:
        pref = UserPreference(
            user_id=user_id,
            fields=fields,
            keywords=keywords,
            platform_urls=urls_data,
        )
        db.add(pref)
    else:
        pref.fields = fields
        pref.keywords = keywords
        pref.platform_urls = urls_data

    db.commit()
    db.refresh(pref)

    return {
        "fields": pref.fields,
        "keywords": pref.keywords,
        "platform_urls": pref.platform_urls,
    }
