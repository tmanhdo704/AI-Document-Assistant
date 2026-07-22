from fastapi import APIRouter, Cookie, Depends, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.config import get_settings
from app.core.exceptions import ApplicationError
from app.models.user import User
from app.schemas.auth import (
    AuthResponse,
    GoogleLoginRequest,
    LoginRequest,
    RegisterRequest,
    UserResponse,
)
from app.services.auth_service import AuthService

router = APIRouter(
    prefix="/auth",
    tags=["authentication"],
)

REFRESH_COOKIE_NAME = "docally_refresh_token"
REFRESH_COOKIE_PATH = "/api/v1/auth"


def set_refresh_cookie(
    response: Response,
    refresh_token: str,
) -> None:
    settings = get_settings()

    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=refresh_token,
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
        httponly=True,
        secure=settings.environment == "production",
        samesite="lax",
        path=REFRESH_COOKIE_PATH,
    )


def clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        path=REFRESH_COOKIE_PATH,
    )


@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(
    payload: RegisterRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> AuthResponse:
    result = AuthService(db).register(payload)
    set_refresh_cookie(response, result.refresh_token)
    return result.response


@router.post(
    "/login",
    response_model=AuthResponse,
)
def login(
    payload: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> AuthResponse:
    result = AuthService(db).login(payload)
    set_refresh_cookie(response, result.refresh_token)
    return result.response


@router.post(
    "/google",
    response_model=AuthResponse,
)
def google_login(
    payload: GoogleLoginRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> AuthResponse:
    result = AuthService(db).google_login(payload)
    set_refresh_cookie(response, result.refresh_token)
    return result.response


@router.post(
    "/refresh",
    response_model=AuthResponse,
)
def refresh(
    response: Response,
    refresh_token: str | None = Cookie(
        default=None,
        alias=REFRESH_COOKIE_NAME,
    ),
    db: Session = Depends(get_db),
) -> AuthResponse:
    if refresh_token is None:
        raise ApplicationError(
            "INVALID_REFRESH_TOKEN",
            "Refresh token is missing.",
            status_code=401,
        )

    result = AuthService(db).refresh(refresh_token)
    set_refresh_cookie(response, result.refresh_token)
    return result.response


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
)
def logout(
    response: Response,
    refresh_token: str | None = Cookie(
        default=None,
        alias=REFRESH_COOKIE_NAME,
    ),
    db: Session = Depends(get_db),
) -> None:
    AuthService(db).logout(refresh_token)
    clear_refresh_cookie(response)


@router.get(
    "/me",
    response_model=UserResponse,
)
def get_me(
    current_user: User = Depends(get_current_user),
) -> User:
    return current_user
