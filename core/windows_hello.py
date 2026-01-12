#!/usr/bin/env python3
"""
Windows Hello Authentication Integration
Provides biometric authentication via Windows Hello API.
"""

import sys
import ctypes
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# Windows Hello availability flag
WINDOWS_HELLO_AVAILABLE = False

if sys.platform == 'win32':
    try:
        # Try importing Windows Runtime
        import winrt.windows.security.credentials.ui as credentials_ui
        WINDOWS_HELLO_AVAILABLE = True
    except ImportError:
        logger.info("Windows Runtime not available - install winrt package")

class WindowsHelloAuth:
    """Windows Hello authentication handler."""

    def __init__(self):
        self.available = WINDOWS_HELLO_AVAILABLE

    def is_available(self) -> bool:
        """Check if Windows Hello is configured on this device."""
        if not self.available:
            return False
        try:
            # Check if Windows Hello is set up
            return self._check_availability()
        except Exception as e:
            logger.error(f"Windows Hello check failed: {e}")
            return False

    def _check_availability(self) -> bool:
        """Internal availability check."""
        if not WINDOWS_HELLO_AVAILABLE:
            return False
        try:
            import asyncio
            from winrt.windows.security.credentials.ui import (
                UserConsentVerifier,
                UserConsentVerifierAvailability
            )

            async def check():
                result = await UserConsentVerifier.check_availability_async()
                return result == UserConsentVerifierAvailability.AVAILABLE

            return asyncio.run(check())
        except Exception:
            return False

    def authenticate(self, message: str = "Verify your identity") -> bool:
        """
        Request Windows Hello authentication.

        Args:
            message: Prompt message shown to user

        Returns:
            True if authentication successful, False otherwise
        """
        if not self.available:
            logger.warning("Windows Hello not available")
            return False

        try:
            import asyncio
            from winrt.windows.security.credentials.ui import (
                UserConsentVerifier,
                UserConsentVerificationResult
            )

            async def verify():
                result = await UserConsentVerifier.request_verification_async(message)
                return result == UserConsentVerificationResult.VERIFIED

            return asyncio.run(verify())
        except Exception as e:
            logger.error(f"Windows Hello authentication failed: {e}")
            return False


def is_windows_hello_available() -> bool:
    """Quick check if Windows Hello can be used."""
    auth = WindowsHelloAuth()
    return auth.is_available()


def authenticate_with_windows_hello(message: str = "Igris requires authentication") -> bool:
    """Convenience function for Windows Hello auth."""
    auth = WindowsHelloAuth()
    return auth.authenticate(message)


# Self-test
if __name__ == "__main__":
    print("Windows Hello Authentication Test")
    print("=" * 40)
    print(f"Platform: {sys.platform}")
    print(f"Module available: {WINDOWS_HELLO_AVAILABLE}")

    auth = WindowsHelloAuth()
    print(f"Windows Hello available: {auth.is_available()}")

    if auth.is_available():
        print("\nRequesting authentication...")
        result = auth.authenticate("Test authentication for Igris")
        print(f"Authentication result: {'SUCCESS' if result else 'FAILED'}")
    else:
        print("\nWindows Hello not available on this system")
