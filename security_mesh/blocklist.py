from __future__ import annotations

from pathlib import Path
import json
from typing import Set


class Blocklist:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._set: Set[str] = set()
        self._load()

    def _load(self) -> None:
        try:
            self._set = set(json.loads(self.path.read_text(encoding="utf-8")))
        except Exception:
            self._set = set()

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(sorted(self._set), indent=2), encoding="utf-8")

    def add(self, fingerprint: str) -> None:
        self._set.add(fingerprint)
        self._save()

    def remove(self, fingerprint: str) -> None:
        self._set.discard(fingerprint)
        self._save()

    def contains(self, fingerprint: str) -> bool:
        return fingerprint in self._set

