# test_parser.py

#!/usr/bin/env python3
"""Test Infinity parser with actual XML files"""

import json
from pathlib import Path
from config.settings import get_config
from src.parsers.infinity_parser import InfinityParser
from src.transformers.orca_formatter import ORCAFormatter


def main():
    print("=" * 60)
    print("Testing Infinity Parser & ORCA Formatter")
    print("=" * 60)
    
    # Load config
    cfg = get_config()
    
    # Initialize parser
    parser = InfinityParser()
    
    # Test each vessel
    for vessel_ref_code, imo in cfg.vessel_identifiers.items():
        print(f"\n{'='*60}")
        print(f"Processing vessel: {vessel_ref_code} (IMO: {imo})")
        print('='*60)
        
        # File paths
        live_file = cfg.data_dir / f"{vessel_ref_code}_live_position.xml"
        history_file = cfg.data_dir / f"{vessel_ref_code}_history_positions.xml"
        interface_file = cfg.data_dir / f"{vessel_ref_code}_interface.xml"
        
        # Parse live position
        print("\n1. Parsing live position...")
        with open(live_file, 'r') as f:
            live_xml = f.read()
        
        live_position = parser.parse_live_position(live_xml)
        if live_position:
            print(f"   ✓ Live position parsed:")
            print(f"     Timestamp: {live_position['timestamp']}")
            print(f"     Position: {live_position['lat']}, {live_position['lon']}")
            print(f"     Course: {live_position['course']}°")
            print(f"     Speed: {live_position['speed_og']} knots")
        else:
            print("   ✗ Failed to parse live position")
        
        # Parse history positions
        print("\n2. Parsing history positions...")
        with open(history_file, 'r') as f:
            history_xml = f.read()
        
        history_positions = parser.parse_history_positions(history_xml)
        print(f"   ✓ Parsed {len(history_positions)} history position(s)")
        if history_positions:
            print(f"     Newest: {history_positions[0]['timestamp']}")
            print(f"     Oldest: {history_positions[-1]['timestamp']}")
        
        # Parse interface
        print("\n3. Parsing current interface...")
        with open(interface_file, 'r') as f:
            interface_xml = f.read()
        
        interface = parser.parse_current_interface(interface_xml)
        if interface:
            print(f"   ✓ Interface: {interface}")
        else:
            print("   ✗ No interface found")
        
        # Format for ORCA - Live position only
        print("\n4. Formatting live position for ORCA...")
        if live_position:
            orca_live = ORCAFormatter.format_vessel_data(
                imo=imo,
                positions=[live_position],
                internet_connection_status=interface
            )
            
            print(f"   ✓ ORCA format created")
            print("\n   ORCA Payload (Live):")
            print("   " + "-" * 56)
            print(json.dumps(orca_live, indent=6))
            print("   " + "-" * 56)
            
            # Save to file
            live_json_file = cfg.data_dir / f"{vessel_ref_code}_orca_live.json"
            with open(live_json_file, 'w') as f:
                json.dump(orca_live, f, indent=2)
            print(f"\n   Saved to: {live_json_file.name}")
        
        # Format for ORCA - History positions
        print("\n5. Formatting history positions for ORCA...")
        if history_positions:
            orca_history = ORCAFormatter.format_vessel_data(
                imo=imo,
                positions=history_positions,
                internet_connection_status=interface
            )
            
            print(f"   ✓ ORCA format created with {len(orca_history['data'][0]['values'])} positions")
            
            # Save to file
            history_json_file = cfg.data_dir / f"{vessel_ref_code}_orca_history.json"
            with open(history_json_file, 'w') as f:
                json.dump(orca_history, f, indent=2)
            print(f"   Saved to: {history_json_file.name}")
            
            # Show first and last entries as preview
            print("\n   Preview - First entry:")
            print(json.dumps(orca_history['data'][0]['values'][0], indent=6))
            print("\n   Preview - Last entry:")
            print(json.dumps(orca_history['data'][0]['values'][-1], indent=6))
    
    print("\n" + "=" * 60)
    print("✓ Parser test complete!")
    print("=" * 60)
    print(f"\nJSON files saved to: {cfg.data_dir}")
    print("\nNext step: Build ORCA client to POST this data")


if __name__ == "__main__":
    main()
