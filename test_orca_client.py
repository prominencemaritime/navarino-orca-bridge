#!/usr/bin/env python3
"""Test ORCA client by posting parsed data"""

import json
from src.app import initialise_app


def main():
    print("=" * 60)
    print("Testing ORCA Client")
    print("=" * 60)
    
    # Initialise application
    ctx = initialise_app()
    
    # Use pre-initialised ORCA client from context
    orca = ctx.orca_client
    
    # Test with each vessel's live data
    for vessel_ref_code, imo in ctx.config.vessel_identifiers.items():
        print(f"\n{'='*60}")
        print(f"Testing vessel: {vessel_ref_code} (IMO: {imo})")
        print('='*60)
        
        # Load the ORCA-formatted live data we created
        live_json_file = ctx.config.data_dir / f"{vessel_ref_code}_orca_live.json"
        
        if not live_json_file.exists():
            print(f"✗ File not found: {live_json_file}")
            print("  Run test_parser.py first to generate ORCA JSON files")
            continue
        
        with open(live_json_file, 'r') as f:
            orca_data = json.load(f)
        
        print(f"\nData to POST:")
        print(json.dumps(orca_data, indent=2))
        
        # Confirm before posting
        if ctx.config.orca_test:
            print(f"\n✓ Posting to TEST environment: {ctx.config.orca_base_url}")
        else:
            print(f"\n⚠ WARNING: Posting to LIVE environment: {ctx.config.orca_base_url}")
            response = input("  Continue? (yes/no): ")
            if response.lower() != 'yes':
                print("  Skipped.")
                continue
        
        try:
            # POST to ORCA
            result = orca.post_data(orca_data)
            
            print(f"\n✓ Success!")
            print(f"Response: {result}")
            
        except Exception as e:
            print(f"\n✗ Error: {e}")
            continue
    
    print("\n" + "=" * 60)
    print("ORCA client test complete")
    print("=" * 60)


if __name__ == "__main__":
    main()
