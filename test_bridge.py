#!/usr/bin/env python3
"""Test Infinity-ORCA Bridge"""
import json

from src.app import initialise_app


def main():
    print("=" * 60)
    print("Testing Infinity-ORCA Bridge (DRY RUN)")
    print("=" * 60)
    
    # Initialise application (loads config, sets up logging, creates clients)
    ctx = initialise_app()
    
    # Use pre-initialised bridge from context
    bridge = ctx.bridge
    
    print("\n" + "=" * 60)
    print("Test 1: Sync Live Position (Dry Run)")
    print("=" * 60)
    
    results = bridge.sync_all_vessels(
        vessels=ctx.config.vessels,
        sync_history=False,
        dry_run=ctx.config.dry_run
    )
    
    for result in results:
        print(f"\nVessel: {result['vessel']}")
        print(f"Status: {result['status']}")
        if result['status'] == 'dry_run':
            print(f"Would sync: {len(result['data']['data'][0]['values'])} value(s)")
            print("\nFull payload preview:")
            print(json.dumps(result['data'], indent=2))
    
    print("\n" + "=" * 60)
    print("Test 2: Sync History (Dry Run)")
    print("=" * 60)
    
    results = bridge.sync_all_vessels(
        vessels=ctx.config.vessels,
        sync_history=True,
        dry_run=ctx.config.dry_run
    )
    
    for result in results:
        print(f"\nVessel: {result['vessel']}")
        print(f"Status: {result['status']}")
        if result['status'] == 'dry_run':
            print(f"Would sync: {result['position_count']} position(s)")
    
    if ctx.config.dry_run:
        print("\n" + "=" * 60)
        print("⚠️  Currently in DRY RUN mode")
        print("=" * 60)
        print("\nTo enable live posting:")
        print("1. Set DRY_RUN=False in .env")
        print("2. Ensure ORCA_X_API_KEY is set")
        print("3. Run: python test_bridge.py")
    else:
        print("\n" + "=" * 60)
        print("✓ Bridge test complete (LIVE MODE)")
        print("=" * 60)


if __name__ == "__main__":
    main()
