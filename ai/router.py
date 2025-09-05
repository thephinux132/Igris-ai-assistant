from __future__ import annotations

import time
from typing import Callable, Optional

from .bench import AIBenchmarker
from .policy_defaults import AIRouterPolicy, load_policy_from_dict


class AIRouter:
    """Route prompts to the best backend based on policy and live metrics.

    backends:
      - local_llm(prompt) -> str
      - remote_llm(prompt) -> str

    env_signals (callables returning scalars/bools) are optional:
      - battery_low() -> bool
      - plugged_in() -> bool
      - network_latency_ms() -> float
    """

    def __init__(
        self,
        local_llm: Callable[[str], str],
        remote_llm: Callable[[str], str],
        policy: Optional[AIRouterPolicy] = None,
        battery_low: Optional[Callable[[], bool]] = None,
        plugged_in: Optional[Callable[[], bool]] = None,
        network_latency_ms: Optional[Callable[[], float]] = None,
    ) -> None:
        self.local_llm = local_llm
        self.remote_llm = remote_llm
        self.policy = policy or AIRouterPolicy()
        self.bench = AIBenchmarker()
        self.battery_low = battery_low
        self.plugged_in = plugged_in
        self.network_latency_ms = network_latency_ms
        self.user_override_mode: Optional[str] = None

    def set_policy(self, dct: dict) -> None:
        self.policy = load_policy_from_dict(dct)

    def set_user_override(self, mode: Optional[str]) -> None:
        self.user_override_mode = mode

    def _decide_mode(self) -> str:
        if self.user_override_mode:
            return self.user_override_mode
        if callable(self.plugged_in) and self.plugged_in():
            return self.policy.plugged_in_mode
        if callable(self.battery_low) and self.battery_low():
            return self.policy.low_battery_mode
        if callable(self.network_latency_ms):
            try:
                if self.network_latency_ms() > self.policy.max_latency_ms_fast:
                    return self.policy.high_latency_mode
            except Exception:
                pass
        return self.policy.default_mode

    def ask(self, prompt: str) -> str:
        mode = self._decide_mode()
        chosen = "local" if mode == "fast" else "remote"
        fn = self.local_llm if chosen == "local" else self.remote_llm
        start = time.time()
        out = fn(prompt)
        end = time.time()
        self.bench.record(chosen, start, end)
        return out

