#!/usr/bin/env python3
"""
Integration test for the complete Clockwork pipeline.

This script tests the Intake → Assembly → Forge pipeline with the 
enhanced components from all phases.
"""

import sys
import tempfile
import os
from pathlib import Path

# Add the clockwork package to path
sys.path.insert(0, str(Path(__file__).parent))

def test_basic_integration():
    """Test basic integration without external dependencies."""
    print("🧪 Testing Clockwork Integration...")
    
    try:
        # Test basic imports
        print("📦 Testing imports...")
        from clockwork.models import IR, ActionList, ArtifactBundle, ClockworkConfig
        from clockwork.core import ClockworkCore
        from clockwork.errors import ClockworkError, IntakeError
        print("✓ Basic imports successful")
        
        # Test ClockworkCore initialization
        print("🔧 Testing ClockworkCore initialization...")
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir)
            
            # Create a basic clockwork.json config
            config_file = config_path / "clockwork.json"
            config_file.write_text('{"project_name": "test-project", "log_level": "INFO"}')
            
            # Initialize ClockworkCore
            core = ClockworkCore(config_path=config_path)
            print(f"✓ ClockworkCore initialized for project: {core.config.project_name}")
            print(f"✓ Available runners: {', '.join(core.available_runners)}")
        
        # Test error handling
        print("❌ Testing error handling...")
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                # Try to initialize with invalid config
                config_path = Path(temp_dir)
                config_file = config_path / "clockwork.json"
                config_file.write_text('{"invalid": json}')  # Invalid JSON
                
                core = ClockworkCore(config_path=config_path)
        except Exception as e:
            if "JSON" in str(e):
                print("✓ Configuration error handling works")
            else:
                print(f"⚠️  Unexpected error: {e}")
        
        # Test model creation
        print("📋 Testing model creation...")
        config = ClockworkConfig(project_name="test-integration")
        print(f"✓ Created config: {config.project_name}")
        
        action_list = ActionList(
            version="1",
            steps=[
                {"name": "test_step", "args": {"message": "Hello, Clockwork!"}}
            ]
        )
        print(f"✓ Created ActionList with {len(action_list.steps)} steps")
        
        print("\n🎉 Integration test completed successfully!")
        return True
        
    except Exception as e:
        print(f"\n❌ Integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_runner_capabilities():
    """Test runner capabilities without actually running anything."""
    print("\n🏃 Testing runner capabilities...")
    
    try:
        from clockwork.forge.runner import RunnerFactory, select_runner
        
        factory = RunnerFactory()
        available = factory.get_available_runners()
        print(f"✓ Available runners: {', '.join(available)}")
        
        # Test runner selection
        context = {"requires_isolation": False}
        selected = select_runner(context)
        print(f"✓ Selected runner for context: {selected}")
        
        # Test runner creation (local should always be available)
        if "local" in available:
            runner = factory.create_runner("local")
            capabilities = runner.get_capabilities()
            print(f"✓ Local runner capabilities: {capabilities['type']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Runner test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_error_system():
    """Test the centralized error system."""
    print("\n⚠️  Testing error system...")
    
    try:
        from clockwork.errors import (
            ClockworkError, IntakeError, ForgeError,
            create_user_friendly_error, format_error_chain
        )
        
        # Test basic error creation
        error = ClockworkError(
            "Test error message",
            error_code="TEST_ERROR",
            context={"component": "test", "operation": "testing"},
            suggestions=["This is a test", "Check the test configuration"]
        )
        
        friendly_msg = create_user_friendly_error(error)
        print("✓ Error system works:")
        print(f"   Raw: {error}")
        print(f"   Friendly: {friendly_msg.split(chr(10))[0]}...")  # First line only
        
        # Test error chaining
        try:
            raise ValueError("Original error")
        except ValueError as original:
            wrapped = IntakeError("Wrapped error", context={"file": "test.cw"})
            wrapped.__cause__ = original
            
            chain = format_error_chain(wrapped)
            print(f"✓ Error chaining: {len(chain)} characters")
        
        return True
        
    except Exception as e:
        print(f"❌ Error system test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("🔮 CLOCKWORK INTEGRATION TEST")
    print("=" * 60)
    
    tests = [
        test_basic_integration,
        test_runner_capabilities, 
        test_error_system
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
    
    print("\n" + "=" * 60)
    print(f"📊 RESULTS: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All integration tests passed!")
        sys.exit(0)
    else:
        print("❌ Some tests failed. Check the output above.")
        sys.exit(1)