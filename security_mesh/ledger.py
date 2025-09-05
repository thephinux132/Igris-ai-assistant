from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import List, Optional


@dataclass
class LedgerEntry:
    idx: int
    prev_hash: str
    payload: dict
    sig: Optional[str] = None  # placeholder for signature

    def compute_hash(self) -> str:
        h = sha256()
        h.update(str(self.idx).encode())
        h.update(self.prev_hash.encode())
        h.update(json.dumps(self.payload, sort_keys=True).encode())
        if self.sig:
            h.update(self.sig.encode())
        return h.hexdigest()


class Ledger:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.entries: List[LedgerEntry] = []
        self._load()

    def _load(self) -> None:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self.entries = [LedgerEntry(**e) for e in data]
        except Exception:
            self.entries = []

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = [e.__dict__ for e in self.entries]
        self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def append(self, payload: dict, sig: Optional[str] = None) -> LedgerEntry:
        prev_hash = self.entries[-1].compute_hash() if self.entries else "genesis"
        e = LedgerEntry(idx=len(self.entries), prev_hash=prev_hash, payload=payload, sig=sig)
        self.entries.append(e)
        self._save()
        return e

    def verify(self) -> bool:
        prev = "genesis"
        for idx, e in enumerate(self.entries):
            if e.idx != idx:
                return False
            if e.prev_hash != prev:
                return False
            prev = e.compute_hash()
        return True

