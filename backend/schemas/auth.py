from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginData(BaseModel):
    user_id: int
    username: str
    token: str


class LoginResponse(BaseModel):
    code: int = 200
    message: str = "success"
    data: LoginData | None = None
