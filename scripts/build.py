#!/usr/bin/env python3
"""
Build script for Igris AI Assistant
Creates standalone executables using PyInstaller.
"""

import sys
import os
import shutil
import subprocess
import argparse
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).parent.parent
BUILD_DIR = PROJECT_ROOT / "build"
DIST_DIR = PROJECT_ROOT / "dist"

def get_version() -> str:
    """Get version from project."""
    return "2.0.0"

def get_platform_name() -> str:
    """Get platform identifier for build artifacts."""
    if sys.platform == "win32":
        return "windows"
    elif sys.platform == "darwin":
        return "macos"
    else:
        return "linux"

def clean():
    """Clean build directories."""
    print("Cleaning build directories...")

    for dir_path in [BUILD_DIR, DIST_DIR]:
        if dir_path.exists():
            shutil.rmtree(dir_path)
            print(f"  Removed {dir_path}")

def check_dependencies():
    """Check required build dependencies."""
    print("Checking dependencies...")

    try:
        import PyInstaller
        print(f"  PyInstaller: {PyInstaller.__version__}")
    except ImportError:
        print("  ERROR: PyInstaller not found")
        print("  Install with: pip install pyinstaller")
        return False

    # Check UPX (optional, for compression)
    if shutil.which("upx"):
        print("  UPX: found")
    else:
        print("  UPX: not found (optional)")

    return True

def build_executable(debug: bool = False, onefile: bool = False):
    """Build the executable."""
    print(f"\nBuilding for {get_platform_name()}...")

    spec_file = PROJECT_ROOT / "igris.spec"

    if not spec_file.exists():
        print(f"ERROR: Spec file not found: {spec_file}")
        return False

    cmd = [
        sys.executable, "-m", "PyInstaller",
        str(spec_file),
        "--clean",
        f"--distpath={DIST_DIR}",
        f"--workpath={BUILD_DIR}",
    ]

    if debug:
        cmd.append("--debug=all")

    if onefile:
        cmd.append("--onefile")

    print(f"Running: {' '.join(cmd)}")

    result = subprocess.run(cmd, cwd=PROJECT_ROOT)

    if result.returncode != 0:
        print("ERROR: Build failed")
        return False

    print("Build successful!")
    return True

def create_archive():
    """Create distribution archive."""
    print("\nCreating distribution archive...")

    platform = get_platform_name()
    version = get_version()
    timestamp = datetime.now().strftime("%Y%m%d")

    archive_name = f"igris-{version}-{platform}-{timestamp}"

    dist_path = DIST_DIR / "igris"

    if not dist_path.exists():
        print(f"ERROR: Distribution not found: {dist_path}")
        return None

    # Create archive
    if sys.platform == "win32":
        archive_path = DIST_DIR / f"{archive_name}.zip"
        shutil.make_archive(
            str(DIST_DIR / archive_name),
            "zip",
            dist_path.parent,
            dist_path.name
        )
    else:
        archive_path = DIST_DIR / f"{archive_name}.tar.gz"
        shutil.make_archive(
            str(DIST_DIR / archive_name),
            "gztar",
            dist_path.parent,
            dist_path.name
        )

    print(f"Created: {archive_path}")
    print(f"Size: {archive_path.stat().st_size / 1024 / 1024:.1f} MB")

    return archive_path

def run_smoke_test():
    """Run basic smoke test on built executable."""
    print("\nRunning smoke test...")

    if sys.platform == "win32":
        exe_path = DIST_DIR / "igris" / "igris.exe"
    else:
        exe_path = DIST_DIR / "igris" / "igris"

    if not exe_path.exists():
        print(f"ERROR: Executable not found: {exe_path}")
        return False

    # Test --version or --help
    # Note: Using --help as it's a standard argparse flag
    result = subprocess.run(
        [str(exe_path), "--help"],
        capture_output=True,
        text=True,
        timeout=30
    )

    if result.returncode == 0:
        print("  ✓ Executable runs")
        print("  ✓ --help works")
        return True
    else:
        print(f"  ✗ Failed: {result.stderr}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Build Igris executables")
    parser.add_argument("--clean", action="store_true", help="Clean build directories")
    parser.add_argument("--debug", action="store_true", help="Debug build")
    parser.add_argument("--onefile", action="store_true", help="Single file executable")
    parser.add_argument("--no-archive", action="store_true", help="Skip archive creation")
    parser.add_argument("--no-test", action="store_true", help="Skip smoke test")
    args = parser.parse_args()

    print("=" * 50)
    print("  Igris Build System")
    print("=" * 50)
    print(f"Platform: {get_platform_name()}")
    print(f"Version: {get_version()}")
    print(f"Python: {sys.version}")
    print()

    if args.clean:
        clean()
        return 0

    if not check_dependencies():
        return 1

    clean()

    if not build_executable(debug=args.debug, onefile=args.onefile):
        return 1

    if not args.no_test:
        if not run_smoke_test():
            print("WARNING: Smoke test failed")

    if not args.no_archive:
        archive = create_archive()
        if archive:
            print(f"\nDistribution ready: {archive}")

    print("\n" + "=" * 50)
    print("  Build Complete!")
    print("=" * 50)

    return 0

if __name__ == "__main__":
    sys.exit(main())
