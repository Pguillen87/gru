import pytest

from modal_service.security import AuthenticationRejected, app_check_token, bearer_token, may_schedule_gpu, valid_firebase_claims


def test_valid_firebase_identity_requires_audience_issuer_and_uid():
    valid = {
        "aud": "gru-mascote",
        "iss": "https://securetoken.google.com/gru-mascote",
        "uid": "uid-a",
    }
    assert valid_firebase_claims(valid, "gru-mascote")
    assert not valid_firebase_claims(valid | {"aud": "other"}, "gru-mascote")
    assert not valid_firebase_claims(valid | {"iss": "https://example.invalid"}, "gru-mascote")
    assert not valid_firebase_claims(valid | {"uid": ""}, "gru-mascote")


def test_gpu_scheduler_requires_both_kill_switch_and_authorization():
    assert not may_schedule_gpu(False, False)
    assert not may_schedule_gpu(False, True)
    assert not may_schedule_gpu(True, False)
    assert may_schedule_gpu(True, True)


def test_missing_auth_and_app_check_are_rejected_before_handlers():
    with pytest.raises(AuthenticationRejected):
        bearer_token(None)
    with pytest.raises(AuthenticationRejected):
        bearer_token("Bearer ")
    with pytest.raises(AuthenticationRejected):
        app_check_token(None)
    with pytest.raises(AuthenticationRejected):
        app_check_token(" ")
