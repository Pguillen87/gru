"""Pure authentication claim checks shared by the API and unit tests."""

from __future__ import annotations


class AuthenticationRejected(ValueError):
    pass


def bearer_token(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer ") or not authorization.removeprefix("Bearer ").strip():
        raise AuthenticationRejected("A valid identity is required.")
    return authorization.removeprefix("Bearer ").strip()


def app_check_token(value: str | None) -> str:
    if not value or not value.strip():
        raise AuthenticationRejected("A valid app proof is required.")
    return value.strip()


def valid_firebase_claims(claims: dict[str, object], project_id: str) -> bool:
    return (
        claims.get("aud") == project_id
        and claims.get("iss") == f"https://securetoken.google.com/{project_id}"
        and bool(claims.get("uid") or claims.get("sub"))
    )


def may_schedule_gpu(generation_enabled: bool, generation_authorized: bool) -> bool:
    """A second scheduler-side guard; the GPU function enforces the flag again."""
    return generation_enabled and generation_authorized
