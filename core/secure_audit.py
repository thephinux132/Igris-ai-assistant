#!/usr/bin/env python3
"""
Secure Audit Logging for Igris
Provides encrypted, tamper-evident audit trail.
"""

import json
import logging
import hashlib
import hmac
import os
import gzip
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict
from enum import Enum
import threading

logger = logging.getLogger(__name__)

# Optional dependencies
try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.backends import default_backend
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    logger.warning("cryptography not available - audit logs will not be encrypted")

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

class AuditEventType(Enum):
    AUTH_SUCCESS = "auth_success"
    AUTH_FAILURE = "auth_failure"
    AUTH_LOCKOUT = "auth_lockout"
    COMMAND_EXECUTED = "command_executed"
    COMMAND_BLOCKED = "command_blocked"
    APPROVAL_GRANTED = "approval_granted"
    APPROVAL_DENIED = "approval_denied"
    API_REQUEST = "api_request"
    CONFIG_CHANGE = "config_change"
    SECURITY_VIOLATION = "security_violation"
    KEY_REGISTERED = "key_registered"
    KEY_REVOKED = "key_revoked"
    SYSTEM_START = "system_start"
    SYSTEM_STOP = "system_stop"

@dataclass
class AuditEntry:
    timestamp: str
    event_type: str
    severity: str  # INFO, WARNING, CRITICAL
    actor: str  # user/system identifier
    action: str
    target: Optional[str]
    details: Optional[Dict[str, Any]]
    result: str  # success, failure, blocked
    source_ip: Optional[str]
    previous_hash: Optional[str]  # For chain verification

    def to_dict(self) -> dict:
        return asdict(self)

    def compute_hash(self) -> str:
        """Compute hash for integrity verification."""
        data = json.dumps(self.to_dict(), sort_keys=True)
        return hashlib.sha256(data.encode()).hexdigest()

class AuditLogEncryption:
    """Handles encryption/decryption of audit entries."""

    def __init__(self, key: bytes):
        if not CRYPTO_AVAILABLE:
            raise RuntimeError("cryptography library required for encryption")
        self.aesgcm = AESGCM(key)

    @classmethod
    def derive_key(cls, password: str, salt: bytes) -> bytes:
        """Derive encryption key from password."""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,  # 256 bits
            salt=salt,
            iterations=100000,
            backend=default_backend()
        )
        return kdf.derive(password.encode())

    def encrypt(self, data: bytes) -> bytes:
        """Encrypt data with AES-256-GCM."""
        nonce = os.urandom(12)
        ciphertext = self.aesgcm.encrypt(nonce, data, None)
        return nonce + ciphertext

    def decrypt(self, data: bytes) -> bytes:
        """Decrypt data."""
        nonce = data[:12]
        ciphertext = data[12:]
        return self.aesgcm.decrypt(nonce, ciphertext, None)

class SecureAuditLog:
    """Secure, tamper-evident audit logging system."""

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or Path(__file__).parent.parent / "config" / "audit_config.yaml"
        self.config = self._load_config()

        self.log_dir = Path(self.config.get("storage", {}).get("path", "logs/audit"))
        self.log_dir.mkdir(parents=True, exist_ok=True)

        self.encryption: Optional[AuditLogEncryption] = None
        self.current_log_path: Optional[Path] = None
        self.last_hash: Optional[str] = None
        self.lock = threading.Lock()

        self._init_current_log()
        self._init_encryption()

    def _load_config(self) -> dict:
        """Load audit configuration."""
        if YAML_AVAILABLE and self.config_path.exists():
            try:
                return yaml.safe_load(self.config_path.read_text())
            except Exception as e:
                logger.error(f"Failed to load audit config: {e}")

        return {
            "storage": {"path": "logs/audit", "max_size_mb": 100},
            "encryption": {"enabled": False},
            "integrity": {"enabled": True, "chain_verification": True}
        }

    def _init_encryption(self):
        """Initialize encryption if configured."""
        if not self.config.get("encryption", {}).get("enabled", False):
            return

        if not CRYPTO_AVAILABLE:
            logger.warning("Encryption enabled but cryptography not available")
            return

        # Get or create encryption key
        key_path = self.log_dir / ".audit_key"
        salt_path = self.log_dir / ".audit_salt"

        if key_path.exists() and salt_path.exists():
            # Load existing
            salt = salt_path.read_bytes()
            # In production, key should come from secure storage
            # For now, derive from machine-specific data
            password = self._get_machine_id()
        else:
            # Generate new
            salt = os.urandom(16)
            salt_path.write_bytes(salt)
            salt_path.chmod(0o600)
            password = self._get_machine_id()

        try:
            key = AuditLogEncryption.derive_key(password, salt)
            self.encryption = AuditLogEncryption(key)
            logger.info("Audit log encryption initialized")
        except Exception as e:
            logger.error(f"Failed to initialize encryption: {e}")

    def _get_machine_id(self) -> str:
        """Get machine-specific identifier for key derivation."""
        import platform
        import uuid

        # Combine various machine identifiers
        components = [
            platform.node(),
            str(uuid.getnode()),  # MAC address
            platform.system(),
        ]
        return hashlib.sha256(":".join(components).encode()).hexdigest()

    def _init_current_log(self):
        """Initialize or find current log file."""
        today = datetime.now().strftime("%Y-%m-%d")
        self.current_log_path = self.log_dir / f"audit_{today}.log"

        # Get last hash for chain verification
        if self.current_log_path.exists():
            self.last_hash = self._get_last_hash()

    def _get_last_hash(self) -> Optional[str]:
        """Get hash of last entry for chain verification."""
        if not self.current_log_path.exists():
            return None

        try:
            with open(self.current_log_path, 'rb') as f:
                # Read last line
                f.seek(0, 2)  # End
                size = f.tell()
                if size == 0:
                    return None

                # Find last newline
                pos = size - 1
                while pos > 0:
                    f.seek(pos)
                    if f.read(1) == b'\n':
                        break
                    pos -= 1

                last_line = f.read().strip()

                if self.encryption:
                    last_line = self.encryption.decrypt(last_line)

                entry = json.loads(last_line)
                return entry.get("_hash")
        except Exception as e:
            logger.error(f"Failed to get last hash: {e}")
            return None

    def _rotate_if_needed(self):
        """Rotate log if size limit reached."""
        if not self.current_log_path.exists():
            return

        max_size = self.config.get("storage", {}).get("max_size_mb", 100) * 1024 * 1024

        if self.current_log_path.stat().st_size >= max_size:
            # Compress and archive
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            archive_path = self.log_dir / f"audit_{timestamp}.log.gz"

            with open(self.current_log_path, 'rb') as f_in:
                with gzip.open(archive_path, 'wb') as f_out:
                    f_out.write(f_in.read())

            self.current_log_path.unlink()
            logger.info(f"Rotated audit log to {archive_path}")

            # Clean old archives
            self._cleanup_old_archives()

    def _cleanup_old_archives(self):
        """Remove old archived logs."""
        max_count = self.config.get("storage", {}).get("rotation_count", 10)
        archives = sorted(self.log_dir.glob("audit_*.log.gz"), reverse=True)

        for archive in archives[max_count:]:
            archive.unlink()
            logger.info(f"Removed old archive: {archive}")

    def log(
        self,
        event_type: AuditEventType,
        actor: str,
        action: str,
        target: Optional[str] = None,
        details: Optional[Dict] = None,
        result: str = "success",
        severity: str = "INFO",
        source_ip: Optional[str] = None
    ):
        """
        Log an audit event.

        Args:
            event_type: Type of event
            actor: Who performed the action
            action: What action was performed
            target: Target of the action
            details: Additional details
            result: Outcome (success, failure, blocked)
            severity: INFO, WARNING, CRITICAL
            source_ip: Source IP if applicable
        """
        # Check if event type should be logged
        events_config = self.config.get("events", {})
        event_category = event_type.value.split("_")[0]
        if not events_config.get(event_category, True):
            return

        entry = AuditEntry(
            timestamp=datetime.utcnow().isoformat() + "Z",
            event_type=event_type.value,
            severity=severity,
            actor=actor,
            action=action,
            target=target,
            details=details,
            result=result,
            source_ip=source_ip,
            previous_hash=self.last_hash if self.config.get("integrity", {}).get("chain_verification", True) else None
        )

        # Compute hash for this entry
        entry_dict = entry.to_dict()
        entry_hash = entry.compute_hash()
        entry_dict["_hash"] = entry_hash

        with self.lock:
            self._rotate_if_needed()

            # Serialize
            line = json.dumps(entry_dict)

            # Encrypt if enabled
            if self.encryption:
                line = self.encryption.encrypt(line.encode())
            else:
                line = line.encode()

            # Write
            with open(self.current_log_path, 'ab') as f:
                f.write(line + b'\n')

            # Update chain
            self.last_hash = entry_hash

        logger.debug(f"Audit: {event_type.value} by {actor}")

    def verify_integrity(self, log_path: Optional[Path] = None) -> Dict[str, Any]:
        """
        Verify integrity of audit log.

        Returns:
            Verification result with status and details
        """
        log_path = log_path or self.current_log_path

        if not log_path.exists():
            return {"status": "error", "message": "Log file not found"}

        results = {
            "status": "valid",
            "entries_checked": 0,
            "chain_valid": True,
            "errors": []
        }

        previous_hash = None

        try:
            with open(log_path, 'rb') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue

                    # Decrypt if needed
                    if self.encryption:
                        try:
                            line = self.encryption.decrypt(line)
                        except Exception:
                            results["errors"].append(f"Line {line_num}: Decryption failed")
                            results["status"] = "corrupted"
                            continue

                    try:
                        entry_dict = json.loads(line)
                    except json.JSONDecodeError:
                        results["errors"].append(f"Line {line_num}: Invalid JSON")
                        results["status"] = "corrupted"
                        continue

                    # Verify hash
                    stored_hash = entry_dict.pop("_hash", None)
                    computed_hash = hashlib.sha256(
                        json.dumps(entry_dict, sort_keys=True).encode()
                    ).hexdigest()

                    if stored_hash != computed_hash:
                        results["errors"].append(f"Line {line_num}: Hash mismatch")
                        results["status"] = "tampered"

                    # Verify chain
                    if self.config.get("integrity", {}).get("chain_verification", True):
                        if entry_dict.get("previous_hash") != previous_hash:
                            if previous_hash is not None:  # First entry has no previous
                                results["chain_valid"] = False
                                results["errors"].append(f"Line {line_num}: Chain broken")
                                results["status"] = "tampered"

                    previous_hash = stored_hash
                    results["entries_checked"] += 1

        except Exception as e:
            results["status"] = "error"
            results["errors"].append(str(e))

        return results

    def export(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        format: str = "json"
    ) -> str:
        """
        Export audit logs.

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            format: Output format (json, csv)

        Returns:
            Exported data as string
        """
        entries = []

        # Find relevant log files
        log_files = sorted(self.log_dir.glob("audit_*.log"))

        for log_path in log_files:
            with open(log_path, 'rb') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    if self.encryption:
                        try:
                            line = self.encryption.decrypt(line)
                        except Exception:
                            continue

                    try:
                        entry = json.loads(line)

                        # Filter by date
                        ts = entry.get("timestamp", "")[:10]
                        if start_date and ts < start_date:
                            continue
                        if end_date and ts > end_date:
                            continue

                        entries.append(entry)
                    except json.JSONDecodeError:
                        continue

        if format == "csv":
            if not entries:
                return "timestamp,event_type,severity,actor,action,target,result\n"

            lines = ["timestamp,event_type,severity,actor,action,target,result"]
            for e in entries:
                lines.append(",".join([
                    e.get("timestamp", ""),
                    e.get("event_type", ""),
                    e.get("severity", ""),
                    e.get("actor", ""),
                    e.get("action", "").replace(",", ";"),
                    str(e.get("target", "")).replace(",", ";"),
                    e.get("result", "")
                ]))
            return "\n".join(lines)

        return json.dumps(entries, indent=2)

    def query(
        self,
        event_type: Optional[str] = None,
        actor: Optional[str] = None,
        severity: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict]:
        """Query audit entries."""
        results = []

        if not self.current_log_path.exists():
            return results

        with open(self.current_log_path, 'rb') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                if self.encryption:
                    try:
                        line = self.encryption.decrypt(line)
                    except Exception:
                        continue

                try:
                    entry = json.loads(line)

                    # Apply filters
                    if event_type and entry.get("event_type") != event_type:
                        continue
                    if actor and entry.get("actor") != actor:
                        continue
                    if severity and entry.get("severity") != severity:
                        continue

                    results.append(entry)

                    if len(results) >= limit:
                        break
                except json.JSONDecodeError:
                    continue

        return results


# Global instance
_audit_log = None

def get_audit_log() -> SecureAuditLog:
    global _audit_log
    if _audit_log is None:
        _audit_log = SecureAuditLog()
    return _audit_log

def log_event(
    event_type: AuditEventType,
    actor: str,
    action: str,
    **kwargs
):
    """Convenience function to log audit event."""
    get_audit_log().log(event_type, actor, action, **kwargs)


# Self-test
if __name__ == "__main__":
    print("Secure Audit Log Test")
    print("=" * 50)
    print(f"Encryption available: {CRYPTO_AVAILABLE}")

    audit = SecureAuditLog()

    # Log some test events
    print("\nLogging test events...")

    audit.log(
        AuditEventType.SYSTEM_START,
        actor="system",
        action="Igris started",
        severity="INFO"
    )

    audit.log(
        AuditEventType.AUTH_SUCCESS,
        actor="admin",
        action="PIN authentication",
        details={"method": "pin"},
        result="success"
    )

    audit.log(
        AuditEventType.COMMAND_EXECUTED,
        actor="admin",
        action="open notepad",
        target="notepad.exe",
        result="success"
    )

    audit.log(
        AuditEventType.SECURITY_VIOLATION,
        actor="unknown",
        action="Shell injection attempt",
        details={"input": "test; rm -rf /"},
        result="blocked",
        severity="CRITICAL"
    )

    print(f"Log file: {audit.current_log_path}")

    # Verify integrity
    print("\nVerifying integrity...")
    result = audit.verify_integrity()
    print(f"Status: {result['status']}")
    print(f"Entries checked: {result['entries_checked']}")
    print(f"Chain valid: {result['chain_valid']}")

    if result['errors']:
        print("Errors:")
        for err in result['errors']:
            print(f"  - {err}")

    # Query recent
    print("\nRecent entries:")
    entries = audit.query(limit=5)
    for e in entries:
        print(f"  [{e['severity']}] {e['event_type']}: {e['action']}")
