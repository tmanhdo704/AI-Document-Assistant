from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import ApplicationError
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.models.user import User
from app.repositories.auth_session_repository import AuthSessionRepository
from app.repositories.user_repository import UserRepository
from app.schemas.auth import (
    AuthResponse,
    GoogleLoginRequest,
    LoginRequest,
    RegisterRequest,
    UserResponse,
)
from app.services.google_auth_service import GoogleAuthService


@dataclass(frozen=True)
class AuthenticationResult:
    response: AuthResponse
    refresh_token: str


class AuthService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.user_repository = UserRepository(db)
        self.session_repository = AuthSessionRepository(db)

    def register(self, payload: RegisterRequest) -> AuthenticationResult:
        email = payload.email.lower()

        if self.user_repository.get_by_email(email) is not None:
            raise ApplicationError(
                "EMAIL_ALREADY_EXISTS",
                "Email is already in use.",
                status_code=409,
            )

        try:
            user = self.user_repository.create(
                email=email,
                password_hash=hash_password(payload.password),
                full_name=(
                    payload.full_name.strip()
                    if payload.full_name
                    else None
                ),
            )
            refresh_token = self._create_refresh_session(user)

            self.db.commit()
            self.db.refresh(user)
        except IntegrityError as error:
            self.db.rollback()

            raise ApplicationError(
                "EMAIL_ALREADY_EXISTS",
                "Email is already in use.",
                status_code=409,
            ) from error

        return AuthenticationResult(
            response=self._build_auth_response(user),
            refresh_token=refresh_token,
        )

    def login(self, payload: LoginRequest) -> AuthenticationResult:
        email = payload.email.lower()
        user = self.user_repository.get_by_email(email)

        if (
            user is None
            or user.password_hash is None
            or not verify_password(payload.password, user.password_hash)
        ):
            raise ApplicationError(
                "INVALID_CREDENTIALS",
                "Email or password is incorrect.",
                status_code=401,
            )

        refresh_token = self._create_refresh_session(user)
        self.db.commit()
        self.db.refresh(user)

        return AuthenticationResult(
            response=self._build_auth_response(user),
            refresh_token=refresh_token,
        )

    def google_login(
        self,
        payload: GoogleLoginRequest,
    ) -> AuthenticationResult:
        profile = GoogleAuthService.verify_credential(
            payload.credential,
        )

        try:
            user = self.user_repository.get_by_google_sub(
                profile.sub,
            )

            if user is None:
                user = self.user_repository.get_by_email(
                    profile.email,
                )

                if user is None:
                    user = self.user_repository.create_google(
                        email=profile.email,
                        google_sub=profile.sub,
                        full_name=profile.full_name,
                    )
                elif user.google_sub is None:
                    user = self.user_repository.link_google_identity(
                        user=user,
                        google_sub=profile.sub,
                        full_name=profile.full_name,
                    )
                elif user.google_sub != profile.sub:
                    raise ApplicationError(
                        "GOOGLE_ACCOUNT_CONFLICT",
                        "Email is linked to another Google account.",
                        status_code=409,
                    )

            refresh_token = self._create_refresh_session(user)
            self.db.commit()
            self.db.refresh(user)
        except IntegrityError as error:
            self.db.rollback()

            raise ApplicationError(
                "GOOGLE_ACCOUNT_CONFLICT",
                "Google account could not be linked.",
                status_code=409,
            ) from error

        return AuthenticationResult(
            response=self._build_auth_response(user),
            refresh_token=refresh_token,
        )

    def refresh(self, refresh_token: str) -> AuthenticationResult:
        now = datetime.now(UTC)
        auth_session = self.session_repository.get_active_by_token_hash(
            hash_refresh_token(refresh_token),
            now,
        )

        if auth_session is None:
            raise ApplicationError(
                "INVALID_REFRESH_TOKEN",
                "Refresh token is invalid or expired.",
                status_code=401,
            )

        user = self.user_repository.get_by_id(auth_session.user_id)

        if user is None:
            raise ApplicationError(
                "INVALID_REFRESH_TOKEN",
                "Refresh token is invalid or expired.",
                status_code=401,
            )

        self.session_repository.revoke(auth_session, now)
        new_refresh_token = self._create_refresh_session(user)
        self.db.commit()
        self.db.refresh(user)

        return AuthenticationResult(
            response=self._build_auth_response(user),
            refresh_token=new_refresh_token,
        )

    def logout(self, refresh_token: str | None) -> None:
        if refresh_token is None:
            return

        now = datetime.now(UTC)
        auth_session = self.session_repository.get_active_by_token_hash(
            hash_refresh_token(refresh_token),
            now,
        )

        if auth_session is not None:
            self.session_repository.revoke(auth_session, now)
            self.db.commit()

    @staticmethod
    def _build_auth_response(user: User) -> AuthResponse:
        return AuthResponse(
            access_token=create_access_token(str(user.id)),
            user=UserResponse.model_validate(user),
        )

    def _create_refresh_session(
        self,
        user: User,
    ) -> str:
        settings = get_settings()
        refresh_token = generate_refresh_token()

        self.session_repository.create(
            user_id=user.id,
            token_hash=hash_refresh_token(refresh_token),
            expires_at=datetime.now(UTC)
            + timedelta(
                days=settings.refresh_token_expire_days,
            ),
        )

        return refresh_token
