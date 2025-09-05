from __future__ import annotations

import os
import socket
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class DeviceIdentity:
    device_id: str
    hostname: str
    cert_path: Optional[Path] = None
    key_path: Optional[Path] = None


def generate_local_identity(root: Path) -> DeviceIdentity:
    root.mkdir(parents=True, exist_ok=True)
    device_id = socket.gethostname()
    # placeholders for TLS material
    (root / "device.id").write_text(device_id, encoding="utf-8")
    return DeviceIdentity(device_id=device_id, hostname=device_id)

