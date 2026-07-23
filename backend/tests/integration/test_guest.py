from fastapi.testclient import TestClient

from app.api.v1.endpoints.guest import GUEST_COOKIE_NAME


def test_create_guest_session_sets_http_only_cookie(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/v1/guest/session",
        headers={
            "User-Agent": "Chrome on Windows",
            "Accept-Language": "vi-VN",
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body == {
        "question_count": 0,
        "question_limit": 3,
        "questions_remaining": 3,
    }

    assert "guest_token" not in body
    assert response.cookies.get(GUEST_COOKIE_NAME)

    set_cookie = response.headers["set-cookie"].lower()

    assert "httponly" in set_cookie
    assert "samesite=lax" in set_cookie
    assert "path=/api/v1" in set_cookie


def test_guest_usage_uses_cookie(
    client: TestClient,
) -> None:
    create_response = client.post(
        "/api/v1/guest/session",
    )

    assert create_response.status_code == 200

    usage_response = client.get(
        "/api/v1/guest/usage",
    )

    assert usage_response.status_code == 200
    assert usage_response.json()["questions_remaining"] == 3


def test_guest_usage_requires_cookie(
    client: TestClient,
) -> None:
    response = client.get(
        "/api/v1/guest/usage",
    )

    assert response.status_code == 401
    assert (
        response.json()["error"]["code"]
        == "INVALID_GUEST_SESSION"
    )


def test_deleted_cookie_receives_rotated_token(
    client: TestClient,
) -> None:
    headers = {
        "User-Agent": "Chrome on Windows",
        "Accept-Language": "vi-VN",
    }

    first_response = client.post(
        "/api/v1/guest/session",
        headers=headers,
    )
    first_token = first_response.cookies.get(
        GUEST_COOKIE_NAME,
    )

    assert first_token

    client.cookies.delete(
        GUEST_COOKIE_NAME,
    )

    restored_response = client.post(
        "/api/v1/guest/session",
        headers=headers,
    )
    restored_token = restored_response.cookies.get(
        GUEST_COOKIE_NAME,
    )

    assert restored_response.status_code == 200
    assert restored_token
    assert restored_token != first_token
    assert restored_response.json()["questions_remaining"] == 3


def test_invalid_guest_cookie_is_rejected(
    client: TestClient,
) -> None:
    client.cookies.set(
        GUEST_COOKIE_NAME,
        "invalid-guest-token",
        path="/api/v1",
    )

    response = client.get(
        "/api/v1/guest/usage",
    )

    assert response.status_code == 401
    assert (
        response.json()["error"]["code"]
        == "INVALID_GUEST_SESSION"
    )
