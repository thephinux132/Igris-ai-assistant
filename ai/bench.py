from __future__ import annotations

import time
from statistics import mean
from typing import Callable, Dict, List, Optional


class AIBenchmarker:
    """Track rolling latency and simple quality proxies per backend.

    Quality proxy is caller-provided (e.g., exact match rate on prompts with known answers).
    """

    def __init__(self, window: int = 20) -> None:
        self.window = window
        self.latency_ms: Dict[str, List[float]] = {}
        self.quality: Dict[str, List[float]] = {}

    def record(self, backend: str, start: float, end: float, quality: Optional[float] = None) -> None:
        dt = (end - start) * 1000.0
        self.latency_ms.setdefault(backend, []).append(dt)
        if len(self.latency_ms[backend]) > self.window:
            self.latency_ms[backend] = self.latency_ms[backend][-self.window :]
        if quality is not None:
            self.quality.setdefault(backend, []).append(quality)
            if len(self.quality[backend]) > self.window:
                self.quality[backend] = self.quality[backend][-self.window :]

    def avg_latency(self, backend: str) -> Optional[float]:
        vals = self.latency_ms.get(backend)
        return mean(vals) if vals else None

    def avg_quality(self, backend: str) -> Optional[float]:
        vals = self.quality.get(backend)
        return mean(vals) if vals else None

