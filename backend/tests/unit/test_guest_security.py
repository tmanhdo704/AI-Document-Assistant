from app.core.security import (
    create_guest_identity_hash,
    generate_guest_token,
    hash_guest_token,
)


def test_generate_guest_token_returns_unique_tokens() -> None:
    first_token = generate_guest_token()
    second_token = generate_guest_token()

    assert first_token
    assert second_token
    assert first_token != second_token


def test_hash_guest_token_is_deterministic() -> None:
    token = "example-guest-token"

    first_hash = hash_guest_token(token)
    second_hash = hash_guest_token(token)

    assert first_hash == second_hash
    assert first_hash != token
    assert len(first_hash) == 64


def test_guest_identity_hash_is_stable_after_normalization() -> None:
    first_hash = create_guest_identity_hash(
        ip_address=" 192.168.1.20 ",
        user_agent=" Chrome on Windows ",
        accept_language=" vi-VN ",
    )

    second_hash = create_guest_identity_hash(
        ip_address="192.168.1.20",
        user_agent="chrome on windows",
        accept_language="VI-vn",
    )

    assert first_hash == second_hash


def test_guest_identity_hash_changes_for_different_client() -> None:
    first_hash = create_guest_identity_hash(
        ip_address="192.168.1.20",
        user_agent="Chrome on Windows",
        accept_language="vi-VN",
    )

    second_hash = create_guest_identity_hash(
        ip_address="192.168.1.21",
        user_agent="Chrome on Windows",
        accept_language="vi-VN",
    )

    assert first_hash != second_hash