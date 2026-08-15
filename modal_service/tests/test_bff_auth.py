from __future__ import annotations

import jwt
import pytest

from modal_service.bff_auth import AUDIENCE, ISSUER, BffAuthenticationRejected, consume_jti, verify_bff_token


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
    assert identity.expires_at == NOW + 90


def test_jti_is_consumed_once_until_expiration():
    store = {}
    consume_jti(store, "jti-1", NOW + 90, now=lambda: NOW)
    with pytest.raises(BffAuthenticationRejected, match="replayed"):
        consume_jti(store, "jti-1", NOW + 90, now=lambda: NOW + 1)


def test_expired_jti_record_does_not_block_a_new_short_lived_token():
    store = {"bff-jti:jti-1": NOW - 1}
    consume_jti(store, "jti-1", NOW + 90, now=lambda: NOW)
    assert store["bff-jti:jti-1"] == NOW + 90


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
