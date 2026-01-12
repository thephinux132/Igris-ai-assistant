#!/usr/bin/env python3
"""
API Authentication Module for Igris
Handles API key management and request authentication.
"""

import secrets
import hashlib
import hmac
import logging
import time
from pathlib import Path
from typing import Optional, Dict, Tuple
from dataclasses import dataclass
from functools import wraps
from collections import defaultdict
import threading

logger = logging.getLogger(__name__)

@dataclass
class APIKey:
    key_id: str
    key_hash: str
    name: str
    created: float
    last_used: Optional[float] = None
    permissions: list = None

    def __post_init__(self):
        if self.permissions is None:
            self.permissions = ["read", "execute"]

class RateLimiter:
    """Token bucket rate limiter."""

    def __init__(self, rate: int = 60, burst: int = 10):
        self.rate = rate  # tokens per minute
        self.burst = burst
        self.tokens: Dict[str, float] = defaultdict(lambda: burst)
        self.last_update: Dict[str, float] = defaultdict(time.time)
        self.lock = threading.Lock()

    def allow(self, key: str) -> Tuple[bool, int]:
        """
        Check if request is allowed.

        Returns:
            (allowed, retry_after_seconds)
        """
        with self.lock:
            now = time.time()
            elapsed = now - self.last_update[key]
            self.last_update[key] = now

            # Add tokens based on elapsed time
            self.tokens[key] = min(
                self.burst,
                self.tokens[key] + elapsed * (self.rate / 60)
            )

            if self.tokens[key] >= 1:
                self.tokens[key] -= 1
                return True, 0
            else:
                retry_after = int((1 - self.tokens[key]) * 60 / self.rate)
                return False, retry_after

class APIKeyManager:
    """Manages API keys for remote access."""

    def __init__(self, keys_path: Optional[Path] = None):
        self.keys_path = keys_path or Path(__file__).parent.parent / "config" / ".api_keys"
        self.keys: Dict[str, APIKey] = {}
        self.lock = threading.Lock()
        self._load_keys()

    def _load_keys(self):
        """Load API keys from secure storage."""
        if not self.keys_path.exists():
            return

        try:
            import json
            data = json.loads(self.keys_path.read_text())
            for key_data in data.get("keys", []):
                key = APIKey(**key_data)
                self.keys[key.key_id] = key
            logger.info(f"Loaded {len(self.keys)} API keys")
        except Exception as e:
            logger.error(f"Failed to load API keys: {e}")

    def _save_keys(self):
        """Save API keys to storage."""
        import json
        data = {
            "keys": [
                {
                    "key_id": k.key_id,
                    "key_hash": k.key_hash,
                    "name": k.name,
                    "created": k.created,
                    "last_used": k.last_used,
                    "permissions": k.permissions
                }
                for k in self.keys.values()
            ]
        }
        self.keys_path.parent.mkdir(parents=True, exist_ok=True)
        self.keys_path.write_text(json.dumps(data, indent=2))
        # Restrict permissions
        self.keys_path.chmod(0o600)

    def generate_key(self, name: str, permissions: list = None) -> str:
        """
        Generate a new API key.

        Returns:
            The raw API key (only shown once)
        """
        # Generate secure random key
        raw_key = secrets.token_urlsafe(32)
        key_id = secrets.token_hex(8)
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

        key = APIKey(
            key_id=key_id,
            key_hash=key_hash,
            name=name,
            created=time.time(),
            permissions=permissions or ["read", "execute"]
        )

        with self.lock:
            self.keys[key_id] = key
            self._save_keys()

        # Return format: key_id.raw_key
        return f"{key_id}.{raw_key}"

    def validate_key(self, api_key: str) -> Optional[APIKey]:
        """
        Validate an API key.

        Args:
            api_key: Key in format key_id.raw_key

        Returns:
            APIKey if valid, None otherwise
        """
        try:
            key_id, raw_key = api_key.split(".", 1)
        except ValueError:
            return None

        key = self.keys.get(key_id)
        if not key:
            return None

        # Verify hash
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        if not hmac.compare_digest(key_hash, key.key_hash):
            return None

        # Update last used
        with self.lock:
            key.last_used = time.time()

        return key

    def revoke_key(self, key_id: str) -> bool:
        """Revoke an API key."""
        with self.lock:
            if key_id in self.keys:
                del self.keys[key_id]
                self._save_keys()
                return True
        return False

    def list_keys(self) -> list:
        """List all API keys (without secrets)."""
        return [
            {
                "key_id": k.key_id,
                "name": k.name,
                "created": k.created,
                "last_used": k.last_used,
                "permissions": k.permissions
            }
            for k in self.keys.values()
        ]


# Decorator for protected endpoints
def require_api_key(permissions: list = None):
    """Decorator to require API key authentication."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # This will be implemented by the web framework
            # Placeholder for framework-agnostic design
            return func(*args, **kwargs)
        wrapper._require_api_key = True
        wrapper._required_permissions = permissions or ["read"]
        return wrapper
    return decorator
