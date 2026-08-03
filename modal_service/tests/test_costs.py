import pytest

from modal_service.costs import CostLimitExceeded, can_reserve, require_reservation


def test_cost_reservation_respects_cap():
    assert can_reserve(4.8, 0.2, 5.0)
    with pytest.raises(CostLimitExceeded):
        require_reservation(4.9, 0.2, 5.0)
