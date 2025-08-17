#!/usr/bin/env python3
import sys
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path.cwd()))

print("Testing basic Python execution...")
print("Current working directory:", Path.cwd())
print("Python path:", sys.path[0])

# Test basic import
try:
    import clockwork.models
    print("✓ Models module imported successfully")
except ImportError as e:
    print(f"✗ Models import failed: {e}")
except Exception as e:
    print(f"✗ Unexpected error importing models: {e}")

try:
    from clockwork.models import ClockworkConfig
    config = ClockworkConfig(project_name="test")
    print(f"✓ ClockworkConfig created: {config.project_name}")
except Exception as e:
    print(f"✗ ClockworkConfig test failed: {e}")

print("Simple test completed.")