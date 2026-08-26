import pytest

from modal_service.domain import DomainError
from modal_service.request_validation import validate_idempotency_key


def test_idempotency_key_is_trimmed_and_accepts_the_android_identifier_contract():
    assert validate_idempotency_key("  request:abc_123-xyz  ") == "request:abc_123-xyz"


@pytest.mark.parametrize("value", ["", " ", "contains space", "invalid/slash", "x" * 161])
def test_idempotency_key_rejects_unbounded_or_unsafe_values(value: str):
    with pytest.raises(DomainError, match="Idempotency key"):
        validate_idempotency_key(value)
