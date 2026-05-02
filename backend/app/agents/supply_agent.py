"""Agent: supply risk signals (extensible for carrier delays, vendor scorecards, etc.)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SupplyAssessment:
    sku: str
    risk_score: float
    factors: dict[str, Any]


class SupplyAgent:
    """
    Computes a lightweight supply-risk score used by other agents (e.g., InventoryAgent).
    Phase A uses deterministic heuristics; later versions can ingest vendor APIs.
    """

    def assess(self, sku: str, *, disruption_lead_time_days: int | None) -> SupplyAssessment:
        factors: dict[str, Any] = {}
        if disruption_lead_time_days is not None and disruption_lead_time_days > 14:
            factors["long_lead_time"] = True
            risk = 0.65
        elif disruption_lead_time_days is not None:
            factors["elevated_lead_time"] = True
            risk = 0.35
        else:
            risk = 0.1
        return SupplyAssessment(sku=sku, risk_score=risk, factors=factors)
