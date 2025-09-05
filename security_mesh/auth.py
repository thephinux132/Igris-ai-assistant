from __future__ import annotations

import hashlib
from typing import Tuple


def fingerprint_public_key(pem: bytes) -> str:
    """Return SHA-256 fingerprint of a PEM public key (hex)."""
    return hashlib.sha256(pem).hexdigest()


def cross_sign_statement(statement: bytes, signer_key: bytes) -> Tuple[bytes, str]:
    """Placeholder for detached signature; returns (sig, alg_hint).

    Replace with real crypto as needed.
    """
    digest = hashlib.sha256(signer_key + statement).hexdigest().encode()
    return digest, "sha256-dev"

