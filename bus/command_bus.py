from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable, Dict, List


class CommandBus:
    """Fan-out aggregator with inproc transport.

    Subscribers register handlers by command name. `dispatch` sends to all reachable nodes
    (loopback-only in this stub) and aggregates responses.
    """

    def __init__(self) -> None:
        self._handlers: Dict[str, List[Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]]] = {}

    def subscribe(self, command: str, handler: Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]) -> None:
        self._handlers.setdefault(command, []).append(handler)

    async def dispatch(self, command: str, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for h in self._handlers.get(command, []):
            try:
                results.append(await h(dict(payload)))
            except Exception as e:
                results.append({"error": str(e)})
        return results

