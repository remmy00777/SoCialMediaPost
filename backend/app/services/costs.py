from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass(slots=True)
class CostLedger:
    daily_limit: float
    monthly_limit: float
    hard_limit: float
    entries: list[dict[str, float | str]] = field(default_factory=list)

    def add(self, provider: str, category: str, amount_usd: float) -> None:
        projected = self.total + amount_usd
        if projected > self.hard_limit:
            raise RuntimeError("Hard spending limit would be exceeded")
        self.entries.append(
            {
                "provider": provider,
                "category": category,
                "amount_usd": round(amount_usd, 6),
                "timestamp": datetime.now(UTC).isoformat(),
            }
        )

    @property
    def total(self) -> float:
        return round(sum(float(entry["amount_usd"]) for entry in self.entries), 6)

    def status(self) -> dict[str, float | bool]:
        return {
            "total_usd": self.total,
            "daily_limit_usd": self.daily_limit,
            "monthly_limit_usd": self.monthly_limit,
            "hard_limit_usd": self.hard_limit,
            "within_limits": self.total <= min(self.daily_limit, self.monthly_limit, self.hard_limit),
        }
