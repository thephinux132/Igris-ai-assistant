"""
Secure Authentication Module

Provides real authentication with strong security:
- Argon2id password hashing (not SHA256)
- Rate limiting and lockout
- Audit logging
- Windows Hello API integration
- Hardware Security Key (FIDO2) integration

Replaces simulated authentication (fake fingerprint/voice).
"""

import time
import logging
import getpass
from datetime import datetime, timedelta
from typing import Optional, Dict
from pathlib import Path

# Phase 5: Windows Hello integration
try:
    from core.windows_hello import WindowsHelloAuth, is_windows_hello_available
    WINDOWS_HELLO_AVAILABLE = True
except ImportError:
    WINDOWS_HELLO_AVAILABLE = False

# Phase 5: Hardware Key integration
try:
    from core.hardware_key import HardwareKeyManager, is_available as hw_key_available
    HARDWARE_KEY_AVAILABLE = True
except ImportError:
    HARDWARE_KEY_AVAILABLE = False

# Local imports
try:
    from core.secrets_manager import SecretsManager, SecretStorageError
except ImportError:
    # Allow running standalone for testing
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from core.secrets_manager import SecretsManager, SecretStorageError


# Configure logging
logging.basicConfig(level=logging.INFO)
auth_logger = logging.getLogger('igris.security.auth')


class AuthenticationError(Exception):
    """Raised when authentication fails"""
    pass


class RateLimitError(AuthenticationError):
    """Raised when rate limit is exceeded"""
    pass


class AuthenticationManager:
    """
    Manages user authentication with security features.

    Features:
    - Argon2id password hashing
    - Rate limiting (configurable attempts and cooldown)
    - Account lockout
    - Audit logging
    - Windows Hello integration
    - Hardware Key (FIDO2) integration
    """

    def __init__(
        self,
        max_attempts: int = 5,
        cooldown_minutes: int = 5,
        secrets_manager: Optional[SecretsManager] = None
    ):
        """
        Initialize authentication manager.

        Args:
            max_attempts: Maximum failed attempts before lockout (default: 5)
            cooldown_minutes: Lockout duration in minutes (default: 5)
            secrets_manager: SecretsManager instance (creates new if None)
        """
        self.max_attempts = max_attempts
        self.cooldown_duration = timedelta(minutes=cooldown_minutes)
        self.secrets_mgr = secrets_manager or SecretsManager()

        # Track failed attempts (in-memory, resets on restart)
        self.failed_attempts: Dict[str, int] = {}
        self.lockout_until: Dict[str, datetime] = {}

        auth_logger.info(
            f"AuthenticationManager initialized: "
            f"max_attempts={max_attempts}, cooldown={cooldown_minutes}min"
        )

    def _check_rate_limit(self, identifier: str = "default") -> None:
        """
        Check if rate limit has been exceeded.

        Args:
            identifier: Unique identifier for rate limiting (e.g., username)

        Raises:
            RateLimitError: If currently locked out
        """
        if identifier in self.lockout_until:
            unlock_time = self.lockout_until[identifier]
            if datetime.now() < unlock_time:
                remaining = (unlock_time - datetime.now()).seconds
                raise RateLimitError(
                    f"Account locked. Try again in {remaining} seconds."
                )
            else:
                # Lockout expired, reset
                del self.lockout_until[identifier]
                self.failed_attempts[identifier] = 0
                auth_logger.info(f"Lockout expired for {identifier}")

    def _record_failed_attempt(self, identifier: str = "default") -> None:
        """
        Record a failed authentication attempt.

        Args:
            identifier: Unique identifier for rate limiting
        """
        self.failed_attempts[identifier] = self.failed_attempts.get(identifier, 0) + 1

        if self.failed_attempts[identifier] >= self.max_attempts:
            # Lock out the account
            self.lockout_until[identifier] = datetime.now() + self.cooldown_duration
            auth_logger.warning(
                f"Account {identifier} locked after {self.max_attempts} failed attempts. "
                f"Unlock at {self.lockout_until[identifier]}"
            )

    def _reset_failed_attempts(self, identifier: str = "default") -> None:
        """Reset failed attempts after successful auth"""
        if identifier in self.failed_attempts:
            del self.failed_attempts[identifier]
        if identifier in self.lockout_until:
            del self.lockout_until[identifier]

    def is_pin_configured(self) -> bool:
        """
        Check if admin PIN is configured.

        Returns:
            True if PIN hash exists in storage
        """
        pin_hash = self.secrets_mgr.get_pin_hash()
        return pin_hash is not None

    def setup_pin(self, pin: str) -> None:
        """
        Set up admin PIN for first time.

        Args:
            pin: Plain text PIN to hash and store

        Raises:
            ValueError: If PIN doesn't meet requirements
        """
        # Validate PIN requirements
        if not pin:
            raise ValueError("PIN cannot be empty")

        if len(pin) < 4:
            raise ValueError("PIN must be at least 4 characters")

        if len(pin) > 32:
            raise ValueError("PIN must be at most 32 characters")

        # Hash and store
        pin_hash = self.secrets_mgr.hash_password(pin)
        self.secrets_mgr.store_pin_hash(pin_hash)

        auth_logger.info("Admin PIN configured successfully")

    def change_pin(self, old_pin: str, new_pin: str) -> bool:
        """
        Change admin PIN (requires old PIN for verification).

        Args:
            old_pin: Current PIN
            new_pin: New PIN to set

        Returns:
            True if changed successfully

        Raises:
            AuthenticationError: If old PIN is incorrect
            ValueError: If new PIN doesn't meet requirements
        """
        # Verify old PIN
        if not self.verify_pin(old_pin):
            raise AuthenticationError("Current PIN is incorrect")

        # Set new PIN
        self.setup_pin(new_pin)
        auth_logger.info("Admin PIN changed successfully")
        return True

    def verify_pin(self, pin: str, identifier: str = "admin") -> bool:
        """
        Verify admin PIN without rate limiting (internal use).

        Args:
            pin: PIN to verify
            identifier: User identifier for logging

        Returns:
            True if PIN matches
        """
        pin_hash = self.secrets_mgr.get_pin_hash()
        if not pin_hash:
            auth_logger.error("No PIN configured")
            return False

        try:
            return self.secrets_mgr.verify_password(pin, pin_hash)
        except Exception as e:
            auth_logger.error(f"PIN verification error: {e}")
            return False

    def authenticate_biometric(self) -> bool:
        """Authenticate using Windows Hello biometrics."""
        if not WINDOWS_HELLO_AVAILABLE:
            return False

        hello = WindowsHelloAuth()
        if not hello.is_available():
            return False

        result = hello.authenticate("Igris requires admin authentication")
        if result:
            self._reset_failed_attempts("windows_hello")
            auth_logger.info("Windows Hello authentication successful")
        else:
            auth_logger.warning("Windows Hello authentication failed")

        return result

    def authenticate_hardware_key(self) -> bool:
        """Authenticate using hardware security key."""
        if not HARDWARE_KEY_AVAILABLE:
            return False

        manager = HardwareKeyManager()
        if not manager.is_available():
            return False

        if not manager.has_registered_keys():
            return False

        result = manager.authenticate()
        if result:
            self._reset_failed_attempts("hardware_key")
            auth_logger.info("Hardware key authentication successful")
        else:
            self._record_failed_attempt("hardware_key") # Corrected from self._record_failure

        return result

    def authenticate_pin(
        self,
        pin: Optional[str] = None,
        identifier: str = "admin",
        prompt: bool = True
    ) -> bool:
        """
        Authenticate user with PIN (with rate limiting).

        Args:
            pin: PIN to verify (prompts if None and prompt=True)
            identifier: User identifier for rate limiting
            prompt: Whether to prompt for PIN if not provided

        Returns:
            True if authenticated successfully

        Raises:
            RateLimitError: If rate limit exceeded
            AuthenticationError: If PIN not configured
        """
        # Check rate limit
        self._check_rate_limit(identifier)

        # Check if PIN is configured
        if not self.is_pin_configured():
            raise AuthenticationError("Admin PIN not configured. Run setup first.")

        # Get PIN if not provided
        if pin is None:
            if not prompt:
                raise ValueError("PIN required but prompt=False")
            pin = self._prompt_for_pin()

        # Verify PIN
        is_valid = self.verify_pin(pin, identifier)

        if is_valid:
            self._reset_failed_attempts(identifier)
            auth_logger.info(f"Authentication successful for {identifier}")
            return True
        else:
            self._record_failed_attempt(identifier)
            remaining = self.max_attempts - self.failed_attempts.get(identifier, 0)

            if remaining > 0:
                auth_logger.warning(
                    f"Authentication failed for {identifier}. "
                    f"{remaining} attempts remaining"
                )
            else:
                auth_logger.warning(f"Authentication failed and account locked: {identifier}")

            return False

    def _prompt_for_pin(self) -> str:
        """
        Prompt user for PIN (masked input).

        Returns:
            PIN entered by user
        """
        return getpass.getpass("🔑 Enter admin PIN: ")

    def authenticate_admin(self, prompt: bool = True) -> bool:
        """
        Authenticate admin user (primary authentication method).

        Attempts Hardware Key -> Windows Hello -> PIN.

        Args:
            prompt: Whether to prompt for PIN

        Returns:
            True if authenticated

        Raises:
            RateLimitError: If rate limited
        """
        # Try Hardware Key first
        if HARDWARE_KEY_AVAILABLE:
            try:
                manager = HardwareKeyManager()
                if manager.is_available() and manager.has_registered_keys():
                    if self.authenticate_hardware_key():
                        return True
            except Exception as e:
                auth_logger.error(f"Hardware key auth error: {e}")

        # Try Windows Hello next
        if WINDOWS_HELLO_AVAILABLE:
            try:
                if self.authenticate_biometric():
                    return True
            except Exception as e:
                auth_logger.error(f"Biometric auth error: {e}")

        # Fall back to PIN
        return self.authenticate_pin(prompt=prompt)

    def get_lockout_status(self, identifier: str = "admin") -> Dict:
        """
        Get current lockout status for an identifier.

        Returns:
            Dict with status information
        """
        if identifier in self.lockout_until:
            unlock_time = self.lockout_until[identifier]
            if datetime.now() < unlock_time:
                remaining_seconds = (unlock_time - datetime.now()).seconds
                return {
                    'locked': True,
                    'unlock_time': unlock_time,
                    'remaining_seconds': remaining_seconds
                }

        failed = self.failed_attempts.get(identifier, 0)
        return {
            'locked': False,
            'failed_attempts': failed,
            'remaining_attempts': self.max_attempts - failed
        }


# Backward compatibility functions

def cli_prompt_for_pin_secure(auth_mgr: Optional[AuthenticationManager] = None) -> bool:
    """
    Backward compatible PIN prompt (secure version).

    Replaces old cli_prompt_for_pin() with secure implementation.
    """
    if auth_mgr is None:
        auth_mgr = AuthenticationManager()

    try:
        return auth_mgr.authenticate_pin()
    except RateLimitError as e:
        print(f"[SECURITY] {e}")
        return False
    except AuthenticationError as e:
        print(f"[SECURITY] {e}")
        return False


def authenticate_admin_secure(prompt: bool = True) -> bool:
    """
    Backward compatible admin authentication (secure version).

    Replaces old authenticate_admin() function.
    """
    auth_mgr = AuthenticationManager()
    try:
        return auth_mgr.authenticate_admin(prompt=prompt)
    except RateLimitError as e:
        print(f"[SECURITY] {e}")
        return False
    except AuthenticationError as e:
        print(f"[SECURITY] {e}")
        return False


if __name__ == "__main__":
    # Self-test
    print("Secure Authentication Module - Self Test")
    print("=" * 60)

    try:
        # Initialize with lenient settings for testing
        print("\n[Test 1] Initializing authentication manager...")
        auth_mgr = AuthenticationManager(max_attempts=3, cooldown_minutes=1)
        print("✓ Initialized")

        # Setup PIN
        print("\n[Test 2] Setting up test PIN...")
        test_pin = "test1234"
        auth_mgr.setup_pin(test_pin)
        print("✓ PIN configured")

        # Verify correct PIN
        print("\n[Test 3] Verifying correct PIN (no prompt)...")
        if auth_mgr.authenticate_pin(pin=test_pin, prompt=False):
            print("✓ Correct PIN accepted")
        else:
            print("✗ Correct PIN rejected")

        # Verify wrong PIN
        print("\n[Test 4] Testing wrong PIN...")
        if not auth_mgr.authenticate_pin(pin="wrong", prompt=False):
            print("✓ Wrong PIN rejected")
        else:
            print("✗ Wrong PIN accepted")

        # Test rate limiting
        print("\n[Test 5] Testing rate limiting (3 failures)...")
        for i in range(3):
            auth_mgr.authenticate_pin(pin="wrong", prompt=False)
            print(f"  Attempt {i+1} failed (expected)")

        print("\n[Test 6] Attempting after lockout...")
        try:
            auth_mgr.authenticate_pin(pin=test_pin, prompt=False)
            print("✗ Should have been rate limited")
        except RateLimitError as e:
            print(f"✓ Rate limited correctly: {e}")

        # Check lockout status
        print("\n[Test 7] Checking lockout status...")
        status = auth_mgr.get_lockout_status()
        if status['locked']:
            print(f"✓ Account locked for {status['remaining_seconds']}s")
        else:
            print("✗ Account should be locked")

        # Test PIN change
        print("\n[Test 8] Testing PIN change (after cooldown expires)...")
        print("  Waiting for lockout to expire...")
        time.sleep(61)  # Wait for 1-minute cooldown

        try:
            auth_mgr.change_pin(test_pin, "newpin5678")
            print("✓ PIN changed successfully")
        except Exception as e:
            print(f"✗ PIN change failed: {e}")

        # Cleanup
        print("\n[Cleanup] Removing test secrets...")
        auth_mgr.secrets_mgr.delete_secret("admin_pin_hash")
        print("✓ Cleanup complete")

        print("\n" + "=" * 60)
        print("Self-test complete (Note: Test 8 skipped cooldown wait)")

    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()