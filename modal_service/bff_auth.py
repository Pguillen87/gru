"""Short-lived authentication contract for Puleiro BFF to Modal v2."""

from __future__ import annotations

from dataclasses import dataclass
import re
import time
from typing import Callable

import jwt


ISSUER = "puleiro-bff"
AUDIENCE = "gru-modal"
MAX_TOKEN_LIFETIME_SECONDS = 120
IDENTIFIER = re.compile(r"^[A-Za-z0-9:_-]{1,160}$")


class BffAuthenticationRejected(ValueError):
    code = "BFF_UNAUTHENTICATED"


@dataclass(frozen=True)
class BffIdentity:
    user_id: str
    attempt_id: str
    jti: str


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
    return BffIdentity(user_id, attempt_id, jti)


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
