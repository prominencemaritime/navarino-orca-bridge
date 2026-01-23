#!/usr/bin/env python3
"""Manual sync script"""

import sys
from src.app import initialise_app


def main():
    # Initialise app (loads config and sets up logging)
    ctx = initialise_app()
    
    # Safety check
    if not ctx.config.dry_run and ctx.config.orca_test:
        print("⚠️  WARNING: DRY_RUN=False but ORCA_TEST=True")
        response = input("Continue? (yes/no): ").strip().lower()
        if response.lower() != 'yes':
            print("Aborted.")
            return 1
    
    if not ctx.config.dry_run and not ctx.config.orca_test:
        print("⚠️  WARNING: DRY_RUN=False but ORCA_TEST=False")
        print("-> Posting to PRODUCTION")
        response = input("Type 'CONFIRM': ").strip().lower()
        if response != 'confirm':
            print("Aborted.")
            return 1
    
    # Sync vessels
    number_of_vessels = len(ctx.config.vessel_identifiers)
    print(f"\nSyncing {number_of_vessels} vessel{'' if number_of_vessels==1 else 's'}")
    results = ctx.bridge.sync_all_vessels(
        vessel_identifiers=ctx.config.vessel_identifiers,
        sync_history=False,
        dry_run=ctx.config.dry_run
    )
    
    # Check for errors
    errors = [r for r in results if r['status'] == 'error']
    if errors:
        print(f"\n⚠️  {len(errors)} vessel{'' if len(errors)==1 else 's'} failed to sync")
        for err in errors:
            print(f"  - {err['vessel']}: {err.get('error')}")
        return 1
    
    print("\n✓ All vessels synced successfully")
    return 0


if __name__ == "__main__":
    sys.exit(main())
