#!/usr/bin/env python3
"""
Hardware Security Key (FIDO2/WebAuthn) Module for Igris
Supports YubiKey, Titan, and other FIDO2 authenticators.
"""

import json
import logging
import secrets
import hashlib
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict
import threading

logger = logging.getLogger(__name__)

# Optional dependencies
FIDO2_AVAILABLE = False
try:
    from fido2.hid import CtapHidDevice
    from fido2.client import Fido2Client, UserInteraction
    from fido2.server import Fido2Server
    from fido2.webauthn import (
        PublicKeyCredentialRpEntity,
        PublicKeyCredentialUserEntity,
        PublicKeyCredentialParameters,
        PublicKeyCredentialType,
        PublicKeyCredentialDescriptor,
        AuthenticatorSelectionCriteria,
        UserVerificationRequirement,
        ResidentKeyRequirement,
        AuthenticatorAttachment,
    )
    from fido2 import cbor
    FIDO2_AVAILABLE = True
except ImportError:
    logger.info("fido2 library not available - install with: pip install fido2")

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

@dataclass
class StoredCredential:
    credential_id: bytes
    public_key: bytes
    sign_count: int
    user_id: str
    created: float
    name: str = "Hardware Key"

    def to_dict(self) -> dict:
        return {
            "credential_id": self.credential_id.hex(),
            "public_key": self.public_key.hex(),
            "sign_count": self.sign_count,
            "user_id": self.user_id,
            "created": self.created,
            "name": self.name
        }

    @classmethod
    def from_dict(cls, data: dict) -> "StoredCredential":
        return cls(
            credential_id=bytes.fromhex(data["credential_id"]),
            public_key=bytes.fromhex(data["public_key"]),
            sign_count=data["sign_count"],
            user_id=data["user_id"],
            created=data["created"],
            name=data.get("name", "Hardware Key")
        )

class CliInteraction(UserInteraction):
    """CLI-based user interaction for FIDO2."""

    def prompt_up(self):
        """Prompt user to touch the security key."""
        print("\n🔑 Touch your security key...")

    def request_pin(self, permissions, rd_id):
        """Request PIN from user."""
        import getpass
        return getpass.getpass("Enter security key PIN: ")

    def request_uv(self, permissions, rd_id):
        """Request user verification."""
        print("Perform user verification on your security key...")
        return True

class HardwareKeyManager:
    """Manages FIDO2 hardware key authentication."""

    def __init__(self, config_path: Optional[Path] = None):
        self.available = FIDO2_AVAILABLE
        self.config_path = config_path or Path(__file__).parent.parent / "config" / "fido2_config.yaml"
        self.config = self._load_config()
        self.credentials_path = Path(
            self.config.get("credentials_path", "config/.fido2_credentials")
        )
        self.credentials: List[StoredCredential] = []
        self.lock = threading.Lock()
        self._load_credentials()

        if self.available:
            self._init_server()

    def _load_config(self) -> dict:
        """Load FIDO2 configuration."""
        if YAML_AVAILABLE and self.config_path.exists():
            try:
                return yaml.safe_load(self.config_path.read_text())
            except Exception as e:
                logger.error(f"Failed to load FIDO2 config: {e}")

        return {
            "relying_party": {"id": "igris.local", "name": "Igris AI Assistant"},
            "authenticator": {"user_verification": "preferred"},
            "timeout": 60000
        }

    def _init_server(self):
        """Initialize FIDO2 server."""
        rp_config = self.config.get("relying_party", {})
        self.rp = PublicKeyCredentialRpEntity(
            id=rp_config.get("id", "igris.local"),
            name=rp_config.get("name", "Igris AI Assistant")
        )
        self.server = Fido2Server(self.rp)

    def _load_credentials(self):
        """Load stored credentials."""
        if not self.credentials_path.exists():
            return

        try:
            data = json.loads(self.credentials_path.read_text())
            self.credentials = [
                StoredCredential.from_dict(c) for c in data.get("credentials", [])
            ]
            logger.info(f"Loaded {len(self.credentials)} hardware key credentials")
        except Exception as e:
            logger.error(f"Failed to load credentials: {e}")

    def _save_credentials(self):
        """Save credentials to storage."""
        data = {"credentials": [c.to_dict() for c in self.credentials]}
        self.credentials_path.parent.mkdir(parents=True, exist_ok=True)
        self.credentials_path.write_text(json.dumps(data, indent=2))
        self.credentials_path.chmod(0o600)

    def is_available(self) -> bool:
        """Check if FIDO2 is available and keys are connected."""
        if not self.available:
            return False

        try:
            devices = list(CtapHidDevice.list_devices())
            return len(devices) > 0
        except Exception:
            return False

    def list_devices(self) -> List[Dict[str, Any]]:
        """List connected FIDO2 devices."""
        if not self.available:
            return []

        devices = []
        try:
            for dev in CtapHidDevice.list_devices():
                devices.append({
                    "path": str(dev.descriptor.path),
                    "product": getattr(dev.descriptor, 'product_string', 'Unknown'),
                    "vendor": getattr(dev.descriptor, 'vendor_id', 0),
                })
        except Exception as e:
            logger.error(f"Error listing devices: {e}")

        return devices

    def has_registered_keys(self) -> bool:
        """Check if any keys are registered."""
        return len(self.credentials) > 0

    def register(self, user_id: str = "admin", user_name: str = "Admin") -> bool:
        """
        Register a new hardware key.

        Args:
            user_id: User identifier
            user_name: Display name

        Returns:
            True if registration successful
        """
        if not self.available:
            logger.error("FIDO2 not available")
            return False

        devices = list(CtapHidDevice.list_devices())
        if not devices:
            logger.error("No security key detected")
            print("❌ No security key detected. Please insert your key.")
            return False

        # Create user entity
        user = PublicKeyCredentialUserEntity(
            id=user_id.encode(),
            name=user_name,
            display_name=user_name
        )

        # Get authenticator selection criteria
        auth_config = self.config.get("authenticator", {})

        uv_map = {
            "required": UserVerificationRequirement.REQUIRED,
            "preferred": UserVerificationRequirement.PREFERRED,
            "discouraged": UserVerificationRequirement.DISCOURAGED
        }
        uv = uv_map.get(auth_config.get("user_verification", "preferred"),
                       UserVerificationRequirement.PREFERRED)

        # Exclude existing credentials
        exclude = [
            PublicKeyCredentialDescriptor(
                type=PublicKeyCredentialType.PUBLIC_KEY,
                id=c.credential_id
            )
            for c in self.credentials if c.user_id == user_id
        ]

        # Begin registration
        try:
            create_options, state = self.server.register_begin(
                user=user,
                credentials=exclude,
                user_verification=uv
            )

            print("\n🔑 Registering hardware key...")
            print("Touch your security key when it blinks.")

            # Use first available device
            device = devices[0]
            client = Fido2Client(
                device,
                f"https://{self.rp.id}",
                user_interaction=CliInteraction()
            )

            # Create credential
            result = client.make_credential(create_options["publicKey"])

            # Complete registration
            auth_data = self.server.register_complete(
                state,
                result.client_data,
                result.attestation_object
            )

            # Store credential
            import time
            credential = StoredCredential(
                credential_id=auth_data.credential_data.credential_id,
                public_key=cbor.encode(auth_data.credential_data.public_key),
                sign_count=0,
                user_id=user_id,
                created=time.time(),
                name=f"Key registered {time.strftime('%Y-%m-%d')}"
            )

            with self.lock:
                self.credentials.append(credential)
                self._save_credentials()

            print("✅ Hardware key registered successfully!")
            return True

        except Exception as e:
            logger.error(f"Registration failed: {e}")
            print(f"❌ Registration failed: {e}")
            return False

    def authenticate(self, user_id: str = "admin") -> bool:
        """
        Authenticate using hardware key.

        Args:
            user_id: User to authenticate

        Returns:
            True if authentication successful
        """
        if not self.available:
            logger.error("FIDO2 not available")
            return False

        # Get credentials for user
        user_credentials = [c for c in self.credentials if c.user_id == user_id]
        if not user_credentials:
            logger.error(f"No credentials for user: {user_id}")
            print("❌ No hardware key registered for this user")
            return False

        devices = list(CtapHidDevice.list_devices())
        if not devices:
            logger.error("No security key detected")
            print("❌ No security key detected. Please insert your key.")
            return False

        # Build credential descriptors
        credentials = [
            PublicKeyCredentialDescriptor(
                type=PublicKeyCredentialType.PUBLIC_KEY,
                id=c.credential_id
            )
            for c in user_credentials
        ]

        # Get user verification requirement
        auth_config = self.config.get("authenticator", {})
        uv_map = {
            "required": UserVerificationRequirement.REQUIRED,
            "preferred": UserVerificationRequirement.PREFERRED,
            "discouraged": UserVerificationRequirement.DISCOURAGED
        }
        uv = uv_map.get(auth_config.get("user_verification", "preferred"),
                       UserVerificationRequirement.PREFERRED)

        try:
            # Begin authentication
            request_options, state = self.server.authenticate_begin(
                credentials=credentials,
                user_verification=uv
            )

            print("\n🔑 Authenticating with hardware key...")
            print("Touch your security key when it blinks.")

            # Use first available device
            device = devices[0]
            client = Fido2Client(
                device,
                f"https://{self.rp.id}",
                user_interaction=CliInteraction()
            )

            # Get assertion
            result = client.get_assertion(request_options["publicKey"])
            assertion = result.get_response(0)

            # Find matching credential
            cred = next(
                (c for c in user_credentials
                 if c.credential_id == assertion.credential_id),
                None
            )

            if not cred:
                logger.error("Credential not found")
                return False

            # Verify assertion
            self.server.authenticate_complete(
                state,
                credentials,
                assertion.credential_id,
                result.client_data,
                assertion.authenticator_data,
                assertion.signature
            )

            # Update sign count
            with self.lock:
                cred.sign_count = assertion.authenticator_data.counter
                self._save_credentials()

            print("✅ Hardware key authentication successful!")
            logger.info(f"User {user_id} authenticated with hardware key")
            return True

        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            print(f"❌ Authentication failed: {e}")
            return False

    def list_registered_keys(self) -> List[Dict]:
        """List registered credentials."""
        return [
            {
                "id": c.credential_id.hex()[:16] + "...",
                "user_id": c.user_id,
                "name": c.name,
                "created": c.created,
                "sign_count": c.sign_count
            }
            for c in self.credentials
        ]

    def remove_key(self, credential_id_prefix: str) -> bool:
        """Remove a registered key by ID prefix."""
        with self.lock:
            for i, cred in enumerate(self.credentials):
                if cred.credential_id.hex().startswith(credential_id_prefix):
                    del self.credentials[i]
                    self._save_credentials()
                    return True
        return False


# Convenience functions
_manager = None

def get_manager() -> HardwareKeyManager:
    global _manager
    if _manager is None:
        _manager = HardwareKeyManager()
    return _manager

def is_available() -> bool:
    return get_manager().is_available()

def authenticate(user_id: str = "admin") -> bool:
    return get_manager().authenticate(user_id)

def register(user_id: str = "admin") -> bool:
    return get_manager().register(user_id)


# Self-test / CLI
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Hardware Key Manager")
    parser.add_argument("action", choices=["status", "list", "register", "auth", "remove"])
    parser.add_argument("--user", default="admin", help="User ID")
    parser.add_argument("--key-id", help="Key ID prefix for removal")
    args = parser.parse_args()

    print("Hardware Key Manager")
    print("=" * 40)

    manager = HardwareKeyManager()
    print(f"FIDO2 available: {FIDO2_AVAILABLE}")
    print(f"Key connected: {manager.is_available()}")

    if args.action == "status":
        devices = manager.list_devices()
        print(f"\nConnected devices: {len(devices)}")
        for d in devices:
            print(f"  - {d.get('product', 'Unknown')}")

        keys = manager.list_registered_keys()
        print(f"\nRegistered keys: {len(keys)}")
        for k in keys:
            print(f"  - {k['name']} ({k['id']}) for {k['user_id']}")

    elif args.action == "list":
        keys = manager.list_registered_keys()
        for k in keys:
            print(f"{k['id']} | {k['user_id']} | {k['name']}")

    elif args.action == "register":
        manager.register(args.user)

    elif args.action == "auth":
        result = manager.authenticate(args.user)
        print(f"\nAuthentication: {'SUCCESS' if result else 'FAILED'}")

    elif args.action == "remove":
        if not args.key_id:
            print("Error: --key-id required")
        else:
            if manager.remove_key(args.key_id):
                print("Key removed")
            else:
                print("Key not found")
