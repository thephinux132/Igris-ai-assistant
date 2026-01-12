#!/usr/bin/env python3
"""
macOS Platform Support for Igris
Provides macOS-specific implementations including Keychain and Touch ID.
"""

import os
import sys
import logging
import subprocess
import ctypes
from pathlib import Path
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# Check if running on macOS
IS_MACOS = sys.platform == "darwin"

# LocalAuthentication framework for Touch ID
LA_AVAILABLE = False
if IS_MACOS:
    try:
        from Foundation import NSBundle
        from LocalAuthentication import LAContext, LAPolicyDeviceOwnerAuthenticationWithBiometrics
        LA_AVAILABLE = True
    except ImportError:
        logger.info("LocalAuthentication not available - install pyobjc-framework-LocalAuthentication")


class KeychainStorage:
    """
    macOS Keychain secret storage.
    Uses security command-line tool or keyring library.
    """

    def __init__(self, service_name: str = "igris"):
        self.service_name = service_name
        self.backend = self._detect_backend()

    def _detect_backend(self) -> str:
        """Detect available backend."""
        # Try keyring first (cleaner API)
        try:
            import keyring
            keyring.get_keyring()
            return "keyring"
        except Exception:
            pass

        # Fall back to security command
        if IS_MACOS:
            return "security"

        return "file"

    def store(self, key: str, value: str) -> bool:
        """Store a secret in Keychain."""
        try:
            if self.backend == "keyring":
                import keyring
                keyring.set_password(self.service_name, key, value)
                return True

            elif self.backend == "security":
                # Delete existing (ignore error if not found)
                subprocess.run([
                    "security", "delete-generic-password",
                    "-s", self.service_name,
                    "-a", key
                ], capture_output=True)

                # Add new
                result = subprocess.run([
                    "security", "add-generic-password",
                    "-s", self.service_name,
                    "-a", key,
                    "-w", value,
                    "-U"  # Update if exists
                ], capture_output=True)
                return result.returncode == 0

            else:
                return self._store_file(key, value)

        except Exception as e:
            logger.error(f"Failed to store secret: {e}")
            return False

    def retrieve(self, key: str) -> Optional[str]:
        """Retrieve a secret from Keychain."""
        try:
            if self.backend == "keyring":
                import keyring
                return keyring.get_password(self.service_name, key)

            elif self.backend == "security":
                result = subprocess.run([
                    "security", "find-generic-password",
                    "-s", self.service_name,
                    "-a", key,
                    "-w"  # Output password only
                ], capture_output=True, text=True)

                if result.returncode == 0:
                    return result.stdout.strip()
                return None

            else:
                return self._retrieve_file(key)

        except Exception as e:
            logger.error(f"Failed to retrieve secret: {e}")
            return None

    def delete(self, key: str) -> bool:
        """Delete a secret from Keychain."""
        try:
            if self.backend == "keyring":
                import keyring
                keyring.delete_password(self.service_name, key)
                return True

            elif self.backend == "security":
                result = subprocess.run([
                    "security", "delete-generic-password",
                    "-s", self.service_name,
                    "-a", key
                ], capture_output=True)
                return result.returncode == 0

            return False
        except Exception as e:
            logger.error(f"Failed to delete secret: {e}")
            return False

    def _store_file(self, key: str, value: str) -> bool:
        """Fallback file storage."""
        secrets_dir = Path.home() / ".config" / "igris" / "secrets"
        secrets_dir.mkdir(parents=True, exist_ok=True, mode=0o700)

        try:
            from cryptography.fernet import Fernet

            key_file = secrets_dir / ".key"
            if key_file.exists():
                fernet_key = key_file.read_bytes()
            else:
                fernet_key = Fernet.generate_key()
                key_file.write_bytes(fernet_key)
                os.chmod(key_file, 0o600)

            fernet = Fernet(fernet_key)
            secret_file = secrets_dir / f"{key}.enc"
            secret_file.write_bytes(fernet.encrypt(value.encode()))
            os.chmod(secret_file, 0o600)
            return True
        except Exception as e:
            logger.error(f"File storage failed: {e}")
            return False

    def _retrieve_file(self, key: str) -> Optional[str]:
        """Fallback file retrieval."""
        secrets_dir = Path.home() / ".config" / "igris" / "secrets"
        secret_file = secrets_dir / f"{key}.enc"
        key_file = secrets_dir / ".key"

        if not secret_file.exists() or not key_file.exists():
            return None

        try:
            from cryptography.fernet import Fernet
            fernet = Fernet(key_file.read_bytes())
            return fernet.decrypt(secret_file.read_bytes()).decode()
        except Exception:
            return None


class TouchIDAuth:
    """
    Touch ID authentication for macOS.
    Uses LocalAuthentication framework.
    """

    def __init__(self):
        self.available = LA_AVAILABLE and self._check_availability()

    def _check_availability(self) -> bool:
        """Check if Touch ID is available."""
        if not LA_AVAILABLE:
            return False

        try:
            context = LAContext.alloc().init()
            error = None
            can_evaluate = context.canEvaluatePolicy_error_(
                LAPolicyDeviceOwnerAuthenticationWithBiometrics,
                None
            )
            return can_evaluate
        except Exception as e:
            logger.error(f"Touch ID check failed: {e}")
            return False

    def is_available(self) -> bool:
        """Check if Touch ID can be used."""
        return self.available

    def authenticate(self, reason: str = "Igris requires authentication") -> bool:
        """
        Authenticate using Touch ID.

        Args:
            reason: Reason shown to user

        Returns:
            True if authentication successful
        """
        if not self.available:
            return False

        try:
            context = LAContext.alloc().init()

            # Evaluate policy synchronously
            success = [False]
            error_msg = [None]
            done = [False]

            def callback(success_result, error):
                success[0] = success_result
                if error:
                    error_msg[0] = str(error)
                done[0] = True

            context.evaluatePolicy_localizedReason_reply_(
                LAPolicyDeviceOwnerAuthenticationWithBiometrics,
                reason,
                callback
            )

            # Wait for callback (with timeout)
            import time
            timeout = 30
            start = time.time()
            while not done[0] and (time.time() - start) < timeout:
                time.sleep(0.1)

            if success[0]:
                logger.info("Touch ID authentication successful")
                return True
            else:
                logger.warning(f"Touch ID authentication failed: {error_msg[0]}")
                return False

        except Exception as e:
            logger.error(f"Touch ID error: {e}")
            return False


class MacOSSystemInfo:
    """macOS system information and control."""

    @staticmethod
    def get_macos_version() -> Dict[str, str]:
        """Get macOS version info."""
        try:
            result = subprocess.run(
                ["sw_vers"],
                capture_output=True,
                text=True
            )

            info = {}
            for line in result.stdout.splitlines():
                if ":" in line:
                    key, value = line.split(":", 1)
                    info[key.strip()] = value.strip()

            return {
                "name": info.get("ProductName", "macOS"),
                "version": info.get("ProductVersion", ""),
                "build": info.get("BuildVersion", "")
            }
        except Exception:
            return {"name": "macOS", "version": "", "build": ""}

    @staticmethod
    def lock_screen() -> bool:
        """Lock the screen."""
        try:
            # Use pmset to lock
            subprocess.run([
                "/System/Library/CoreServices/Menu Extras/User.menu/Contents/Resources/CGSession",
                "-suspend"
            ], check=True, capture_output=True)
            return True
        except Exception:
            pass

        # Alternative using AppleScript
        try:
            subprocess.run([
                "osascript",
                "-e",
                'tell application "System Events" to keystroke "q" using {control down, command down}'
            ], check=True, capture_output=True)
            return True
        except Exception:
            return False

    @staticmethod
    def send_notification(title: str, message: str, sound: bool = True) -> bool:
        """Send macOS notification."""
        try:
            script = f'''
            display notification "{message}" with title "{title}"
            '''
            if sound:
                script += ' sound name "default"'

            subprocess.run([
                "osascript", "-e", script
            ], check=True, capture_output=True)
            return True
        except Exception:
            return False

    @staticmethod
    def get_battery_status() -> Dict[str, Any]:
        """Get battery status."""
        try:
            result = subprocess.run(
                ["pmset", "-g", "batt"],
                capture_output=True,
                text=True
            )

            # Parse output
            output = result.stdout
            status = {
                "present": "Battery" in output or "InternalBattery" in output,
                "charging": "charging" in output.lower(),
                "percent": None
            }

            # Extract percentage
            import re
            match = re.search(r'(\d+)%', output)
            if match:
                status["percent"] = int(match.group(1))

            return status
        except Exception:
            return {"present": False}


class LaunchdManager:
    """Manage Igris launchd service."""

    PLIST_NAME = "com.igris.assistant"
    USER_AGENTS_PATH = Path.home() / "Library" / "LaunchAgents"

    def __init__(self):
        self.plist_path = self.USER_AGENTS_PATH / f"{self.PLIST_NAME}.plist"

    def _launchctl(self, *args) -> subprocess.CompletedProcess:
        """Run launchctl command."""
        return subprocess.run(["launchctl"] + list(args), capture_output=True, text=True)

    def install(self, plist_content: str) -> bool:
        """Install the launchd service."""
        try:
            self.USER_AGENTS_PATH.mkdir(parents=True, exist_ok=True)
            self.plist_path.write_text(plist_content)
            logger.info(f"Service installed: {self.plist_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to install service: {e}")
            return False

    def uninstall(self) -> bool:
        """Uninstall the launchd service."""
        try:
            self.stop()
            if self.plist_path.exists():
                self.plist_path.unlink()
            return True
        except Exception as e:
            logger.error(f"Failed to uninstall service: {e}")
            return False

    def load(self) -> bool:
        """Load the service."""
        result = self._launchctl("load", str(self.plist_path))
        return result.returncode == 0

    def unload(self) -> bool:
        """Unload the service."""
        result = self._launchctl("unload", str(self.plist_path))
        return result.returncode == 0

    def start(self) -> bool:
        """Start the service."""
        result = self._launchctl("start", self.PLIST_NAME)
        return result.returncode == 0

    def stop(self) -> bool:
        """Stop the service."""
        result = self._launchctl("stop", self.PLIST_NAME)
        return result.returncode == 0

    def status(self) -> Dict[str, Any]:
        """Get service status."""
        result = self._launchctl("list", self.PLIST_NAME)

        running = result.returncode == 0 and self.PLIST_NAME in result.stdout

        return {
            "installed": self.plist_path.exists(),
            "running": running,
            "output": result.stdout + result.stderr
        }


# Platform detection
def get_secret_storage():
    """Get platform-appropriate secret storage."""
    if IS_MACOS:
        return KeychainStorage()
    return None

def get_touchid_auth():
    """Get Touch ID authenticator."""
    if IS_MACOS:
        return TouchIDAuth()
    return None


# Self-test
if __name__ == "__main__":
    print("macOS Platform Support Test")
    print("=" * 50)
    print(f"Is macOS: {IS_MACOS}")
    print(f"LocalAuthentication available: {LA_AVAILABLE}")

    if not IS_MACOS:
        print("Not running on macOS - skipping tests")
        sys.exit(0)

    # System info
    info = MacOSSystemInfo()
    version = info.get_macos_version()
    print(f"\nmacOS: {version['name']} {version['version']} ({version['build']})")

    battery = info.get_battery_status()
    print(f"Battery: {battery.get('percent', 'N/A')}%\n")

    # Keychain
    print("Keychain Storage Test:")
    keychain = KeychainStorage()
    print(f"Backend: {keychain.backend}")

    test_key = "igris_test"
    test_value = "test_secret"

    if keychain.store(test_key, test_value):
        print("  ✓ Stored secret")
        retrieved = keychain.retrieve(test_key)
        if retrieved == test_value:
            print("  ✓ Retrieved correctly")
            keychain.delete(test_key)
            print("  ✓ Deleted")
        else:
            print("  ✗ Retrieval mismatch")
    else:
        print("  ✗ Storage failed")

    # Touch ID
    print("\nTouch ID Test:")
    touchid = TouchIDAuth()
    print(f"Available: {touchid.is_available()}")

    if touchid.is_available():
        print("Requesting Touch ID authentication...")
        result = touchid.authenticate("Test authentication for Igris")
        print(f"Result: {'SUCCESS' if result else 'FAILED'}")

    # Launchd
    print("\nLaunchd Service:")
    launchd = LaunchdManager()
    status = launchd.status()
    print(f"Installed: {status['installed']}")
    print(f"Running: {status['running']}")
