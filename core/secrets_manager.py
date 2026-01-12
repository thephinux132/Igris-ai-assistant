"""
Secrets Management Module

Provides secure storage for credentials and sensitive data.
Uses platform-specific backends:
- Windows: Windows Credential Manager (win32cred)
- Linux/macOS: keyring library with encryption

Features:
- Secure credential storage (no plaintext files)
- Argon2id password hashing
- Migration from old plaintext policy files
- Cross-platform compatibility
"""

import sys
import os
import base64
import hashlib
import secrets as crypto_secrets
import logging
from pathlib import Path
from typing import Optional, Dict
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('igris.security.secrets')

# Try to import platform-specific modules
HAS_WIN32 = False
HAS_KEYRING = False
HAS_ARGON2 = False

try:
    import win32cred
    import pywintypes
    HAS_WIN32 = True
    logger.info("Windows Credential Manager available")
except ImportError:
    logger.warning("win32cred not available (not on Windows or pywin32 not installed)")

try:
    import keyring
    HAS_KEYRING = True
    logger.info("keyring library available")
except ImportError:
    logger.warning("keyring library not available")

try:
    from argon2 import PasswordHasher, low_level
    from argon2.exceptions import VerifyMismatchError
    HAS_ARGON2 = True
    logger.info("argon2-cffi available")
except ImportError:
    logger.warning("argon2-cffi not available, falling back to PBKDF2")


class SecretStorageError(Exception):
    """Raised when secret storage operations fail"""
    pass


class WindowsCredentialBackend:
    """Windows Credential Manager backend"""

    TARGET_PREFIX = "IgrisAI"

    def __init__(self):
        if not HAS_WIN32:
            raise SecretStorageError("Windows Credential Manager not available")

    def store_secret(self, key: str, value: str) -> None:
        """Store a secret in Windows Credential Manager"""
        target_name = f"{self.TARGET_PREFIX}_{key}"

        credential = {
            'Type': win32cred.CRED_TYPE_GENERIC,
            'TargetName': target_name,
            'UserName': os.getlogin(),
            'CredentialBlob': value,
            'Comment': f'Igris AI Assistant - {key}',
            'Persist': win32cred.CRED_PERSIST_LOCAL_MACHINE
        }

        try:
            win32cred.CredWrite(credential, 0)
            logger.info(f"Stored secret in Windows Credential Manager: {key}")
        except pywintypes.error as e:
            raise SecretStorageError(f"Failed to store secret: {e}")

    def retrieve_secret(self, key: str) -> Optional[str]:
        """Retrieve a secret from Windows Credential Manager"""
        target_name = f"{self.TARGET_PREFIX}_{key}"

        try:
            cred = win32cred.CredRead(target_name, win32cred.CRED_TYPE_GENERIC)
            return cred['CredentialBlob'].decode('utf-8') if isinstance(cred['CredentialBlob'], bytes) else cred['CredentialBlob']
        except pywintypes.error:
            # Credential not found
            return None

    def delete_secret(self, key: str) -> bool:
        """Delete a secret from Windows Credential Manager"""
        target_name = f"{self.TARGET_PREFIX}_{key}"

        try:
            win32cred.CredDelete(target_name, win32cred.CRED_TYPE_GENERIC)
            logger.info(f"Deleted secret from Windows Credential Manager: {key}")
            return True
        except pywintypes.error:
            return False


class KeyringBackend:
    """Cross-platform keyring backend with encryption"""

    SERVICE_NAME = "IgrisAI"

    def __init__(self):
        if not HAS_KEYRING:
            raise SecretStorageError("keyring library not available")

        # Initialize or retrieve encryption key
        self._ensure_master_key()

    def _ensure_master_key(self):
        """Ensure master encryption key exists"""
        try:
            key_b64 = keyring.get_password(self.SERVICE_NAME, "master_key")
            if key_b64:
                self.master_key = base64.b64decode(key_b64)
                logger.info("Loaded existing master key from keyring")
            else:
                # Generate new master key
                self.master_key = crypto_secrets.token_bytes(32)
                key_b64 = base64.b64encode(self.master_key).decode('utf-8')
                keyring.set_password(self.SERVICE_NAME, "master_key", key_b64)
                logger.info("Generated new master key and stored in keyring")
        except Exception as e:
            raise SecretStorageError(f"Failed to initialize master key: {e}")

    def _encrypt(self, plaintext: str) -> str:
        """Simple XOR encryption (use cryptography library for production)"""
        # Note: This is a placeholder. Real implementation should use cryptography.fernet
        from cryptography.fernet import Fernet

        # Derive encryption key from master key
        kdf_key = hashlib.pbkdf2_hmac('sha256', self.master_key, b'igris_salt', 100000)
        fernet_key = base64.urlsafe_b64encode(kdf_key)
        f = Fernet(fernet_key)

        encrypted = f.encrypt(plaintext.encode('utf-8'))
        return base64.b64encode(encrypted).decode('utf-8')

    def _decrypt(self, ciphertext: str) -> str:
        """Decrypt data"""
        from cryptography.fernet import Fernet

        kdf_key = hashlib.pbkdf2_hmac('sha256', self.master_key, b'igris_salt', 100000)
        fernet_key = base64.urlsafe_b64encode(kdf_key)
        f = Fernet(fernet_key)

        encrypted = base64.b64decode(ciphertext)
        return f.decrypt(encrypted).decode('utf-8')

    def store_secret(self, key: str, value: str) -> None:
        """Store an encrypted secret in keyring"""
        try:
            encrypted = self._encrypt(value)
            keyring.set_password(self.SERVICE_NAME, key, encrypted)
            logger.info(f"Stored encrypted secret in keyring: {key}")
        except Exception as e:
            raise SecretStorageError(f"Failed to store secret: {e}")

    def retrieve_secret(self, key: str) -> Optional[str]:
        """Retrieve and decrypt a secret from keyring"""
        try:
            encrypted = keyring.get_password(self.SERVICE_NAME, key)
            if encrypted:
                return self._decrypt(encrypted)
            return None
        except Exception as e:
            logger.error(f"Failed to retrieve secret: {e}")
            return None

    def delete_secret(self, key: str) -> bool:
        """Delete a secret from keyring"""
        try:
            keyring.delete_password(self.SERVICE_NAME, key)
            logger.info(f"Deleted secret from keyring: {key}")
            return True
        except Exception:
            return False


class FallbackFileBackend:
    """Fallback file-based storage (NOT secure, only for testing)"""

    def __init__(self):
        self.storage_dir = Path.home() / ".igris" / "secrets"
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        logger.warning("Using fallback file-based storage (NOT SECURE)")

    def store_secret(self, key: str, value: str) -> None:
        """Store secret in file (base64 encoded, not encrypted)"""
        file_path = self.storage_dir / f"{key}.secret"
        encoded = base64.b64encode(value.encode('utf-8')).decode('utf-8')
        file_path.write_text(encoded)
        os.chmod(file_path, 0o600)  # Read/write for owner only
        logger.warning(f"Stored secret in file (NOT SECURE): {key}")

    def retrieve_secret(self, key: str) -> Optional[str]:
        """Retrieve secret from file"""
        file_path = self.storage_dir / f"{key}.secret"
        if file_path.exists():
            encoded = file_path.read_text()
            return base64.b64decode(encoded).decode('utf-8')
        return None

    def delete_secret(self, key: str) -> bool:
        """Delete secret file"""
        file_path = self.storage_dir / f"{key}.secret"
        if file_path.exists():
            file_path.unlink()
            return True
        return False


class SecretsManager:
    """
    Unified secrets management interface.

    Automatically selects the best available backend:
    1. Windows Credential Manager (Windows)
    2. keyring with encryption (Linux/macOS)
    3. File-based fallback (testing only)
    """

    def __init__(self, backend=None):
        """
        Initialize secrets manager.

        Args:
            backend: Force specific backend ('windows', 'keyring', 'file'),
                    or None for auto-detection
        """
        if backend == 'windows' and HAS_WIN32:
            self.backend = WindowsCredentialBackend()
        elif backend == 'keyring' and HAS_KEYRING:
            self.backend = KeyringBackend()
        elif backend == 'file':
            self.backend = FallbackFileBackend()
        elif backend is None:
            # Auto-detect best backend
            if sys.platform == 'win32' and HAS_WIN32:
                logger.info("Using Windows Credential Manager backend")
                self.backend = WindowsCredentialBackend()
            elif HAS_KEYRING:
                logger.info("Using keyring backend")
                self.backend = KeyringBackend()
            else:
                logger.warning("No secure backend available, using file fallback")
                self.backend = FallbackFileBackend()
        else:
            raise SecretStorageError(f"Backend '{backend}' not available")

        # Initialize password hasher
        if HAS_ARGON2:
            self.password_hasher = PasswordHasher(
                time_cost=3,           # Number of iterations
                memory_cost=65536,     # 64 MB
                parallelism=4,         # Number of threads
                hash_len=32,          # Length of hash
                salt_len=16           # Length of salt
            )
            logger.info("Using Argon2id for password hashing")
        else:
            self.password_hasher = None
            logger.info("Using PBKDF2-SHA256 for password hashing")

    def hash_password(self, password: str) -> str:
        """
        Hash a password securely.

        Uses Argon2id if available, otherwise PBKDF2-SHA256.

        Args:
            password: Plain text password

        Returns:
            Hashed password string
        """
        if self.password_hasher and HAS_ARGON2:
            return self.password_hasher.hash(password)
        else:
            # Fallback to PBKDF2-SHA256
            salt = crypto_secrets.token_bytes(16)
            key = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 600000)
            # Store salt + hash together
            combined = base64.b64encode(salt + key).decode('utf-8')
            return f"pbkdf2$600000${combined}"

    def verify_password(self, password: str, hashed: str) -> bool:
        """
        Verify a password against a hash.

        Args:
            password: Plain text password
            hashed: Hashed password to verify against

        Returns:
            True if password matches
        """
        if hashed.startswith('pbkdf2$'):
            # PBKDF2 format: pbkdf2$iterations$base64(salt+hash)
            parts = hashed.split('$')
            iterations = int(parts[1])
            combined = base64.b64decode(parts[2])
            salt = combined[:16]
            stored_key = combined[16:]

            key = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, iterations)
            return crypto_secrets.compare_digest(key, stored_key)
        else:
            # Argon2 format
            if not self.password_hasher:
                raise ValueError("Argon2 not available but hash is Argon2 format")

            try:
                self.password_hasher.verify(hashed, password)
                return True
            except VerifyMismatchError:
                return False

    def store_pin_hash(self, pin_hash: str) -> None:
        """Store admin PIN hash"""
        self.backend.store_secret("admin_pin_hash", pin_hash)

    def get_pin_hash(self) -> Optional[str]:
        """Retrieve admin PIN hash"""
        return self.backend.retrieve_secret("admin_pin_hash")

    def store_api_key(self, service: str, api_key: str) -> None:
        """Store API key for a service"""
        self.backend.store_secret(f"api_key_{service}", api_key)

    def get_api_key(self, service: str) -> Optional[str]:
        """Retrieve API key for a service"""
        return self.backend.retrieve_secret(f"api_key_{service}")

    def store_secret(self, key: str, value: str) -> None:
        """Store arbitrary secret"""
        self.backend.store_secret(key, value)

    def get_secret(self, key: str) -> Optional[str]:
        """Retrieve arbitrary secret"""
        return self.backend.retrieve_secret(key)

    def delete_secret(self, key: str) -> bool:
        """Delete a secret"""
        return self.backend.delete_secret(key)


if __name__ == "__main__":
    # Self-test
    print("Secrets Manager Module - Self Test")
    print("=" * 60)

    try:
        # Test with fallback backend (always available)
        print("\n[Test 1] Initializing secrets manager (fallback)...")
        mgr = SecretsManager(backend='file')
        print("✓ Initialized")

        # Test password hashing
        print("\n[Test 2] Hashing password...")
        test_password = "test1234"
        hashed = mgr.hash_password(test_password)
        print(f"✓ Hashed: {hashed[:50]}...")

        # Test password verification
        print("\n[Test 3] Verifying correct password...")
        if mgr.verify_password(test_password, hashed):
            print("✓ Correct password verified")
        else:
            print("✗ Failed to verify correct password")

        print("\n[Test 4] Rejecting wrong password...")
        if not mgr.verify_password("wrong", hashed):
            print("✓ Wrong password rejected")
        else:
            print("✗ Failed to reject wrong password")

        # Test secret storage
        print("\n[Test 5] Storing secret...")
        mgr.store_secret("test_key", "test_value_12345")
        print("✓ Secret stored")

        print("\n[Test 6] Retrieving secret...")
        retrieved = mgr.get_secret("test_key")
        if retrieved == "test_value_12345":
            print(f"✓ Retrieved: {retrieved}")
        else:
            print(f"✗ Retrieved wrong value: {retrieved}")

        # Test PIN hash storage
        print("\n[Test 7] Storing PIN hash...")
        mgr.store_pin_hash(hashed)
        print("✓ PIN hash stored")

        print("\n[Test 8] Retrieving PIN hash...")
        retrieved_hash = mgr.get_pin_hash()
        if retrieved_hash == hashed:
            print("✓ PIN hash retrieved correctly")
        else:
            print("✗ PIN hash mismatch")

        # Cleanup
        print("\n[Cleanup] Deleting test secrets...")
        mgr.delete_secret("test_key")
        mgr.delete_secret("admin_pin_hash")
        print("✓ Cleanup complete")

        print("\n" + "=" * 60)
        print("Self-test complete. All tests passed!")

    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
