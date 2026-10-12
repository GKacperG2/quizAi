from __future__ import annotations

from dataclasses import dataclass

from quiz_assistant.models import ApiConfig


MODEL_PRICES_PER_MILLION = {
    "gpt-6-luna": (0.10, 0.50),
    "gpt-6.1-sol": (2.00, 10.00),
    "gpt-6-astra": (10.00, 50.00),
}


@dataclass(frozen=True, slots=True)
class BudgetSnapshot:
    limit_usd: float
    spent_usd: float
    reserved_usd: float
    uncertain_usd: float


class BudgetLedger:
    def __init__(self, limit_usd: float = 0.50) -> None:
        self._limit = limit_usd
        self._spent = 0.0
        self._uncertain: dict[str, float] = {}
        self._reservations: dict[str, float] = {}

    def set_limit(self, limit_usd: float) -> None:
        self._limit = max(0.0, float(limit_usd))

    def reserve(self, request_id: str, amount_usd: float) -> bool:
        amount = max(0.0, float(amount_usd))
        if request_id in self._reservations or request_id in self._uncertain:
            return False
        projected = self._spent + sum(self._uncertain.values()) + sum(self._reservations.values()) + amount
        if projected > self._limit:
            return False
        self._reservations[request_id] = amount
        return True

    def reconcile(self, request_id: str, actual_usd: float) -> None:
        if request_id not in self._reservations and request_id not in self._uncertain:
            return
        self._reservations.pop(request_id, None)
        self._uncertain.pop(request_id, None)
        self._spent += max(0.0, float(actual_usd))

    def release(self, request_id: str) -> None:
        self._reservations.pop(request_id, None)
        self._uncertain.pop(request_id, None)

    def mark_uncertain(self, request_id: str) -> None:
        if request_id in self._reservations:
            self._uncertain[request_id] = self._reservations.pop(request_id)

    def snapshot(self) -> BudgetSnapshot:
        return BudgetSnapshot(
            limit_usd=self._limit,
            spent_usd=self._spent,
            reserved_usd=sum(self._reservations.values()),
            uncertain_usd=sum(self._uncertain.values()),
        )


def estimate_request_reservation(config: ApiConfig, frame_count: int = 1) -> float:
    input_price, output_price = MODEL_PRICES_PER_MILLION.get(
        config.model, MODEL_PRICES_PER_MILLION["gpt-6.1-sol"]
    )
    # Conservative local estimate, not a provider-side spending cap.
    raw = ((2000 + 8000 * frame_count) * input_price + config.max_output_tokens * output_price) / 1_000_000
    return raw * 1.3


def calculate_measured_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    input_price, output_price = MODEL_PRICES_PER_MILLION.get(
        model, MODEL_PRICES_PER_MILLION["gpt-6.1-sol"]
    )
    return (input_tokens * input_price + output_tokens * output_price) / 1_000_000
