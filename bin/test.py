#!/usr/bin/env python3
"""Test runner script for ADOC Toolkit."""

import subprocess
import sys
from pathlib import Path


def run_command(command: list[str], description: str) -> bool:
    """Run a command and return True if successful."""
    print(f"\n{'=' * 50}")
    print(f"Running: {description}")
    print(f"Command: {' '.join(command)}")
    print("=" * 50)

    try:
        subprocess.run(command, check=True, capture_output=False)
        print(f"✅ {description} passed")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed with exit code {e.returncode}")
        return False


def main() -> int:
    """Main test runner function."""
    # Change to project root directory
    project_root = Path(__file__).parent.parent
    print(f"Project root: {project_root}")

    # Test commands to run
    tests = [
        (["uv", "run", "pytest", "-v"], "Unit Tests (Verbose)"),
        (["uv", "run", "ruff", "check", "."], "Linting Check"),
        (["uv", "run", "ruff", "format", "--check", "."], "Format Check"),
    ]

    # Optional type checking (may have many errors in test files)
    optional_tests = [
        (["uv", "run", "mypy", "."], "Type Checking (Optional)"),
    ]

    all_passed = True
    results = []

    print("ADOC Toolkit Test Suite")
    print("======================")

    for command, description in tests:
        passed = run_command(command, description)
        results.append((description, passed))
        if not passed:
            all_passed = False

    # Run optional tests (don't affect overall pass/fail)
    print(f"\n{'=' * 50}")
    print("OPTIONAL TESTS")
    print("=" * 50)

    for command, description in optional_tests:
        passed = run_command(command, description)
        results.append((description, passed))

    # Summary
    print(f"\n{'=' * 50}")
    print("TEST SUMMARY")
    print("=" * 50)

    for description, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{description}: {status}")

    print(
        f"\nOverall: {'✅ ALL TESTS PASSED' if all_passed else '❌ SOME TESTS FAILED'}"
    )

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
