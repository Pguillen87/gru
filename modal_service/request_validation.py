"""Validation helpers shared by public Modal API endpoints."""

from __future__ import annotations

from modal_service.domain import DomainError

MAX_IDEMPOTENCY_KEY_LENGTH = 160


def validate_idempotency_key(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise DomainError("Idempotency key is required.")
    if len(normalized) > MAX_IDEMPOTENCY_KEY_LENGTH:
        raise DomainError("Idempotency key is invalid.")
    if not all(character.isascii() and (character.isalnum() or character in ":_-") for character in normalized):
        raise DomainError("Idempotency key is invalid.")
    return normalized
