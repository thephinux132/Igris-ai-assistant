from __future__ import annotations

import asyncio
import json
from typing import Any, Awaitable, Callable, Dict, Optional


class Gossip:
    """Lightweight gossip interface (transport-agnostic).

    on_message: async callback(channel: str, payload: dict)
    publish: async send(channel: str, payload: dict)
    subscribe: register interest in channels
    """

    def __init__(self) -> None:
        self._subs: Dict[str, Callable[[str, Dict[str, Any]], Awaitable[None]]] = {}

    def subscribe(self, channel: str, handler: Callable[[str, Dict[str, Any]], Awaitable[None]]) -> None:
        self._subs[channel] = handler

    async def publish(self, channel: str, payload: Dict[str, Any]) -> None:
        # loopback stub; replace with network transport
        handler = self._subs.get(channel)
        if handler:
            await handler(channel, payload)

