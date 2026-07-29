#!/usr/bin/env python3
"""Test Infinity Web Service client - all methods, all vessels"""

from src.app import initialise_app


def main():
    print("=" * 60)
    print("Testing Infinity Web Service Client")
    print("=" * 60)

    ctx = initialise_app()

    results = {}

    for vessel in ctx.config.vessels:
        vessel_ref_code = vessel.ref_code
        imo = vessel.imo
        client = ctx.infinity_clients[vessel_ref_code]

        print(f"\n{'=' * 60}")
        print(f"Testing vessel: {vessel_ref_code} (IMO: {imo})")
        print("=" * 60)

        vessel_ok = True

        # 1. Live position
        print("\n1. Fetching live position...")
        try:
            live_response = client.get_live_position(vessel_ref_code)
            live_file = ctx.config.data_dir / f"{vessel_ref_code}_live_position.xml"
            with open(live_file, 'w', encoding='utf-8') as f:
                f.write(live_response)
            print(f"   ✓ Saved to: {live_file.name}")
        except Exception as e:
            print(f"   ✗ Failed: {e}")
            vessel_ok = False

        # 2. Last history position
        print("2. Fetching last history position...")
        try:
            last_hist_response = client.get_last_history_position(vessel_ref_code)
            last_hist_file = ctx.config.data_dir / f"{vessel_ref_code}_last_history_position.xml"
            with open(last_hist_file, 'w', encoding='utf-8') as f:
                f.write(last_hist_response)
            print(f"   ✓ Saved to: {last_hist_file.name}")
        except Exception as e:
            print(f"   ✗ Failed: {e}")
            vessel_ok = False

        # 3. History positions
        print("3. Fetching position history...")
        try:
            history_response = client.get_history_positions(vessel_ref_code)
            history_file = ctx.config.data_dir / f"{vessel_ref_code}_history_positions.xml"
            with open(history_file, 'w', encoding='utf-8') as f:
                f.write(history_response)
            print(f"   ✓ Saved to: {history_file.name}")
        except Exception as e:
            print(f"   ✗ Failed: {e}")
            vessel_ok = False

        # 4. Current interface
        print("4. Fetching current interface...")
        try:
            interface_response = client.get_vessel_current_interface(vessel_ref_code)
            interface_file = ctx.config.data_dir / f"{vessel_ref_code}_interface.xml"
            with open(interface_file, 'w', encoding='utf-8') as f:
                f.write(interface_response)
            print(f"   ✓ Saved to: {interface_file.name}")
        except Exception as e:
            print(f"   ✗ Failed: {e}")
            vessel_ok = False

        # Live position preview (only if fetch succeeded)
        if vessel_ok:
            print(f"\nLive position preview (first 300 chars):")
            print("-" * 60)
            print(live_response[:300])
            print("-" * 60)

        results[vessel_ref_code] = vessel_ok

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    success = [r for r, ok in results.items() if ok]
    failed  = [r for r, ok in results.items() if not ok]

    print(f"Passed: {len(success)}/{len(results)}")
    for ref in success:
        print(f"  ✓ {ref}")

    if failed:
        print(f"Failed: {len(failed)}/{len(results)}")
        for ref in failed:
            print(f"  ✗ {ref}  ← check logs above (auth failure = wrong token, timeout = vessel offline)")

    print(f"\nXML files saved to: {ctx.config.data_dir}")

    return 0 if not failed else 1


if __name__ == "__main__":
    exit(main())
