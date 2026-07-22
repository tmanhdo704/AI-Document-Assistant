from fastapi.testclient import TestClient
from pytest import MonkeyPatch

from app.services.google_auth_service import (
    GoogleAuthService,
    GoogleProfile,
)

REFRESH_COOKIE_NAME = "docally_refresh_token"


def mock_google_profile(
    monkeypatch: MonkeyPatch,
    *,
    sub: str,
    email: str,
    full_name: str | None,
) -> None:
    def verify_credential(_: str) -> GoogleProfile:
        return GoogleProfile(
            sub=sub,
            email=email,
            full_name=full_name,
        )

    monkeypatch.setattr(
        GoogleAuthService,
        "verify_credential",
        staticmethod(verify_credential),
    )


def test_register_login_and_get_me(client: TestClient) -> None:
    register_response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "user@example.com",
            "password": "strong-password",
            "full_name": "Test User",
        },
    )

    assert register_response.status_code == 201

    registered = register_response.json()

    assert registered["token_type"] == "bearer"
    assert registered["user"]["email"] == "user@example.com"
    assert registered["user"]["full_name"] == "Test User"
    assert "password_hash" not in registered["user"]
    assert register_response.cookies.get(REFRESH_COOKIE_NAME)

    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "user@example.com",
            "password": "strong-password",
        },
    )

    assert login_response.status_code == 200

    access_token = login_response.json()["access_token"]

    assert login_response.cookies.get(REFRESH_COOKIE_NAME)

    me_response = client.get(
        "/api/v1/auth/me",
        headers={
            "Authorization": f"Bearer {access_token}",
        },
    )

    assert me_response.status_code == 200
    assert me_response.json()["email"] == "user@example.com"


def test_duplicate_email_is_rejected(client: TestClient) -> None:
    payload = {
        "email": "user@example.com",
        "password": "strong-password",
    }

    first_response = client.post(
        "/api/v1/auth/register",
        json=payload,
    )

    second_response = client.post(
        "/api/v1/auth/register",
        json=payload,
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 409
    assert (
        second_response.json()["error"]["code"]
        == "EMAIL_ALREADY_EXISTS"
    )


def test_invalid_credentials_are_rejected(
    client: TestClient,
) -> None:
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "user@example.com",
            "password": "strong-password",
        },
    )

    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "user@example.com",
            "password": "wrong-password",
        },
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_me_requires_valid_access_token(
    client: TestClient,
) -> None:
    response = client.get("/api/v1/auth/me")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_refresh_rotates_refresh_token(
    client: TestClient,
) -> None:
    register_response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "user@example.com",
            "password": "strong-password",
        },
    )
    old_refresh_token = register_response.cookies.get(
        REFRESH_COOKIE_NAME,
    )

    response = client.post("/api/v1/auth/refresh")

    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"

    new_refresh_token = response.cookies.get(REFRESH_COOKIE_NAME)

    assert old_refresh_token
    assert new_refresh_token
    assert new_refresh_token != old_refresh_token


def test_logout_revokes_refresh_token(
    client: TestClient,
) -> None:
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "user@example.com",
            "password": "strong-password",
        },
    )

    logout_response = client.post("/api/v1/auth/logout")
    refresh_response = client.post("/api/v1/auth/refresh")

    assert logout_response.status_code == 204
    assert refresh_response.status_code == 401
    assert (
        refresh_response.json()["error"]["code"]
        == "INVALID_REFRESH_TOKEN"
    )


def test_google_login_creates_google_user(
    client: TestClient,
    monkeypatch: MonkeyPatch,
) -> None:
    mock_google_profile(
        monkeypatch,
        sub="google-user-123",
        email="google-user@example.com",
        full_name="Google User",
    )

    response = client.post(
        "/api/v1/auth/google",
        json={"credential": "valid-google-credential"},
    )

    assert response.status_code == 200

    body = response.json()

    assert body["token_type"] == "bearer"
    assert body["user"]["email"] == "google-user@example.com"
    assert body["user"]["full_name"] == "Google User"
    assert body["user"]["auth_provider"] == "GOOGLE"
    assert response.cookies.get(REFRESH_COOKIE_NAME)

    me_response = client.get(
        "/api/v1/auth/me",
        headers={
            "Authorization": f"Bearer {body['access_token']}",
        },
    )

    assert me_response.status_code == 200
    assert me_response.json()["id"] == body["user"]["id"]


def test_google_login_links_existing_local_user(
    client: TestClient,
    monkeypatch: MonkeyPatch,
) -> None:
    register_response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "linked@example.com",
            "password": "strong-password",
            "full_name": "Local Name",
        },
    )
    local_user = register_response.json()["user"]

    mock_google_profile(
        monkeypatch,
        sub="google-linked-123",
        email="linked@example.com",
        full_name="Google Name",
    )

    google_response = client.post(
        "/api/v1/auth/google",
        json={"credential": "valid-google-credential"},
    )
    google_user = google_response.json()["user"]

    assert google_response.status_code == 200
    assert google_user["id"] == local_user["id"]
    assert google_user["full_name"] == "Local Name"
    assert google_user["auth_provider"] == "LOCAL"

    mock_google_profile(
        monkeypatch,
        sub="google-linked-123",
        email="changed@example.com",
        full_name="Changed Google Name",
    )

    repeated_response = client.post(
        "/api/v1/auth/google",
        json={"credential": "another-valid-credential"},
    )

    assert repeated_response.status_code == 200
    assert repeated_response.json()["user"]["id"] == local_user["id"]
    assert repeated_response.json()["user"]["email"] == "linked@example.com"

    password_login_response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "linked@example.com",
            "password": "strong-password",
        },
    )

    assert password_login_response.status_code == 200
    assert password_login_response.json()["user"]["id"] == local_user["id"]
