# src/bridge.py

import logging
from typing import List, Dict, Any
from config.settings import get_config
from src.clients.infinity import InfinityWebServiceClient
from src.clients.orca import ORCAClient
from src.parsers.infinity_parser import InfinityParser
from src.transformers.orca_formatter import ORCAFormatter

logger = logging.getLogger(__name__)


class InfinityORCABridge:
    """Bridge to sync vessel data from Infinity to ORCA"""
    
    def __init__(
        self,
        infinity_client: InfinityWebServiceClient,
        orca_client: ORCAClient
    ):
        """
        Initialize the bridge
        
        Args:
            infinity_client: Initialized Infinity client
            orca_client: Initialized ORCA client
        """
        self.infinity = infinity_client
        self.orca = orca_client
        self.parser = InfinityParser()
        
        logger.info("Bridge initialized")
    
    def sync_vessel_live(
        self,
        vessel_ref_code: str,
        imo: int,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Sync live position for a single vessel
        
        Args:
            vessel_ref_code: Vessel reference code for Infinity
            imo: Vessel IMO number for ORCA
            dry_run: If True, don't actually POST to ORCA
            
        Returns:
            Dict with sync results
        """
        logger.info(f"Starting live sync | vessel={vessel_ref_code} | imo={imo} | dry_run={dry_run}")
        
        try:
            # Step 1: Fetch live position from Infinity
            logger.info("Fetching live position from Infinity...")
            position_xml = self.infinity.get_live_position(vessel_ref_code)
            
            # Step 2: Fetch interface status from Infinity
            logger.info("Fetching interface status from Infinity...")
            interface_xml = self.infinity.get_vessel_current_interface(vessel_ref_code)
            
            # Step 3: Parse responses
            logger.info("Parsing Infinity responses...")
            position = self.parser.parse_live_position(position_xml)
            interface = self.parser.parse_current_interface(interface_xml)
            
            if not position:
                logger.error("Failed to parse position data")
                return {
                    "status": "error",
                    "vessel": vessel_ref_code,
                    "message": "Failed to parse position data"
                }
            
            logger.info(f"Parsed position | lat={position['lat']}, lon={position['lon']}")
            logger.info(f"Interface: {interface or 'unknown'}")
            
            # Step 4: Format for ORCA
            logger.info("Formatting data for ORCA...")
            orca_data = ORCAFormatter.format_vessel_data(
                imo=imo,
                positions=[position],
                internet_connection_status=interface
            )
            
            # Step 5: POST to ORCA (unless dry run)
            if dry_run:
                logger.info("DRY RUN - Would POST to ORCA:")
                logger.info(f"  IMO: {imo}")
                logger.info(f"  Timestamp: {position['timestamp']}")
                logger.info(f"  Position: {position['lat']}, {position['lon']}")
                logger.info(f"  Interface: {interface}")
                
                return {
                    "status": "dry_run",
                    "vessel": vessel_ref_code,
                    "imo": imo,
                    "data": orca_data
                }
            
            else:
                logger.info("Posting to ORCA...")
                orca_response = self.orca.post_data(orca_data)
                
                logger.info(f"✓ Successfully synced vessel {vessel_ref_code}")
                
                return {
                    "status": "success",
                    "vessel": vessel_ref_code,
                    "imo": imo,
                    "orca_response": orca_response
                }
        
        except Exception as e:
            logger.error(f"Failed to sync vessel {vessel_ref_code} | error={e}")
            return {
                "status": "error",
                "vessel": vessel_ref_code,
                "error": str(e)
            }
    
    def sync_vessel_history(
        self,
        vessel_ref_code: str,
        imo: int,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Sync historical positions for a single vessel
        
        Args:
            vessel_ref_code: Vessel reference code for Infinity
            imo: Vessel IMO number for ORCA
            dry_run: If True, don't actually POST to ORCA
            
        Returns:
            Dict with sync results
        """
        logger.info(f"Starting history sync | vessel={vessel_ref_code} | imo={imo} | dry_run={dry_run}")
        
        try:
            # Step 1: Fetch history from Infinity
            logger.info("Fetching position history from Infinity...")
            history_xml = self.infinity.get_history_positions(vessel_ref_code)
            
            # Step 2: Fetch interface status
            logger.info("Fetching interface status from Infinity...")
            interface_xml = self.infinity.get_vessel_current_interface(vessel_ref_code)
            
            # Step 3: Parse responses
            logger.info("Parsing Infinity responses...")
            positions = self.parser.parse_history_positions(history_xml)
            interface = self.parser.parse_current_interface(interface_xml)
            
            if not positions:
                logger.warning("No history positions found")
                return {
                    "status": "no_data",
                    "vessel": vessel_ref_code,
                    "message": "No history positions available"
                }
            
            logger.info(f"Parsed {len(positions)} history position(s)")
            
            # Step 4: Format for ORCA
            logger.info("Formatting data for ORCA...")
            orca_data = ORCAFormatter.format_vessel_data(
                imo=imo,
                positions=positions,
                internet_connection_status=interface
            )
            
            # Step 5: POST to ORCA (unless dry run)
            if dry_run:
                logger.info(f"DRY RUN - Would POST {len(positions)} positions to ORCA")
                logger.info(f"  Date range: {positions[-1]['timestamp']} to {positions[0]['timestamp']}")
                
                return {
                    "status": "dry_run",
                    "vessel": vessel_ref_code,
                    "imo": imo,
                    "position_count": len(positions),
                    "data": orca_data
                }
            
            else:
                logger.info(f"Posting {len(positions)} positions to ORCA...")
                orca_response = self.orca.post_data(orca_data)
                
                logger.info(f"✓ Successfully synced {len(positions)} history positions for {vessel_ref_code}")
                
                return {
                    "status": "success",
                    "vessel": vessel_ref_code,
                    "imo": imo,
                    "position_count": len(positions),
                    "orca_response": orca_response
                }
        
        except Exception as e:
            logger.error(f"Failed to sync history for {vessel_ref_code} | error={e}")
            return {
                "status": "error",
                "vessel": vessel_ref_code,
                "error": str(e)
            }
    
    def sync_all_vessels(
        self,
        vessel_identifiers: Dict[str, int],
        sync_history: bool = False,
        dry_run: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Sync all configured vessels
        
        Args:
            vessel_identifiers: Dict mapping vessel_ref_code to IMO
            sync_history: If True, sync history; if False, only live
            dry_run: If True, don't actually POST to ORCA
            
        Returns:
            List of sync results for each vessel
        """
        # Safety check: if dry_run is False but config says dry_run, warn
        cfg = get_config()
        
        if not dry_run and cfg.dry_run:
            logger.warning("Method called with dry_run=False but config has DRY_RUN=True")
            logger.warning("Using config value (DRY_RUN=True) for safety")
            dry_run = True

        logger.info(f"Starting batch sync | vessels={len(vessel_identifiers)} | history={sync_history} | dry_run={dry_run}")
        
        results = []
        
        for vessel_ref_code, imo in vessel_identifiers.items():
            logger.info(f"Processing vessel {vessel_ref_code}...")
            
            if sync_history:
                result = self.sync_vessel_history(vessel_ref_code, imo, dry_run)
            else:
                result = self.sync_vessel_live(vessel_ref_code, imo, dry_run)
            
            results.append(result)
        
        # Summary
        success_count = sum(1 for r in results if r['status'] == 'success')
        error_count = sum(1 for r in results if r['status'] == 'error')
        
        logger.info("="*60)
        logger.info("BATCH SYNC SUMMARY")
        logger.info("="*60)
        logger.info(f"Total vessels: {len(results)}")
        logger.info(f"Successful: {success_count}")
        logger.info(f"Errors: {error_count}")
        logger.info("="*60)
        
        return results
