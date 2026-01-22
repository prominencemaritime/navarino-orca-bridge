#!/usr/bin/env python3
"""Production vessel sync script"""

import sys
from config.settings import get_config
from src.clients.infinity import InfinityWebServiceClient
from src.clients.orca import ORCAClient
from src.bridge import InfinityORCABridge


def main():
    # Load config
    cfg = get_config()
    
    # Safety check
    if not cfg.dry_run and cfg.orca_test:
        print("⚠️  WARNING: DRY_RUN=False but ORCA_TEST=True")
        print("You're about to POST to ORCA TEST environment.")
        response = input("Continue? (yes/no): ")
        if response.lower() != 'yes':
            print("Aborted.")
            return 1
    
    if not cfg.dry_run and not cfg.orca_test:
        print("⚠️  CRITICAL WARNING: DRY_RUN=False and ORCA_TEST=False")
        print("You're about to POST to ORCA PRODUCTION environment.")
        print("This will affect LIVE data!")
        response = input("Type 'CONFIRM' to proceed: ")
        if response != 'CONFIRM':
            print("Aborted.")
            return 1
    
    # Initialize clients
    infinity = InfinityWebServiceClient(
        base_url=cfg.infinity_base_url,
        token=cfg.infinity_token,
        timeout=cfg.request_timeout
    )
    
    orca = ORCAClient(
        base_url=cfg.orca_base_url,
        api_key=cfg.orca_x_api_key,
        timeout=cfg.request_timeout
    )
    
    # Initialize bridge
    bridge = InfinityORCABridge(infinity, orca)
    
    # Sync all vessels (live positions)
    print(f"\nSyncing {len(cfg.vessel_identifiers)} vessel(s)...")
    results = bridge.sync_all_vessels(
        vessel_identifiers=cfg.vessel_identifiers,
        sync_history=False,
        dry_run=cfg.dry_run
    )
    
    # Check for errors
    errors = [r for r in results if r['status'] == 'error']
    if errors:
        print(f"\n⚠️  {len(errors)} vessel(s) failed to sync")
        for err in errors:
            print(f"  - {err['vessel']}: {err.get('error', 'Unknown error')}")
        return 1
    
    print("\n✓ All vessels synced successfully")
    return 0


if __name__ == "__main__":
    sys.exit(main())
