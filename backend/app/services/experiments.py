from __future__ import annotations

import hashlib
import math
from typing import Any


def deterministic_assignment(experiment_id: str, package_id: str) -> str:
    digest = hashlib.sha256(f"{experiment_id}:{package_id}".encode()).digest()
    return "control" if digest[0] < 128 else "variant"


def proportion_confidence_interval(successes: int, total: int, z: float = 1.96) -> dict[str, float]:
    if total <= 0:
        return {"lower": 0.0, "upper": 0.0, "estimate": 0.0}
    p = successes / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * total)) / total) / denominator
    return {"lower": max(0, center - margin), "upper": min(1, center + margin), "estimate": p}


def evaluate_experiment(control: list[float], variant: list[float], minimum_sample_size: int) -> dict[str, Any]:
    if len(control) < minimum_sample_size or len(variant) < minimum_sample_size:
        return {"decision": "continue", "reason": "minimum sample size not reached"}
    control_mean = sum(control) / len(control)
    variant_mean = sum(variant) / len(variant)
    lift = (variant_mean - control_mean) / abs(control_mean) if control_mean else 0
    decision = "adopt_variant" if lift >= 0.05 else "keep_control" if lift <= -0.02 else "inconclusive"
    return {
        "decision": decision,
        "control_mean": round(control_mean, 4),
        "variant_mean": round(variant_mean, 4),
        "relative_lift": round(lift, 4),
        "note": "Major changes still require human approval.",
    }
