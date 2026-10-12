from quiz_assistant.budget import (
    BudgetLedger,
    calculate_measured_cost,
    estimate_request_reservation,
)
from quiz_assistant.models import ApiConfig


def test_budget_reservation_reconciliation_and_uncertain_cost() -> None:
    ledger = BudgetLedger(0.10)
    assert ledger.reserve("one", 0.02)
    ledger.reconcile("one", 0.01)
    assert ledger.reserve("two", 0.03)
    ledger.mark_uncertain("two")
    snapshot = ledger.snapshot()
    assert snapshot.spent_usd == 0.01
    assert snapshot.uncertain_usd == 0.03
    assert snapshot.reserved_usd == 0


def test_budget_rejects_request_over_limit() -> None:
    ledger = BudgetLedger(0.01)
    assert not ledger.reserve("too-expensive", 0.02)


def test_luna_cost_and_reservation_are_small_but_positive() -> None:
    config = ApiConfig()
    assert 0 < estimate_request_reservation(config) < config.session_budget_usd
    assert calculate_measured_cost("gpt-6-luna", 2500, 600) == 0.00055


def test_reservation_scales_with_images_and_output():
    one = estimate_request_reservation(ApiConfig(), 1)
    assert estimate_request_reservation(ApiConfig(), 6) > one
    assert estimate_request_reservation(ApiConfig(max_output_tokens=10000), 1) > one


def test_reconcile_unknown_cost_is_idempotent():
    ledger = BudgetLedger(.5)
    ledger.reserve("a", .1)
    ledger.mark_uncertain("a")
    ledger.reconcile("a", .02)
    ledger.reconcile("a", .02)
    assert ledger.snapshot().spent_usd == .02
    assert ledger.snapshot().uncertain_usd == 0
