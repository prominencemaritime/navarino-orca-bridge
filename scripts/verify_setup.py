#!/usr/bin/env python3
"""Verify the new architecture works correctly."""

import sys

def test_app_initialization():
    """Test that app initialises without errors."""
    print("Testing app initialization...")
    try:
        from src.app import initialise_app
        ctx = initialise_app()
        print(f"  ✓ Config loaded: {len(ctx.config.vessel_identifiers)} vessels")
        print(f"  ✓ Infinity client initialised")
        print(f"  ✓ ORCA client initialised")
        print(f"  ✓ Bridge initialised with timezone: {ctx.bridge.timezone}")
        return True
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        return False

def test_bridge_has_timezone():
    """Test that bridge has timezone attribute."""
    print("\nTesting bridge timezone...")
    try:
        from src.app import initialise_app
        ctx = initialise_app()
        assert hasattr(ctx.bridge, 'timezone'), "Bridge missing timezone attribute"
        assert ctx.bridge.timezone == ctx.config.timezone, "Bridge timezone mismatch"
        print(f"  ✓ Bridge timezone: {ctx.bridge.timezone}")
        return True
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        return False

def test_no_get_config_in_bridge():
    """Test that bridge.py doesn't import get_config."""
    print("\nTesting bridge.py doesn't use get_config...")
    try:
        with open('src/bridge.py', 'r') as f:
            content = f.read()
            assert 'get_config' not in content, "bridge.py still references get_config()"
        print(f"  ✓ bridge.py is clean")
        return True
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        return False

def main():
    print("=" * 60)
    print("NAVARINO ORCA BRIDGE - SETUP VERIFICATION")
    print("=" * 60)
    
    tests = [
        test_app_initialization,
        test_bridge_has_timezone,
        test_no_get_config_in_bridge,
    ]
    
    results = [test() for test in tests]
    
    print("\n" + "=" * 60)
    if all(results):
        print("✓ ALL TESTS PASSED - Ready for Docker deployment")
        print("=" * 60)
        return 0
    else:
        print("✗ SOME TESTS FAILED - Fix issues before proceeding")
        print("=" * 60)
        return 1

if __name__ == "__main__":
    sys.exit(main())
