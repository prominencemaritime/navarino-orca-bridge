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
        dry_run=True
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
        dry_run=True
    )
    
    for result in results:
        print(f"\nVessel: {result['vessel']}")
        print(f"Status: {result['status']}")
        if result['status'] == 'dry_run':
            print(f"Would sync: {result['position_count']} position(s)")
    
    print("\n" + "=" * 60)
    print("✓ Bridge test complete!")
    print("=" * 60)
    print("\nWhen you get ORCA API key:")
    print("1. Add ORCA_X_API_KEY to .env")
    print("2. Run: python test_bridge.py  (with dry_run=False)")


if __name__ == "__main__":
    main()
