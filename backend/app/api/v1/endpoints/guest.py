from fastapi import APIRouter, Cookie, Depends, Request, Response
from sqlalchemy.orm import Session

from app.api.deps import GUEST_COOKIE_NAME, get_db
from app.core.config import get_settings
from app.core.exceptions import ApplicationError
from app.schemas.guest import GuestUsageResponse
from app.services.guest_service import GuestService

router = APIRouter(
    prefix="/guest",
    tags=["guest"],
)

GUEST_COOKIE_PATH = "/api/v1"


def set_guest_cookie(
    response: Response,
    guest_token: str,
) -> None:
    settings = get_settings()

    response.set_cookie(
        key=GUEST_COOKIE_NAME,
        value=guest_token,
        httponly=True,
        secure=settings.environment == "production",
        samesite="lax",
        path=GUEST_COOKIE_PATH,
    )


@router.post(
    "/session",
    response_model=GuestUsageResponse,
)
def create_or_restore_guest_session(
    request: Request,
    response: Response,
    guest_token: str | None = Cookie(
        default=None,
        alias=GUEST_COOKIE_NAME,
    ),
    db: Session = Depends(get_db),
) -> GuestUsageResponse:
    if request.client is None:
        raise ApplicationError(
            "CLIENT_IDENTITY_UNAVAILABLE",
            "Client identity could not be determined.",
            status_code=400,
        )

    result = GuestService(db).create_or_restore_session(
        guest_token=guest_token,
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent"),
        accept_language=request.headers.get("accept-language"),
    )

    set_guest_cookie(
        response,
        result.guest_token,
    )

    return result.response


@router.get(
    "/usage",
    response_model=GuestUsageResponse,
)
def get_guest_usage(
    guest_token: str | None = Cookie(
        default=None,
        alias=GUEST_COOKIE_NAME,
    ),
    db: Session = Depends(get_db),
) -> GuestUsageResponse:
    if guest_token is None:
        raise ApplicationError(
            "INVALID_GUEST_SESSION",
            "Guest session cookie is missing.",
            status_code=401,
        )

    return GuestService(db).get_usage(guest_token)
