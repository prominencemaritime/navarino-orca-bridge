# test_bridge.py

#!/usr/bin/env python3
"""Test the complete bridge (dry run mode)"""

import json
from config.settings import get_config
from src.clients.infinity import InfinityWebServiceClient
from src.clients.orca import ORCAClient
from src.bridge import InfinityORCABridge


def main():
    print("=" * 60)
    print("Testing Infinity-ORCA Bridge (DRY RUN)")
    print("=" * 60)
    
    # Load config
    cfg = get_config()
    
    # Initialize clients
    infinity = InfinityWebServiceClient(
        base_url=cfg.infinity_base_url,
        token=cfg.infinity_token,
        timeout=cfg.request_timeout
    )
    
    # Note: ORCA client will fail if no API key, but we won't use it in dry run
    try:
        orca = ORCAClient(
            base_url=cfg.orca_base_url,
            api_key=cfg.orca_x_api_key,
            timeout=cfg.request_timeout
        )
    except:
        print("\n⚠ ORCA API key not configured - using dry run mode only")
        orca = None
    
    # Initialize bridge
    bridge = InfinityORCABridge(infinity, orca)
    
    print("\n" + "=" * 60)
    print("Test 1: Sync Live Position (Dry Run)")
    print("=" * 60)
    
    results = bridge.sync_all_vessels(
        vessel_identifiers=cfg.vessel_identifiers,
        sync_history=False,
        dry_run=cfg.dry_run
    )
    
    for result in results:
        print(f"\nVessel: {result['vessel']}")
        print(f"Status: {result['status']}")
        if result['status'] == 'dry_run':
            print(f"Would sync: {len(result['data']['data'][0]['values'])} value(s)")
    
    print("\n" + "=" * 60)
    print("Test 2: Sync History (Dry Run)")
    print("=" * 60)
    
    results = bridge.sync_all_vessels(
        vessel_identifiers=cfg.vessel_identifiers,
        sync_history=True,
        dry_run=cfg.dry_run
    )
    
    for result in results:
        print(f"\nVessel: {result['vessel']}")
        print(f"Status: {result['status']}")
        if result['status'] == 'dry_run':
            print(f"Would sync: {result['position_count']} position(s)")
    
    if cfg.dry_run:
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
