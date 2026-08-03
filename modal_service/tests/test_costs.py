import pytest

from modal_service.costs import CostLimitExceeded, RateLimitExceeded, can_reserve, require_job_quota, require_reservation


def test_cost_reservation_respects_cap():
    assert can_reserve(4.8, 0.2, 5.0)
    with pytest.raises(CostLimitExceeded):
        require_reservation(4.9, 0.2, 5.0)


def test_user_job_quota_rejects_the_next_job():
    assert require_job_quota(1, 2) == 2
    with pytest.raises(RateLimitExceeded):
        require_job_quota(2, 2)
