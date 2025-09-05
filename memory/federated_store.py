from __future__ import annotations

import base64
import json
import os
import time
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Dict, Optional

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM  # type: ignore
except Exception:  # keep optional
    AESGCM = None  # type: ignore


@dataclass
class Record:
    key: str
    value: Any
    ttl_sec: Optional[int] = None
    created_ts: float = time.time()

    def expired(self) -> bool:
        return self.ttl_sec is not None and (time.time() - self.created_ts) > self.ttl_sec


class FederatedStore:
    """Encrypted JSON-backed store with per-device keys and TTL.

    Storage layout (directory):
      - meta.json (device_id, key_hint)
      - records/*.rec (encrypted blobs)
    """

    def __init__(self, root: Path, device_id: str, key: bytes) -> None:
        self.root = root
        self.device_id = device_id
        self.key = key
        self.meta = {"device_id": device_id, "key_hint": sha256(key).hexdigest()[:8]}
        (self.root / "records").mkdir(parents=True, exist_ok=True)
        (self.root / "meta.json").write_text(json.dumps(self.meta, indent=2), encoding="utf-8")

    def _enc(self, data: bytes) -> bytes:
        if AESGCM is None:
            # XOR fallback (not secure) to keep runtime optional; for dev only
            return bytes(b ^ self.key[0] for b in data)
        nonce = os.urandom(12)
        ct = AESGCM(self.key).encrypt(nonce, data, None)
        return nonce + ct

    def _dec(self, blob: bytes) -> bytes:
        if AESGCM is None:
            return bytes(b ^ self.key[0] for b in blob)
        nonce, ct = blob[:12], blob[12:]
        return AESGCM(self.key).decrypt(nonce, ct, None)

    def put(self, key: str, value: Any, ttl_sec: Optional[int] = None) -> None:
        rec = Record(key=key, value=value, ttl_sec=ttl_sec, created_ts=time.time())
        data = json.dumps(rec.__dict__).encode("utf-8")
        blob = self._enc(data)
        path = self.root / "records" / f"{sha256(key.encode()).hexdigest()}.rec"
        path.write_bytes(blob)

    def get(self, key: str) -> Optional[Any]:
        path = self.root / "records" / f"{sha256(key.encode()).hexdigest()}.rec"
        if not path.exists():
            return None
        try:
            data = self._dec(path.read_bytes())
            rec = json.loads(data.decode("utf-8"))
            # expired?
            if rec.get("ttl_sec") is not None:
                if (time.time() - float(rec.get("created_ts", time.time()))) > float(rec["ttl_sec"]):
                    try:
                        path.unlink()
                    finally:
                        return None
            return rec.get("value")
        except Exception:
            return None

    def purge_expired(self) -> int:
        removed = 0
        for p in (self.root / "records").glob("*.rec"):
            try:
                data = self._dec(p.read_bytes())
                rec = json.loads(data.decode("utf-8"))
                ttl = rec.get("ttl_sec")
                created = rec.get("created_ts", time.time())
                if ttl is not None and (time.time() - float(created)) > float(ttl):
                    p.unlink()
                    removed += 1
            except Exception:
                continue
        return removed

