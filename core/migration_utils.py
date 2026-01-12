"""
Migration Utilities

Handles migration from old plaintext credential storage to secure storage.
Run automatically on first launch after security upgrade.

Migration Tasks:
- Detect old ai_script_policy.json with admin_pin_hash
- Prompt user to re-enter PIN (cannot reverse SHA256)
- Generate new Argon2id hash
- Store in secure backend (Windows Credential Manager / keyring)
- Remove admin_pin_hash from policy file
- Mark as migrated
"""

import json
import hashlib
import getpass
import logging
from pathlib import Path
from typing import Optional, Dict
from datetime import datetime

try:
    from core.secrets_manager import SecretsManager
    from core.secure_auth import AuthenticationManager
except ImportError:
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from core.secrets_manager import SecretsManager
    from core.secure_auth import AuthenticationManager

# Configure logging
logging.basicConfig(level=logging.INFO)
migration_logger = logging.getLogger('igris.migration')


class MigrationError(Exception):
    """Raised when migration fails"""
    pass


class LegacyPolicyLocations:
    """Known locations for old policy files"""

    LOCATIONS = [
        Path.home() / "OneDrive" / "Documents" / "ai_script_policy.json",
        Path(__file__).parent / "ai_script_policy.json",
        Path(__file__).parent.parent / "ai_script_policy.json",
        Path(__file__).parent.parent / "config" / "ai_script_policy.json",
    ]


def find_legacy_policy_file() -> Optional[Path]:
    """
    Search for legacy policy file in known locations.

    Returns:
        Path to policy file if found, None otherwise
    """
    for location in LegacyPolicyLocations.LOCATIONS:
        if location.exists():
            migration_logger.info(f"Found legacy policy file: {location}")
            return location

    migration_logger.info("No legacy policy file found")
    return None


def load_legacy_policy(policy_path: Path) -> Dict:
    """
    Load legacy policy file.

    Args:
        policy_path: Path to policy file

    Returns:
        Policy dictionary

    Raises:
        MigrationError: If file cannot be loaded
    """
    try:
        content = policy_path.read_text(encoding='utf-8')
        policy = json.loads(content)
        migration_logger.info(f"Loaded legacy policy with {len(policy)} keys")
        return policy
    except json.JSONDecodeError as e:
        raise MigrationError(f"Invalid JSON in policy file: {e}")
    except Exception as e:
        raise MigrationError(f"Cannot read policy file: {e}")


def needs_migration(policy: Dict) -> bool:
    """
    Check if policy needs migration.

    Args:
        policy: Policy dictionary

    Returns:
        True if migration needed
    """
    # Check if already migrated
    if policy.get('migrated_to_secure_storage'):
        migration_logger.info("Policy already migrated")
        return False

    # Check if has old-style admin_pin_hash
    if 'admin_pin_hash' in policy:
        migration_logger.info("Policy needs migration (has admin_pin_hash)")
        return True

    return False


def verify_old_pin(pin: str, old_hash: str) -> bool:
    """
    Verify PIN against old SHA256 hash.

    Args:
        pin: Plain text PIN
        old_hash: Old SHA256 hash

    Returns:
        True if PIN matches
    """
    computed_hash = hashlib.sha256(pin.encode('utf-8')).hexdigest()
    return computed_hash == old_hash


def migrate_pin_to_secure_storage(
    old_pin_hash: str,
    secrets_mgr: SecretsManager,
    max_attempts: int = 3
) -> bool:
    """
    Migrate PIN from SHA256 hash to Argon2id in secure storage.

    Args:
        old_pin_hash: Old SHA256 hash
        secrets_mgr: SecretsManager instance
        max_attempts: Maximum attempts to enter correct PIN

    Returns:
        True if migration successful

    Raises:
        MigrationError: If migration fails
    """
    print("\n" + "=" * 60)
    print("SECURITY UPGRADE - PIN Migration Required")
    print("=" * 60)
    print("\nYour admin PIN is being upgraded to stronger encryption.")
    print("Please enter your current PIN to migrate to secure storage.\n")

    for attempt in range(max_attempts):
        # Prompt for current PIN
        current_pin = getpass.getpass(f"Current PIN (attempt {attempt + 1}/{max_attempts}): ")

        # Verify against old hash
        if verify_old_pin(current_pin, old_pin_hash):
            # Generate new Argon2id hash
            new_hash = secrets_mgr.hash_password(current_pin)

            # Store in secure backend
            secrets_mgr.store_pin_hash(new_hash)

            migration_logger.info("PIN migrated successfully to secure storage")
            print("\n✓ PIN migrated successfully to secure storage!")
            return True
        else:
            remaining = max_attempts - attempt - 1
            if remaining > 0:
                print(f"✗ Incorrect PIN. {remaining} attempts remaining.")
            else:
                print("✗ Migration failed: Too many incorrect attempts.")
                raise MigrationError("Failed to verify old PIN")

    return False


def migrate_policy_file(
    policy_path: Path,
    policy: Dict,
    secrets_mgr: SecretsManager
) -> None:
    """
    Migrate policy file to new format.

    Args:
        policy_path: Path to policy file
        policy: Policy dictionary
        secrets_mgr: SecretsManager instance

    Raises:
        MigrationError: If migration fails
    """
    migration_logger.info(f"Starting policy file migration: {policy_path}")

    # Check if has admin_pin_hash
    if 'admin_pin_hash' not in policy:
        migration_logger.warning("No admin_pin_hash found in policy")
        return

    old_pin_hash = policy['admin_pin_hash']

    # Migrate PIN to secure storage
    if not migrate_pin_to_secure_storage(old_pin_hash, secrets_mgr):
        raise MigrationError("PIN migration failed")

    # Remove admin_pin_hash from policy
    policy.pop('admin_pin_hash')

    # Add migration marker
    policy['migrated_to_secure_storage'] = True
    policy['migration_date'] = datetime.now().isoformat()
    policy['migration_version'] = '2.0.0'

    # Create backup of old policy
    backup_path = policy_path.with_suffix('.json.backup')
    backup_path.write_text(policy_path.read_text(), encoding='utf-8')
    migration_logger.info(f"Created backup: {backup_path}")

    # Write updated policy
    policy_path.write_text(json.dumps(policy, indent=2), encoding='utf-8')
    migration_logger.info(f"Updated policy file: {policy_path}")

    print(f"\n✓ Policy file updated: {policy_path}")
    print(f"✓ Backup created: {backup_path}")


def check_and_migrate() -> bool:
    """
    Check for legacy policy and migrate if needed.

    This is the main entry point for automatic migration.
    Call this on application startup.

    Returns:
        True if migration was performed or not needed, False if failed
    """
    try:
        migration_logger.info("Checking for legacy policy migration...")

        # Find legacy policy file
        policy_path = find_legacy_policy_file()
        if not policy_path:
            migration_logger.info("No legacy policy file found")
            return True

        # Load policy
        policy = load_legacy_policy(policy_path)

        # Check if migration needed
        if not needs_migration(policy):
            migration_logger.info("No migration needed")
            return True

        # Initialize secrets manager
        secrets_mgr = SecretsManager()

        # Perform migration
        migrate_policy_file(policy_path, policy, secrets_mgr)

        print("\n" + "=" * 60)
        print("Migration Complete!")
        print("=" * 60)
        print("\nYour credentials are now stored securely.")
        print("The old policy file has been backed up.\n")

        return True

    except MigrationError as e:
        migration_logger.error(f"Migration failed: {e}")
        print(f"\n✗ Migration failed: {e}")
        return False
    except Exception as e:
        migration_logger.error(f"Unexpected migration error: {e}")
        print(f"\n✗ Unexpected error during migration: {e}")
        return False


def setup_new_installation(secrets_mgr: Optional[SecretsManager] = None) -> bool:
    """
    Setup PIN for new installation (no legacy policy).

    Args:
        secrets_mgr: SecretsManager instance (creates new if None)

    Returns:
        True if setup successful
    """
    if secrets_mgr is None:
        secrets_mgr = SecretsManager()

    # Check if PIN already configured
    if secrets_mgr.get_pin_hash():
        migration_logger.info("PIN already configured")
        return True

    print("\n" + "=" * 60)
    print("IGRIS AI ASSISTANT - First Time Setup")
    print("=" * 60)
    print("\nWelcome! Let's set up your admin PIN.")
    print("PIN Requirements:")
    print("  - At least 4 characters")
    print("  - Maximum 32 characters")
    print("  - Can be numbers, letters, or mixed\n")

    for attempt in range(3):
        # Get new PIN
        pin1 = getpass.getpass("Enter new admin PIN: ")

        # Validate length
        if len(pin1) < 4:
            print("✗ PIN too short (minimum 4 characters)")
            continue
        if len(pin1) > 32:
            print("✗ PIN too long (maximum 32 characters)")
            continue

        # Confirm PIN
        pin2 = getpass.getpass("Confirm admin PIN: ")

        if pin1 != pin2:
            print("✗ PINs do not match")
            continue

        # Hash and store
        pin_hash = secrets_mgr.hash_password(pin1)
        secrets_mgr.store_pin_hash(pin_hash)

        print("\n✓ Admin PIN configured successfully!")
        migration_logger.info("Admin PIN configured for new installation")
        return True

    print("\n✗ Setup failed: Too many attempts")
    return False


if __name__ == "__main__":
    # Test migration process
    print("Migration Utilities - Test Mode")
    print("=" * 60)

    # Check for legacy policy
    policy_path = find_legacy_policy_file()

    if policy_path:
        print(f"\nFound policy file: {policy_path}")
        policy = load_legacy_policy(policy_path)

        if needs_migration(policy):
            print("\n⚠ Migration required!")
            response = input("\nRun migration now? (yes/no): ")

            if response.lower() == 'yes':
                success = check_and_migrate()
                if success:
                    print("\n✓ Migration completed successfully")
                else:
                    print("\n✗ Migration failed")
            else:
                print("\nMigration skipped")
        else:
            print("\n✓ Policy already migrated or no migration needed")
    else:
        print("\nNo legacy policy found")
        print("This appears to be a new installation")

        response = input("\nRun first-time setup? (yes/no): ")
        if response.lower() == 'yes':
            success = setup_new_installation()
            if success:
                print("\n✓ Setup completed successfully")
            else:
                print("\n✗ Setup failed")
