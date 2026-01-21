#!/usr/bin/env python3
"""Test Infinity Web Service client - all methods"""

from config.settings import get_config
from src.clients.infinity import InfinityWebServiceClient


def main():
    print("=" * 60)
    print("Testing Infinity Web Service Client")
    print("=" * 60)
    
    # Load config
    cfg = get_config()
    
    # Initialize client
    client = InfinityWebServiceClient(
        base_url=cfg.infinity_base_url,
        token=cfg.infinity_token,
        timeout=cfg.request_timeout
    )
    
    try:
        # Test all configured vessels
        for vessel_ref_code, imo in cfg.vessel_identifiers.items():
            print(f"\n{'='*60}")
            print(f"Testing vessel: {vessel_ref_code} (IMO: {imo})")
            print('='*60)
            
            # 1. Test live position
            print(f"\n1. Fetching live position...")
            live_response = client.get_live_position(vessel_ref_code)
            live_file = cfg.data_dir / f"{vessel_ref_code}_live_position.xml"
            with open(live_file, 'w', encoding='utf-8') as f:
                f.write(live_response)
            print(f"   ✓ Saved to: {live_file.name}")
            
            # 2. Test last history position
            print(f"2. Fetching last history position...")
            last_hist_response = client.get_last_history_position(vessel_ref_code)
            last_hist_file = cfg.data_dir / f"{vessel_ref_code}_last_history_position.xml"
            with open(last_hist_file, 'w', encoding='utf-8') as f:
                f.write(last_hist_response)
            print(f"   ✓ Saved to: {last_hist_file.name}")
            
            # 3. Test history positions
            print(f"3. Fetching position history...")
            history_response = client.get_history_positions(vessel_ref_code)
            history_file = cfg.data_dir / f"{vessel_ref_code}_history_positions.xml"
            with open(history_file, 'w', encoding='utf-8') as f:
                f.write(history_response)
            print(f"   ✓ Saved to: {history_file.name}")
            
            # 4. Test current interface
            print(f"4. Fetching current interface...")
            interface_response = client.get_vessel_current_interface(vessel_ref_code)
            interface_file = cfg.data_dir / f"{vessel_ref_code}_interface.xml"
            with open(interface_file, 'w', encoding='utf-8') as f:
                f.write(interface_response)
            print(f"   ✓ Saved to: {interface_file.name}")
            
            # Show preview of live position
            print(f"\nLive position preview (first 300 chars):")
            print("-" * 60)
            print(live_response[:300])
            print("-" * 60)
        
        print("\n" + "=" * 60)
        print("✓ All tests passed!")
        print("=" * 60)
        print(f"\nXML files saved to: {cfg.data_dir}")
        print("\nNext steps:")
        print("1. Examine XML files to understand structure")
        print("2. Build parser for position data")
        print("3. Build parser for interface data")
        print("4. Build ORCA formatter")
        
        return 0
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
