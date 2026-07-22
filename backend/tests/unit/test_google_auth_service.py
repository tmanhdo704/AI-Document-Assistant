import pytest
from pytest import MonkeyPatch

from app.core.exceptions import ApplicationError
from app.services import google_auth_service
from app.services.google_auth_service import GoogleAuthService


def test_verify_google_credential_returns_normalized_profile(
    monkeypatch: MonkeyPatch,
) -> None:
    def verify_token(
        credential: str,
        request: object,
        audience: str,
    ) -> dict[str, object]:
        assert credential == "valid-credential"
        assert request is not None
        assert audience

        return {
            "sub": "google-user-123",
            "email": "User@Example.com",
            "email_verified": True,
            "name": "  Google User  ",
        }

    monkeypatch.setattr(
        google_auth_service.id_token,
        "verify_oauth2_token",
        verify_token,
    )

    profile = GoogleAuthService.verify_credential(
        "valid-credential",
    )

    assert profile.sub == "google-user-123"
    assert profile.email == "user@example.com"
    assert profile.full_name == "Google User"


def test_verify_google_credential_requires_verified_email(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        google_auth_service.id_token,
        "verify_oauth2_token",
        lambda *_: {
            "sub": "google-user-123",
            "email": "user@example.com",
            "email_verified": False,
        },
    )

    with pytest.raises(ApplicationError) as captured:
        GoogleAuthService.verify_credential("credential")

    assert captured.value.code == "INVALID_GOOGLE_CREDENTIAL"
    assert captured.value.status_code == 401


def test_verify_google_credential_rejects_invalid_token(
    monkeypatch: MonkeyPatch,
) -> None:
    def reject_token(*_: object) -> None:
        raise ValueError("invalid token")

    monkeypatch.setattr(
        google_auth_service.id_token,
        "verify_oauth2_token",
        reject_token,
    )

    with pytest.raises(ApplicationError) as captured:
        GoogleAuthService.verify_credential("invalid-credential")

    assert captured.value.code == "INVALID_GOOGLE_CREDENTIAL"
    assert captured.value.status_code == 401
