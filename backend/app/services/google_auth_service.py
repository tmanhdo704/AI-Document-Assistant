from dataclasses import dataclass

from google.auth.exceptions import GoogleAuthError
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from app.core.config import get_settings
from app.core.exceptions import ApplicationError


@dataclass(frozen=True)
class GoogleProfile:
    sub: str
    email: str
    full_name: str | None


class GoogleAuthService:
    @staticmethod
    def verify_credential(credential: str) -> GoogleProfile:
        settings = get_settings()

        try:
            claims = id_token.verify_oauth2_token(
                credential,
                google_requests.Request(),
                settings.google_client_id,
            )
        except ValueError as error:
            raise ApplicationError(
                "INVALID_GOOGLE_CREDENTIAL",
                "Google credential is invalid or expired.",
                status_code=401,
            ) from error
        except GoogleAuthError as error:
            raise ApplicationError(
                "GOOGLE_AUTH_UNAVAILABLE",
                "Google authentication is temporarily unavailable.",
                status_code=503,
            ) from error

        sub = claims.get("sub")
        email = claims.get("email")
        email_verified = claims.get("email_verified")
        name = claims.get("name")

        if (
            not isinstance(sub, str)
            or not sub
            or not isinstance(email, str)
            or not email
            or email_verified is not True
        ):
            raise ApplicationError(
                "INVALID_GOOGLE_CREDENTIAL",
                "Google credential does not contain a verified email.",
                status_code=401,
            )

        full_name = (
            name.strip()
            if isinstance(name, str) and name.strip()
            else None
        )

        return GoogleProfile(
            sub=sub,
            email=email.lower(),
            full_name=full_name,
        )