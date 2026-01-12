#!/usr/bin/env python3
"""
Run all Igris security tests.
"""

import sys
import subprocess
from pathlib import Path

TEST_DIR = Path(__file__).parent

def run_test(test_file: Path) -> bool:
    print(f"\n>>> Running {test_file.name}...")
    result = subprocess.run(
        [sys.executable, str(test_file)],
        cwd=TEST_DIR.parent
    )
    return result.returncode == 0

def main():
    tests = [
        "test_phase2_auth.py",
        "test_phase3_execution.py",
        "test_phase4_validation.py",
        "test_phase5_integration.py",
        "test_security_suite.py",
    ]

    passed = 0
    failed = 0

    for test_name in tests:
        test_path = TEST_DIR / test_name
        if test_path.exists():
            if run_test(test_path):
                passed += 1
            else:
                failed += 1
        else:
            print(f"  [SKIP] {test_name} not found")

    print("\n" + "=" * 60)
    print(f"TEST SUITES: {passed} passed, {failed} failed")
    print("=" * 60)

    return 0 if failed == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
