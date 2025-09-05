from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional


Mode = Literal["fast", "balanced", "smart"]


@dataclass(frozen=True)
class AIRouterPolicy:
    default_mode: Mode = "balanced"
    low_battery_mode: Mode = "fast"
    high_latency_mode: Mode = "fast"
    plugged_in_mode: Mode = "smart"
    user_priority: Mode = "balanced"  # override when set by user
    max_latency_ms_fast: int = 800
    max_latency_ms_smart: int = 4000


def load_policy_from_dict(d: dict) -> AIRouterPolicy:
    try:
        return AIRouterPolicy(
            default_mode=d.get("default_mode", "balanced"),
            low_battery_mode=d.get("low_battery_mode", "fast"),
            high_latency_mode=d.get("high_latency_mode", "fast"),
            plugged_in_mode=d.get("plugged_in_mode", "smart"),
            user_priority=d.get("user_priority", "balanced"),
            max_latency_ms_fast=int(d.get("max_latency_ms_fast", 800)),
            max_latency_ms_smart=int(d.get("max_latency_ms_smart", 4000)),
        )
    except Exception:
        return AIRouterPolicy()

