#!/usr/bin/env python3
"""
Linux Platform Support for Igris
Provides Linux-specific implementations and integrations.
"""

import os
import sys
import logging
import subprocess
import shutil
from pathlib import Path
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

# Check if running on Linux
IS_LINUX = sys.platform.startswith('linux')

class LinuxSecretStorage:
    """
    Linux secret storage using libsecret/Secret Service API.
    Falls back to encrypted file if unavailable.
    """

    def __init__(self, service_name: str = "igris"):
        self.service_name = service_name
        self.backend = self._detect_backend()

    def _detect_backend(self) -> str:
        """Detect available secret storage backend."""
        # Try libsecret (GNOME Keyring, KWallet)
        try:
            import secretstorage
            bus = secretstorage.dbus_init()
            collection = secretstorage.get_default_collection(bus)
            if collection.is_locked():
                collection.unlock()
            return "secretstorage"
        except Exception:
            pass

        # Try keyring
        try:
            import keyring
            keyring.get_keyring()
            return "keyring"
        except Exception:
            pass

        # Fallback to encrypted file
        return "file"

    def store(self, key: str, value: str) -> bool:
        """Store a secret."""
        try:
            if self.backend == "secretstorage":
                import secretstorage
                bus = secretstorage.dbus_init()
                collection = secretstorage.get_default_collection(bus)
                if collection.is_locked():
                    collection.unlock()

                attributes = {"application": self.service_name, "key": key}
                collection.create_item(
                    f"{self.service_name}:{key}",
                    attributes,
                    value.encode(),
                    replace=True
                )
                return True

            elif self.backend == "keyring":
                import keyring
                keyring.set_password(self.service_name, key, value)
                return True

            else:
                return self._store_file(key, value)

        except Exception as e:
            logger.error(f"Failed to store secret: {e}")
            return False

    def retrieve(self, key: str) -> Optional[str]:
        """Retrieve a secret."""
        try:
            if self.backend == "secretstorage":
                import secretstorage
                bus = secretstorage.dbus_init()
                collection = secretstorage.get_default_collection(bus)
                if collection.is_locked():
                    collection.unlock()

                for item in collection.get_all_items():
                    attrs = item.get_attributes()
                    if attrs.get("application") == self.service_name and attrs.get("key") == key:
                        return item.get_secret().decode()
                return None

            elif self.backend == "keyring":
                import keyring
                return keyring.get_password(self.service_name, key)

            else:
                return self._retrieve_file(key)

        except Exception as e:
            logger.error(f"Failed to retrieve secret: {e}")
            return None

    def _store_file(self, key: str, value: str) -> bool:
        """Store secret in encrypted file."""
        secrets_dir = Path.home() / ".config" / "igris" / "secrets"
        secrets_dir.mkdir(parents=True, exist_ok=True, mode=0o700)

        secret_file = secrets_dir / f"{key}.enc"

        try:
            from cryptography.fernet import Fernet

            # Get or create encryption key
            key_file = secrets_dir / ".key"
            if key_file.exists():
                fernet_key = key_file.read_bytes()
            else:
                fernet_key = Fernet.generate_key()
                key_file.write_bytes(fernet_key)
                key_file.chmod(0o600)

            fernet = Fernet(fernet_key)
            encrypted = fernet.encrypt(value.encode())
            secret_file.write_bytes(encrypted)
            secret_file.chmod(0o600)
            return True
        except Exception as e:
            logger.error(f"File storage failed: {e}")
            return False

    def _retrieve_file(self, key: str) -> Optional[str]:
        """Retrieve secret from encrypted file."""
        secrets_dir = Path.home() / ".config" / "igris" / "secrets"
        secret_file = secrets_dir / f"{key}.enc"
        key_file = secrets_dir / ".key"

        if not secret_file.exists() or not key_file.exists():
            return None

        try:
            from cryptography.fernet import Fernet

            fernet_key = key_file.read_bytes()
            fernet = Fernet(fernet_key)
            encrypted = secret_file.read_bytes()
            return fernet.decrypt(encrypted).decode()
        except Exception as e:
            logger.error(f"File retrieval failed: {e}")
            return None


class LinuxSystemInfo:
    """Linux system information and control."""

    @staticmethod
    def get_distro() -> Dict[str, str]:
        """Get Linux distribution info."""
        info = {"name": "Linux", "version": "", "id": "linux"}

        # Try /etc/os-release
        os_release = Path("/etc/os-release")
        if os_release.exists():
            for line in os_release.read_text().splitlines():
                if "=" in line:
                    key, value = line.split("=", 1)
                    value = value.strip('"')
                    if key == "NAME":
                        info["name"] = value
                    elif key == "VERSION_ID":
                        info["version"] = value
                    elif key == "ID":
                        info["id"] = value

        return info

    @staticmethod
    def get_desktop_environment() -> str:
        """Detect current desktop environment."""
        desktop = os.environ.get("XDG_CURRENT_DESKTOP", "")
        session = os.environ.get("DESKTOP_SESSION", "")

        if "GNOME" in desktop or "gnome" in session:
            return "gnome"
        elif "KDE" in desktop or "plasma" in session:
            return "kde"
        elif "XFCE" in desktop or "xfce" in session:
            return "xfce"
        elif "MATE" in desktop:
            return "mate"
        elif "Cinnamon" in desktop:
            return "cinnamon"

        return desktop.lower() or session.lower() or "unknown"

    @staticmethod
    def is_wayland() -> bool:
        """Check if running under Wayland."""
        return "WAYLAND_DISPLAY" in os.environ

    @staticmethod
    def lock_screen() -> bool:
        """Lock the screen."""
        de = LinuxSystemInfo.get_desktop_environment()

        commands = {
            "gnome": ["gnome-screensaver-command", "-l"],
            "kde": ["qdbus", "org.freedesktop.ScreenSaver", "/ScreenSaver", "Lock"],
            "xfce": ["xflock4"],
            "mate": ["mate-screensaver-command", "-l"],
            "cinnamon": ["cinnamon-screensaver-command", "-l"],
        }

        # Try DE-specific command
        if de in commands:
            try:
                subprocess.run(commands[de], check=True, capture_output=True)
                return True
            except Exception:
                pass

        # Fallback to loginctl
        try:
            subprocess.run(["loginctl", "lock-session"], check=True, capture_output=True)
            return True
        except Exception:
            pass

        # Fallback to xdg-screensaver
        try:
            subprocess.run(["xdg-screensaver", "lock"], check=True, capture_output=True)
            return True
        except Exception:
            pass

        return False

    @staticmethod
    def send_notification(title: str, message: str, icon: str = "dialog-information") -> bool:
        """Send desktop notification."""
        try:
            subprocess.run([
                "notify-send",
                "--app-name=Igris",
                f"--icon={icon}",
                title,
                message
            ], check=True, capture_output=True)
            return True
        except Exception:
            return False


class SystemdManager:
    """Manage Igris systemd service."""

    SERVICE_NAME = "igris"
    USER_SERVICE_PATH = Path.home() / ".config" / "systemd" / "user"
    SYSTEM_SERVICE_PATH = Path("/etc/systemd/system")

    def __init__(self, user_mode: bool = True):
        self.user_mode = user_mode
        self.service_path = self.USER_SERVICE_PATH if user_mode else self.SYSTEM_SERVICE_PATH

    def _systemctl(self, *args) -> subprocess.CompletedProcess:
        """Run systemctl command."""
        cmd = ["systemctl"]
        if self.user_mode:
            cmd.append("--user")
        cmd.extend(args)
        return subprocess.run(cmd, capture_output=True, text=True)

    def install(self, service_content: str) -> bool:
        """Install the systemd service."""
        try:
            self.service_path.mkdir(parents=True, exist_ok=True)
            service_file = self.service_path / f"{self.SERVICE_NAME}.service"
            service_file.write_text(service_content)

            # Reload systemd
            self._systemctl("daemon-reload")
            logger.info(f"Service installed: {service_file}")
            return True
        except Exception as e:
            logger.error(f"Failed to install service: {e}")
            return False

    def uninstall(self) -> bool:
        """Uninstall the systemd service."""
        try:
            self.stop()
            self.disable()

            service_file = self.service_path / f"{self.SERVICE_NAME}.service"
            if service_file.exists():
                service_file.unlink()

            self._systemctl("daemon-reload")
            return True
        except Exception as e:
            logger.error(f"Failed to uninstall service: {e}")
            return False

    def start(self) -> bool:
        """Start the service."""
        result = self._systemctl("start", self.SERVICE_NAME)
        return result.returncode == 0

    def stop(self) -> bool:
        """Stop the service."""
        result = self._systemctl("stop", self.SERVICE_NAME)
        return result.returncode == 0

    def restart(self) -> bool:
        """Restart the service."""
        result = self._systemctl("restart", self.SERVICE_NAME)
        return result.returncode == 0

    def enable(self) -> bool:
        """Enable service to start on boot."""
        result = self._systemctl("enable", self.SERVICE_NAME)
        return result.returncode == 0

    def disable(self) -> bool:
        """Disable service from starting on boot."""
        result = self._systemctl("disable", self.SERVICE_NAME)
        return result.returncode == 0

    def status(self) -> Dict[str, Any]:
        """Get service status."""
        result = self._systemctl("status", self.SERVICE_NAME)

        is_active = self._systemctl("is-active", self.SERVICE_NAME)
        is_enabled = self._systemctl("is-enabled", self.SERVICE_NAME)

        return {
            "active": is_active.stdout.strip() == "active",
            "enabled": is_enabled.stdout.strip() == "enabled",
            "status_output": result.stdout
        }

    def logs(self, lines: int = 50) -> str:
        """Get service logs."""
        cmd = ["journalctl"]
        if self.user_mode:
            cmd.append("--user")
        cmd.extend(["-u", self.SERVICE_NAME, "-n", str(lines), "--no-pager"])

        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.stdout


# Platform detection and factory
def get_secret_storage():
    """Get platform-appropriate secret storage."""
    if IS_LINUX:
        return LinuxSecretStorage()
    return None

def get_system_info():
    """Get platform-appropriate system info."""
    if IS_LINUX:
        return LinuxSystemInfo()
    return None


# Self-test
if __name__ == "__main__":
    print("Linux Platform Support Test")
    print("=" * 50)
    print(f"Is Linux: {IS_LINUX}")

    if not IS_LINUX:
        print("Not running on Linux - skipping tests")
        sys.exit(0)

    # System info
    info = LinuxSystemInfo()
    distro = info.get_distro()
    print(f"\nDistro: {distro['name']} {distro['version']}")
    print(f"Desktop: {info.get_desktop_environment()}")
    print(f"Wayland: {info.is_wayland()}")

    # Secret storage
    print("\nSecret Storage Test:")
    storage = LinuxSecretStorage()
    print(f"Backend: {storage.backend}")

    test_key = "igris_test_key"
    test_value = "test_secret_value"

    if storage.store(test_key, test_value):
        print(f"  ✓ Stored secret")
        retrieved = storage.retrieve(test_key)
        if retrieved == test_value:
            print(f"  ✓ Retrieved secret correctly")
        else:
            print(f"  ✗ Retrieved value mismatch")
    else:
        print(f"  ✗ Failed to store secret")

    # Systemd (if running as user)
    print("\nSystemd Status:")
    systemd = SystemdManager(user_mode=True)
    status = systemd.status()
    print(f"  Service active: {status['active']}")
    print(f"  Service enabled: {status['enabled']}")
