from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from dependencies import get_db, get_current_user
from schemas.user import (
    UserProfileResponse,
    UserProfileData,
    UserPreferences,
    UpdatePreferencesRequest,
    UpdatePreferencesResponse,
)
from services.user_service import get_profile, update_preferences

router = APIRouter()


@router.get("/api/user/profile", response_model=UserProfileResponse)
def profile(user_id: int = Depends(get_current_user), db: Session = Depends(get_db)):
    data = get_profile(db, user_id)
    if data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在",
        )

    return UserProfileResponse(
        data=UserProfileData(
            user_id=data["user_id"],
            username=data["username"],
            preferences=UserPreferences(**data["preferences"]),
        )
    )


@router.put("/api/user/preferences", response_model=UpdatePreferencesResponse)
def update_prefs(
    request: UpdatePreferencesRequest,
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    data = update_preferences(db, user_id, request.fields, request.keywords, request.platform_urls)
    return UpdatePreferencesResponse(
        data=UserPreferences(**data),
    )
