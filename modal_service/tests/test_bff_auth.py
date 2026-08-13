from __future__ import annotations

import jwt
import pytest

from modal_service.bff_auth import AUDIENCE, ISSUER, BffAuthenticationRejected, verify_bff_token


SECRET = "test-secret-with-at-least-thirty-two-bytes"
NOW = 1_800_000_000


def token(**overrides):
    claims = {
        "iss": ISSUER,
        "aud": AUDIENCE,
        "sub": "firebase-uid-1",
        "jti": "jti-1",
        "iat": NOW,
        "exp": NOW + 90,
        "attempt_id": "attempt-1",
    }
    claims.update(overrides)
    return jwt.encode(claims, SECRET, algorithm="HS256")


def test_valid_short_lived_bff_token_yields_owner_and_attempt():
    identity = verify_bff_token(token(), SECRET, now=lambda: NOW + 1)
    assert identity.user_id == "firebase-uid-1"
    assert identity.attempt_id == "attempt-1"
    assert identity.jti == "jti-1"


@pytest.mark.parametrize(
    "claims",
    [
        {"iss": "other"},
        {"aud": "other"},
        {"sub": ""},
        {"exp": NOW - 1},
        {"exp": NOW + 121},
    ],
)
def test_invalid_or_expired_bff_token_is_rejected(claims):
    with pytest.raises(BffAuthenticationRejected):
        verify_bff_token(token(**claims), SECRET, now=lambda: NOW)


def test_missing_secret_is_rejected():
    with pytest.raises(BffAuthenticationRejected):
        verify_bff_token(token(), "", now=lambda: NOW)
