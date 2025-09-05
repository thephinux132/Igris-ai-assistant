from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional


@dataclass
class Peer:
    id: str
    host: str
    port: int
    last_seen: float


class PeerStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._peers: Dict[str, Peer] = {}
        self._load()

    def _load(self) -> None:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            for k, v in data.items():
                self._peers[k] = Peer(**v)
        except Exception:
            self._peers = {}

    def _save(self) -> None:
        data = {k: p.__dict__ for k, p in self._peers.items()}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def upsert(self, peer: Peer) -> None:
        self._peers[peer.id] = peer
        self._save()

    def touch(self, peer_id: str) -> None:
        if peer_id in self._peers:
            self._peers[peer_id].last_seen = time.time()
            self._save()

    def list(self) -> Dict[str, Peer]:
        return dict(self._peers)

