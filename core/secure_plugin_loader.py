"""
Secure Plugin Loader

Provides secure plugin loading with path validation to prevent path traversal attacks.

Security Features:
- Path traversal prevention (../../ patterns blocked)
- Plugin directory enforcement (plugins must be in plugins/)
- Path sanitization and normalization
- Validation before importlib execution
- Audit logging of all plugin loads
"""

import importlib.util
import logging
from pathlib import Path
from typing import Optional
import types
import sys

# Configure logging
logging.basicConfig(level=logging.INFO)
plugin_logger = logging.getLogger('igris.security.plugins')


class PluginSecurityError(Exception):
    """Raised when plugin loading fails security validation"""
    pass


class SecurePluginLoader:
    """
    Secure plugin loader with path validation.

    Prevents path traversal attacks and ensures plugins are loaded
    only from authorized directories.
    """

    def __init__(self, plugins_dir: Optional[Path] = None):
        """
        Initialize secure plugin loader.

        Args:
            plugins_dir: Base directory for plugins (default: ./plugins)
        """
        if plugins_dir is None:
            # Default to plugins/ directory relative to this file's parent
            plugins_dir = Path(__file__).parent.parent / "plugins"

        self.plugins_dir = plugins_dir.resolve()

        if not self.plugins_dir.exists():
            plugin_logger.warning(f"Plugins directory does not exist: {self.plugins_dir}")

        plugin_logger.info(f"SecurePluginLoader initialized: {self.plugins_dir}")

    def validate_plugin_name(self, plugin_name: str) -> tuple[bool, str]:
        """
        Validate plugin name for security issues.

        Args:
            plugin_name: Plugin name (may include "plugin:" prefix)

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not plugin_name:
            return False, "Empty plugin name"

        # Remove "plugin:" prefix if present
        if plugin_name.startswith("plugin:"):
            plugin_name = plugin_name[7:]

        # Check for path traversal
        if ".." in plugin_name:
            return False, "Path traversal detected in plugin name"

        # Check for path separators
        if "/" in plugin_name or "\\" in plugin_name:
            return False, "Path separators not allowed in plugin name"

        # Check for special characters (allow alphanumeric, underscore, hyphen)
        import re
        if not re.match(r'^[a-zA-Z0-9_-]+$', plugin_name):
            return False, "Plugin name contains invalid characters"

        # Check length
        if len(plugin_name) > 100:
            return False, "Plugin name too long"

        return True, "OK"

    def get_plugin_path(self, plugin_name: str) -> Path:
        """
        Get validated plugin file path.

        Args:
            plugin_name: Plugin name

        Returns:
            Resolved, validated Path object

        Raises:
            PluginSecurityError: If validation fails
        """
        # Validate name
        is_valid, error_msg = self.validate_plugin_name(plugin_name)
        if not is_valid:
            raise PluginSecurityError(f"Invalid plugin name: {error_msg}")

        # Remove prefix if present
        if plugin_name.startswith("plugin:"):
            plugin_name = plugin_name[7:]

        # Construct path
        plugin_path = self.plugins_dir / f"{plugin_name}.py"

        # Resolve to absolute path
        try:
            resolved_path = plugin_path.resolve()
        except (OSError, RuntimeError) as e:
            raise PluginSecurityError(f"Cannot resolve plugin path: {e}")

        # Verify path is within plugins directory
        try:
            resolved_path.relative_to(self.plugins_dir)
        except ValueError:
            raise PluginSecurityError(
                f"Plugin path outside allowed directory: {resolved_path}"
            )

        # Check file exists
        if not resolved_path.exists():
            raise PluginSecurityError(f"Plugin file not found: {plugin_name}")

        # Check it's a file (not directory)
        if not resolved_path.is_file():
            raise PluginSecurityError(f"Plugin path is not a file: {plugin_name}")

        plugin_logger.info(f"Validated plugin path: {resolved_path}")
        return resolved_path

    def load_plugin(self, plugin_name: str) -> types.ModuleType:
        """
        Load plugin module securely.

        Args:
            plugin_name: Plugin name (with or without "plugin:" prefix)

        Returns:
            Loaded module

        Raises:
            PluginSecurityError: If validation or loading fails

        Example:
            >>> loader = SecurePluginLoader()
            >>> plugin = loader.load_plugin("network_scanner")
            >>> result = plugin.run()
        """
        # Get validated path
        plugin_path = self.get_plugin_path(plugin_name)

        # Remove prefix for module name
        module_name = plugin_name.removeprefix("plugin:")

        # Load module using importlib
        try:
            spec = importlib.util.spec_from_file_location(module_name, plugin_path)
            if spec is None:
                raise PluginSecurityError(f"Failed to create module spec: {plugin_name}")

            module = importlib.util.module_from_spec(spec)

            if spec.loader is None:
                raise PluginSecurityError(f"No loader available for plugin: {plugin_name}")

            # Execute module
            spec.loader.exec_module(module)

            plugin_logger.info(f"Successfully loaded plugin: {plugin_name}")
            return module

        except Exception as e:
            plugin_logger.error(f"Failed to load plugin {plugin_name}: {e}")
            raise PluginSecurityError(f"Failed to load plugin: {e}")

    def load_plugin_safely(self, plugin_name: str) -> Optional[types.ModuleType]:
        """
        Load plugin with exception handling (returns None on failure).

        Args:
            plugin_name: Plugin name

        Returns:
            Loaded module or None if failed
        """
        try:
            return self.load_plugin(plugin_name)
        except PluginSecurityError as e:
            plugin_logger.error(f"Plugin loading failed: {e}")
            return None
        except Exception as e:
            plugin_logger.error(f"Unexpected error loading plugin: {e}")
            return None

    def list_available_plugins(self) -> list[str]:
        """
        List all available plugin names.

        Returns:
            List of plugin names (without .py extension)
        """
        if not self.plugins_dir.exists():
            return []

        plugins = []
        for path in self.plugins_dir.glob("*.py"):
            if path.name != "__init__.py":
                plugins.append(path.stem)

        return sorted(plugins)


# Convenience function for quick plugin loading
def load_plugin_secure(plugin_name: str, plugins_dir: Optional[Path] = None) -> Optional[types.ModuleType]:
    """
    Convenience function to securely load a plugin.

    Args:
        plugin_name: Plugin name
        plugins_dir: Optional plugins directory

    Returns:
        Loaded module or None if failed
    """
    loader = SecurePluginLoader(plugins_dir)
    return loader.load_plugin_safely(plugin_name)


if __name__ == "__main__":
    # Self-test
    print("Secure Plugin Loader - Self Test")
    print("=" * 60)

    # Test 1: Initialize loader
    print("\n[Test 1] Initializing secure plugin loader...")
    try:
        loader = SecurePluginLoader()
        print(f"✓ Initialized: {loader.plugins_dir}")
    except Exception as e:
        print(f"✗ Failed: {e}")
        sys.exit(1)

    # Test 2: Validate good plugin name
    print("\n[Test 2] Validating good plugin name...")
    is_valid, msg = loader.validate_plugin_name("network_scanner")
    if is_valid:
        print("✓ Valid plugin name accepted")
    else:
        print(f"✗ Valid name rejected: {msg}")

    # Test 3: Block path traversal
    print("\n[Test 3] Blocking path traversal...")
    is_valid, msg = loader.validate_plugin_name("../../malware")
    if not is_valid:
        print(f"✓ Path traversal blocked: {msg}")
    else:
        print("✗ Path traversal not blocked!")

    # Test 4: Block path separators
    print("\n[Test 4] Blocking path separators...")
    is_valid, msg = loader.validate_plugin_name("subdir/plugin")
    if not is_valid:
        print(f"✓ Path separator blocked: {msg}")
    else:
        print("✗ Path separator not blocked!")

    # Test 5: List available plugins
    print("\n[Test 5] Listing available plugins...")
    try:
        plugins = loader.list_available_plugins()
        print(f"✓ Found {len(plugins)} plugins")
        if plugins:
            print(f"  First 5: {', '.join(plugins[:5])}")
    except Exception as e:
        print(f"⚠ Listing failed: {e}")

    # Test 6: Try to load a plugin (if any exist)
    print("\n[Test 6] Testing plugin load (if available)...")
    if plugins:
        test_plugin = plugins[0]
        try:
            module = loader.load_plugin(test_plugin)
            print(f"✓ Successfully loaded: {test_plugin}")

            # Check if it has a run() function
            if hasattr(module, 'run'):
                print(f"  ℹ Plugin has run() function")
        except PluginSecurityError as e:
            print(f"⚠ Plugin load blocked: {e}")
        except Exception as e:
            print(f"⚠ Plugin load failed: {e}")
    else:
        print("  ℹ No plugins available to test")

    # Test 7: Block malicious path
    print("\n[Test 7] Blocking malicious plugin path...")
    try:
        loader.load_plugin("plugin:../../../etc/passwd")
        print("✗ Malicious path not blocked!")
    except PluginSecurityError as e:
        print(f"✓ Malicious path blocked: {e}")

    print("\n" + "=" * 60)
    print("Self-test complete.")
