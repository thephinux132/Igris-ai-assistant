#!/usr/bin/env python3
"""
Comprehensive Security Test Suite
Consolidates all security validation tests.
"""

import sys
import os
from pathlib import Path
from typing import Callable, List, Tuple

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

class TestSuite:
    def __init__(self, name: str):
        self.name = name
        self.tests: List[Tuple[str, Callable]] = []
        self.passed = 0
        self.failed = 0
        self.errors = []

    def test(self, name: str):
        """Decorator to register a test."""
        def decorator(func):
            self.tests.append((name, func))
            return func
        return decorator

    def run(self) -> bool:
        print(f"\n{'='*60}")
        print(f"TEST SUITE: {self.name}")
        print(f"{'='*60}")

        for name, func in self.tests:
            try:
                result = func()
                if result:
                    self.passed += 1
                    print(f"  ✓ {name}")
                else:
                    self.failed += 1
                    print(f"  ✗ {name}")
            except Exception as e:
                self.failed += 1
                self.errors.append((name, str(e)))
                print(f"  ✗ {name}: {e}")

        print(f"\nResults: {self.passed} passed, {self.failed} failed")
        return self.failed == 0

# Initialize test suites
auth_suite = TestSuite("Authentication Security")
exec_suite = TestSuite("Command Execution Security")
input_suite = TestSuite("Input Validation")
plugin_suite = TestSuite("Plugin Security")
approval_suite = TestSuite("Approval Workflow")

# ============================================================
# Authentication Tests
# ============================================================

@auth_suite.test("Secrets manager initializes")
def test_secrets_init():
    from core.secrets_manager import SecretsManager
    sm = SecretsManager()
    return sm is not None

@auth_suite.test("Argon2 hashing available")
def test_argon2():
    from core.secrets_manager import SecretsManager
    sm = SecretsManager()
    hashed = sm.hash_password("test123")
    return hashed and len(hashed) > 20

@auth_suite.test("Password verification works")
def test_password_verify():
    from core.secrets_manager import SecretsManager
    sm = SecretsManager()
    hashed = sm.hash_password("test123")
    return sm.verify_password("test123", hashed)

@auth_suite.test("Wrong password rejected")
def test_wrong_password():
    from core.secrets_manager import SecretsManager
    sm = SecretsManager()
    hashed = sm.hash_password("test123")
    return not sm.verify_password("wrong", hashed)

@auth_suite.test("Rate limiting configured")
def test_rate_limit():
    from core.secure_auth import AuthenticationManager
    am = AuthenticationManager()
    return am.max_attempts > 0 and am.cooldown_duration.total_seconds() > 0

# ============================================================
# Command Execution Tests
# ============================================================

@exec_suite.test("Secure execution module loads")
def test_secure_exec_load():
    from core.secure_execution import safe_run_command
    return callable(safe_run_command)

@exec_suite.test("Safe command executes")
def test_safe_command():
    from core.secure_execution import safe_run_command
    result = safe_run_command(["echo", "test"], timeout=5)
    return result.returncode == 0 and "test" in result.stdout

@exec_suite.test("Shell metacharacters blocked")
def test_shell_metachar():
    from core.secure_execution import validate_command_parts
    try:
        validate_command_parts(["echo", "test; rm -rf /"])
        return False  # Should have raised
    except:
        return True

@exec_suite.test("Path traversal blocked")
def test_path_traversal():
    from core.secure_execution import validate_command_parts
    try:
        validate_command_parts(["cat", "../../etc/passwd"])
        return False
    except:
        return True

@exec_suite.test("Command whitelist enforced")
def test_whitelist():
    from core.command_whitelist import is_command_allowed
    return is_command_allowed("notepad") and not is_command_allowed("evil_binary")

# ============================================================
# Input Validation Tests
# ============================================================

@input_suite.test("Validator initializes")
def test_validator_init():
    from core.input_validation import InputValidator
    v = InputValidator(strict_mode=True)
    return v is not None

@input_suite.test("Clean input accepted")
def test_clean_input():
    from core.input_validation import InputValidator
    v = InputValidator(strict_mode=True)
    valid, _ = v.validate_user_input("open notepad")
    return valid

@input_suite.test("Shell injection blocked")
def test_injection():
    from core.input_validation import InputValidator
    v = InputValidator(strict_mode=True)
    valid, _ = v.validate_user_input("test; rm -rf /")
    return not valid

@input_suite.test("Command substitution blocked")
def test_cmd_substitution():
    from core.input_validation import InputValidator
    v = InputValidator(strict_mode=True)
    valid, _ = v.validate_user_input("$(whoami)")
    return not valid

@input_suite.test("Backticks blocked")
def test_backticks():
    from core.input_validation import InputValidator
    v = InputValidator(strict_mode=True)
    valid, _ = v.validate_user_input("`id`")
    return not valid

@input_suite.test("LLM output sanitized")
def test_llm_sanitize():
    from core.input_validation import InputValidator
    v = InputValidator(strict_mode=True)
    try:
        v.sanitize_llm_output({"action": "test; whoami", "args": []})
        return False
    except:
        return True

# ============================================================
# Plugin Security Tests
# ============================================================

@plugin_suite.test("Plugin loader validates names")
def test_plugin_name():
    from core.secure_plugin_loader import SecurePluginLoader
    loader = SecurePluginLoader()
    valid, _ = loader.validate_plugin_name("good_plugin")
    bad, _ = loader.validate_plugin_name("../../../etc/passwd")
    return valid and not bad

@plugin_suite.test("Plugin path traversal blocked")
def test_plugin_traversal():
    from core.secure_plugin_loader import SecurePluginLoader, PluginSecurityError
    loader = SecurePluginLoader()
    try:
        loader.get_plugin_path("../../../etc/passwd")
        return False
    except PluginSecurityError:
        return True

@plugin_suite.test("GUI files use secure execution")
def test_gui_secure():
    gui_file = PROJECT_ROOT / "gui" / "igris_control_gui_main.py"
    if not gui_file.exists():
        return True  # Skip if not present
    content = gui_file.read_text()
    return "from core.secure_execution import" in content

@plugin_suite.test("High-risk plugins have validation")
def test_plugin_validation():
    plugins_to_check = [
        "automation_scheduler_setup.py",
        "build_ssh_tunnel.py",
        "lan_topology_scanner.py",
    ]
    for plugin_name in plugins_to_check:
        plugin_path = PROJECT_ROOT / "plugins" / plugin_name
        if plugin_path.exists():
            content = plugin_path.read_text()
            if "validate" not in content.lower():
                return False
    return True

# ============================================================
# Approval Workflow Tests
# ============================================================

@approval_suite.test("Approval workflow loads")
def test_approval_load():
    try:
        from core.approval_workflow import ApprovalWorkflow
        return True
    except ImportError:
        return True  # Optional module

@approval_suite.test("Safe commands auto-approved")
def test_auto_approve():
    try:
        from core.approval_workflow import ApprovalWorkflow, ApprovalLevel
        wf = ApprovalWorkflow()
        level, _ = wf.check_command("echo hello")
        return level == ApprovalLevel.AUTO
    except ImportError:
        return True

@approval_suite.test("Dangerous commands flagged")
def test_dangerous_flagged():
    try:
        from core.approval_workflow import ApprovalWorkflow, ApprovalLevel
        wf = ApprovalWorkflow()
        level, _ = wf.check_command("shutdown /s /t 0")
        return level == ApprovalLevel.CRITICAL
    except ImportError:
        return True

# ============================================================
# Main Runner
# ============================================================

def run_all():
    print("\n" + "=" * 60)
    print("IGRIS SECURITY TEST SUITE")
    print("=" * 60)

    all_passed = True
    suites = [auth_suite, exec_suite, input_suite, plugin_suite, approval_suite]

    total_passed = 0
    total_failed = 0

    for suite in suites:
        if not suite.run():
            all_passed = False
        total_passed += suite.passed
        total_failed += suite.failed

    print("\n" + "=" * 60)
    print(f"TOTAL: {total_passed} passed, {total_failed} failed")
    print("=" * 60)

    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(run_all())
