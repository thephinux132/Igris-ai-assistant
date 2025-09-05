from __future__ import annotations

import subprocess
import threading
import time
from typing import Callable, Optional


class Watchdog:
    """Lightweight watchdog for external processes or long-running functions."""

    def __init__(self, timeout_sec: int = 60, on_hung: Optional[Callable[[], None]] = None) -> None:
        self.timeout_sec = timeout_sec
        self.on_hung = on_hung
        self._last_heartbeat = time.time()

    def heartbeat(self) -> None:
        self._last_heartbeat = time.time()

    def monitor(self, stop_flag: Callable[[], bool]) -> None:
        while not stop_flag():
            if time.time() - self._last_heartbeat > self.timeout_sec:
                if self.on_hung:
                    self.on_hung()
                self._last_heartbeat = time.time()  # prevent immediate re-trigger
            time.sleep(1.0)

