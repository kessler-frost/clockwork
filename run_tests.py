#!/usr/bin/env python3
"""
Clockwork Test Runner

This script provides easy access to run different types of tests:
- Unit tests (fast, isolated)
- Integration tests (component interactions)
- Demo test (verify core functionality)

Usage:
    python run_tests.py [unit|integration|demo|all]
"""

import sys
import subprocess
import argparse
from pathlib import Path


def run_command(cmd, description):
    """Run a command and handle errors."""
    print(f"\n🚀 {description}")
    print(f"Command: {' '.join(cmd)}")
    print("-" * 60)
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=False)
        print(f"✅ {description} completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed with exit code {e.returncode}")
        return False
    except FileNotFoundError:
        print(f"❌ Command not found: {cmd[0]}")
        return False


def run_unit_tests():
    """Run unit tests."""
    return run_command(
        ["uv", "run", "pytest", "tests/unit/", "-v"],
        "Running unit tests"
    )


def run_integration_tests():
    """Run integration tests."""
    return run_command(
        ["uv", "run", "pytest", "tests/integration/", "-v"],
        "Running integration tests"
    )


def run_demo_test():
    """Run demo command to verify core functionality."""
    print(f"\n🚀 Running demo test to verify core functionality")
    print(f"Command: uv run clockwork demo --text-only")
    print("-" * 60)

    try:
        result = subprocess.run(
            ["uv", "run", "clockwork", "demo", "--text-only"],
            check=True,
            capture_output=False
        )
        print(f"✅ Demo test completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Demo test failed with exit code {e.returncode}")
        return False
    except FileNotFoundError:
        print(f"❌ Command not found: uv")
        return False


def run_all_tests():
    """Run all tests."""
    print("🧪 Running complete Clockwork test suite")
    print("=" * 60)

    success = True

    # Run unit tests
    if not run_unit_tests():
        success = False

    # Run integration tests
    if not run_integration_tests():
        success = False

    # Run demo test
    if not run_demo_test():
        success = False

    print("\n" + "=" * 60)
    if success:
        print("🎉 All tests completed successfully!")
    else:
        print("💥 Some tests failed. Check the output above.")

    return success


def main():
    """Main test runner."""
    parser = argparse.ArgumentParser(
        description="Clockwork test runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python run_tests.py unit        # Run only unit tests
    python run_tests.py integration # Run only integration tests
    python run_tests.py demo        # Run demo command test
    python run_tests.py all         # Run all tests (default)
        """
    )
    
    parser.add_argument(
        "test_type",
        nargs="?",
        default="all",
        choices=["unit", "integration", "demo", "all"],
        help="Type of tests to run (default: all)"
    )
    
    args = parser.parse_args()
    
    # Verify we're in the right directory
    if not Path("clockwork").exists():
        print("❌ Error: Must be run from the Clockwork project root directory")
        return 1
    
    # Run the requested tests
    success = False
    
    if args.test_type == "unit":
        success = run_unit_tests()
    elif args.test_type == "integration":
        success = run_integration_tests()
    elif args.test_type == "demo":
        success = run_demo_test()
    elif args.test_type == "all":
        success = run_all_tests()
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())