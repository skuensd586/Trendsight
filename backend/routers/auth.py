from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from dependencies import get_db
from schemas.auth import LoginRequest, LoginResponse, LoginData
from services.auth_service import authenticate_user
from utils.jwt_handler import encode_token

router = APIRouter()


@router.post("/api/auth/login", response_model=LoginResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    user = authenticate_user(db, request.username, request.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )

    token = encode_token(user.id, user.username)
    return LoginResponse(
        data=LoginData(
            user_id=user.id,
            username=user.username,
            token=token,
        )
    )
