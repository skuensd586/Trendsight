from pydantic import BaseModel


class PlatformUrl(BaseModel):
    platform_name: str
    url: str


class UserPreferences(BaseModel):
    fields: list[str]
    keywords: list[str]
    platform_urls: list[PlatformUrl]


class UserProfileData(BaseModel):
    user_id: int
    username: str
    preferences: UserPreferences


class UserProfileResponse(BaseModel):
    code: int = 200
    message: str = "success"
    data: UserProfileData | None = None


class UpdatePreferencesRequest(BaseModel):
    fields: list[str]
    keywords: list[str]
    platform_urls: list[PlatformUrl]


class UpdatePreferencesResponse(BaseModel):
    code: int = 200
    message: str = "updated successfully"
    data: UserPreferences | None = None
