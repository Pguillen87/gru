"""Short-lived authentication contract for Puleiro BFF to Modal v2."""

from __future__ import annotations

from dataclasses import dataclass
import os
import re
import time
from typing import Callable, MutableMapping

import jwt


ISSUER = os.getenv("PULEIRO_BFF_JWT_ISSUER", "puleiro-bff")
AUDIENCE = os.getenv("PULEIRO_BFF_JWT_AUDIENCE", "gru-modal")
MAX_TOKEN_LIFETIME_SECONDS = min(int(os.getenv("PULEIRO_BFF_JWT_MAX_TTL_SECONDS", "120")), 120)
IDENTIFIER = re.compile(r"^[A-Za-z0-9:_-]{1,160}$")


class BffAuthenticationRejected(ValueError):
    code = "BFF_UNAUTHENTICATED"


@dataclass(frozen=True)
class BffIdentity:
    user_id: str
    attempt_id: str
    jti: str
    expires_at: int


def verify_bff_token(
    token: str,
    secret: str,
    *,
    now: Callable[[], int] = lambda: int(time.time()),
) -> BffIdentity:
    if not token or not secret:
        raise BffAuthenticationRejected("A valid BFF identity is required.")
    try:
        claims = jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            audience=AUDIENCE,
            issuer=ISSUER,
            options={
                "require": ["iss", "aud", "sub", "jti", "iat", "exp", "attempt_id"],
                "verify_exp": False,
                "verify_iat": False,
            },
        )
    except jwt.PyJWTError as error:
        raise BffAuthenticationRejected("A valid BFF identity is required.") from error
    issued_at = _integer_claim(claims, "iat")
    expires_at = _integer_claim(claims, "exp")
    current = now()
    if issued_at > current + 5 or expires_at <= current or expires_at - issued_at > MAX_TOKEN_LIFETIME_SECONDS:
        raise BffAuthenticationRejected("A valid BFF identity is required.")
    user_id = _identifier_claim(claims, "sub")
    attempt_id = _identifier_claim(claims, "attempt_id")
    jti = _identifier_claim(claims, "jti")
    return BffIdentity(user_id, attempt_id, jti, expires_at)


def consume_jti(
    store: MutableMapping[str, object],
    jti: str,
    expires_at: int,
    *,
    now: Callable[[], int] = lambda: int(time.time()),
) -> None:
    current = now()
    key = f"bff-jti:{jti}"
    recorded = int(store.get(key, 0))
    if recorded > current:
        raise BffAuthenticationRejected("A BFF token cannot be replayed.")
    store[key] = expires_at


def _integer_claim(claims: dict[str, object], name: str) -> int:
    value = claims.get(name)
    if isinstance(value, bool) or not isinstance(value, int):
        raise BffAuthenticationRejected("A valid BFF identity is required.")
    return value


def _identifier_claim(claims: dict[str, object], name: str) -> str:
    value = str(claims.get(name, ""))
    if not IDENTIFIER.fullmatch(value):
        raise BffAuthenticationRejected("A valid BFF identity is required.")
    return value
