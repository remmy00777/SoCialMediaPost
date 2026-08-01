import pytest
from app.services.costs import CostLedger


def test_cost_ledger_tracks_and_blocks_hard_limit():
    ledger = CostLedger(daily_limit=5, monthly_limit=50, hard_limit=10)
    ledger.add('local', 'video', 1.25)
    ledger.add('local', 'image', 0.75)
    assert ledger.total == 2.0
    assert ledger.status()['within_limits'] is True
    with pytest.raises(RuntimeError):
        ledger.add('paid', 'video', 8.01)


def test_cost_ledger_reports_soft_limit_breach():
    ledger = CostLedger(daily_limit=1, monthly_limit=50, hard_limit=100)
    ledger.add('provider', 'llm', 1.01)
    assert ledger.status()['within_limits'] is False
