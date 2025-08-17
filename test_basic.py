#!/usr/bin/env python3
"""Basic test to verify Clockwork project structure and imports."""

import sys
import traceback

def test_imports():
    """Test that all main modules can be imported."""
    print("Testing imports...")
    
    try:
        import clockwork
        print("✅ clockwork imported successfully")
        
        from clockwork import ClockworkCore
        print("✅ ClockworkCore imported successfully")
        
        from clockwork.models import IR, ActionList, ArtifactBundle
        print("✅ Models imported successfully")
        
        from clockwork import intake, assembly, forge
        print("✅ Submodules imported successfully")
        
        print(f"Clockwork version: {clockwork.__version__}")
        
        return True
        
    except Exception as e:
        print(f"❌ Import failed: {e}")
        traceback.print_exc()
        return False

def test_basic_functionality():
    """Test basic functionality without external dependencies."""
    print("\nTesting basic functionality...")
    
    try:
        from clockwork.models import ActionType, ResourceType, Action
        
        # Test enum usage
        action_type = ActionType.FETCH_REPO
        resource_type = ResourceType.SERVICE
        print(f"✅ Enums work: {action_type}, {resource_type}")
        
        # Test model creation
        action = Action(
            name="test_action",
            type=ActionType.FETCH_REPO,
            args={"url": "https://github.com/example/repo"}
        )
        print(f"✅ Model creation works: {action.name}")
        
        return True
        
    except Exception as e:
        print(f"❌ Basic functionality test failed: {e}")
        traceback.print_exc()
        return False

def main():
    """Run all tests."""
    print("Clockwork Basic Test Suite")
    print("=" * 40)
    
    all_passed = True
    
    # Test imports
    if not test_imports():
        all_passed = False
    
    # Test basic functionality
    if not test_basic_functionality():
        all_passed = False
    
    print("\n" + "=" * 40)
    if all_passed:
        print("🎉 All tests passed! Clockwork project structure is working correctly.")
        return 0
    else:
        print("💥 Some tests failed. Please check the errors above.")
        return 1

if __name__ == "__main__":
    exit(main())