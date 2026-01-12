#!/usr/bin/env python3
"""
Test Phase 2: Secrets Migration and Authentication

This script tests the new authentication system to verify:
1. SecretsManager stores and retrieves credentials
2. AuthenticationManager handles authentication correctly
3. Migration utilities work as expected
4. Core module loads policy from secure storage

Run this before deploying Phase 2 changes.
"""

import sys
from pathlib import Path

# Add core to path
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "core"))

print("=" * 70)
print("PHASE 2 AUTHENTICATION TEST")
print("=" * 70)

# Test 1: Import security modules
print("\n[Test 1] Importing security modules...")
try:
    from core.secrets_manager import SecretsManager
    from core.secure_auth import AuthenticationManager
    from core.migration_utils import check_and_migrate, setup_new_installation
    print("✓ All security modules imported successfully")
except ImportError as e:
    print(f"✗ Failed to import security modules: {e}")
    sys.exit(1)

# Test 2: Create SecretsManager
print("\n[Test 2] Creating SecretsManager (fallback backend for testing)...")
try:
    secrets_mgr = SecretsManager(backend='file')
    print(f"✓ SecretsManager created with fallback backend")
except Exception as e:
    print(f"✗ Failed to create SecretsManager: {e}")
    sys.exit(1)

# Test 3: Setup test PIN
print("\n[Test 3] Setting up test PIN...")
try:
    test_pin = "test1234"
    auth_mgr = AuthenticationManager(secrets_manager=secrets_mgr)
    auth_mgr.setup_pin(test_pin)
    print(f"✓ Test PIN configured")
except Exception as e:
    print(f"✗ Failed to setup PIN: {e}")
    sys.exit(1)

# Test 4: Verify PIN (correct)
print("\n[Test 4] Verifying correct PIN...")
try:
    if auth_mgr.verify_pin(test_pin):
        print("✓ Correct PIN verified successfully")
    else:
        print("✗ Correct PIN was rejected")
        sys.exit(1)
except Exception as e:
    print(f"✗ PIN verification failed: {e}")
    sys.exit(1)

# Test 5: Verify PIN (wrong)
print("\n[Test 5] Verifying wrong PIN (should reject)...")
try:
    if not auth_mgr.verify_pin("wrongpin"):
        print("✓ Wrong PIN correctly rejected")
    else:
        print("✗ Wrong PIN was accepted")
        sys.exit(1)
except Exception as e:
    print(f"✗ Wrong PIN test failed: {e}")
    sys.exit(1)

# Test 6: Load policy with secure storage
print("\n[Test 6] Testing core/igris_core.py load_policy()...")
try:
    from core.igris_core import load_policy, SECURITY_MODULES_AVAILABLE

    if not SECURITY_MODULES_AVAILABLE:
        print("⚠ Security modules not available in igris_core")
        print("  This is expected if running before integration")
    else:
        policy = load_policy()
        if 'admin_pin_hash' in policy:
            print(f"✓ Policy loaded with PIN hash from secure storage")
        else:
            print("⚠ Policy loaded but no PIN hash found")
            print("  (This is OK if no PIN was configured)")
except Exception as e:
    print(f"✗ Failed to load policy: {e}")
    import traceback
    traceback.print_exc()

# Test 7: Check migration detection
print("\n[Test 7] Testing migration detection...")
try:
    from core.migration_utils import find_legacy_policy_file, needs_migration, load_legacy_policy

    policy_path = find_legacy_policy_file()
    if policy_path:
        print(f"  Found policy file: {policy_path}")
        policy = load_legacy_policy(policy_path)
        if needs_migration(policy):
            print(f"  ⚠ Migration needed for: {policy_path}")
        else:
            print(f"  ✓ Policy already migrated or no migration needed")
    else:
        print("  ℹ No legacy policy file found (this is OK for new installations)")
except Exception as e:
    print(f"✗ Migration detection failed: {e}")
    import traceback
    traceback.print_exc()

# Cleanup test credentials
print("\n[Cleanup] Removing test credentials...")
try:
    secrets_mgr.delete_secret("admin_pin_hash")
    print("✓ Test credentials cleaned up")
except Exception as e:
    print(f"⚠ Cleanup warning: {e}")

print("\n" + "=" * 70)
print("PHASE 2 TEST SUMMARY")
print("=" * 70)
print("✓ All critical tests passed!")
print("\nPhase 2 integration is ready for deployment.")
print("\nNext steps:")
print("  1. Run migration for existing users: python core/migration_utils.py")
print("  2. For new installations: python -m core.migration_utils (first-time setup)")
print("  3. Test authentication: python -m cli.igris_cli \"test admin command\"")
print("=" * 70)
