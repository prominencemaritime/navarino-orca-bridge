# src/bridge.py

import logging
from typing import List, Dict, Any
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

from src.clients.infinity import InfinityWebServiceClient
from src.clients.orca import ORCAClient
from src.parsers.infinity_parser import InfinityParser
from src.transformers.orca_formatter import ORCAFormatter

from config.settings import VesselConfig

logger = logging.getLogger(__name__)


class InfinityORCABridge:
    """Bridge to sync vessel data from Infinity to ORCA"""
    
    def __init__(
        self,
        infinity_clients: Dict[str, InfinityWebServiceClient],
        orca_client: ORCAClient,
        timezone: str="UTC",
        logs_dir: Path=None
    ):
        """
        Initialise the bridge
        
        Args:
            infinity_client: Initialised Infinity client
            orca_client: Initialised ORCA client
            timezone: Timezone for health status timestamps
            logs_dir: Directory for logs and health status file
        """
        self.infinity_clients = infinity_clients
        self.orca = orca_client
        self.parser = InfinityParser()
        self.timezone = timezone
        
        # Set logs directory (default to /app/logs for Docker)
        if logs_dir is None:
            logs_dir = Path("/app/logs")
        self.logs_dir = logs_dir
        
        logger.info("Bridge initialised")


    def _write_health_status(self, status: str, error_msg: str="") -> None:
        """
        Write health status to file for Docker healthcheck monitoring.

        Args:
            status: "OK" or "ERROR"
            error_msg: Error message if status is ERROR
        """
        try:
            health_file = self.logs_dir / "health_status.txt"

            # Create directory if it does not exist
            health_file.parent.mkdir(parents=True, exist_ok=True)

            # Get timezone-aware timestamp
            now = datetime.now(tz=ZoneInfo(self.timezone))

            # Write automatically using a temporary file
            temp_file = health_file.with_suffix('.tmp')
            with open(temp_file, 'w') as f:
                f.write(f"{status} {now.isoformat()}\n")
                f.write(f"ALERT_TYPE: VesselSync\n")
                f.write(f"TIMEZONE: {self.timezone}\n")
                if error_msg:
                    f.write(f"ERROR_MSG: {error_msg}\n")

            # Atomic rename (prevents healthcheck from reading partially written file)
            temp_file.replace(health_file)

            logger.debug(f"health status written: {status}")

        except Exception as e:
            logger.error(f"Failed to write health status: {e}")


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

        # Initialise health status as ERROR in case of early exception
        error_occurred = False
        error_message = ""
        
        try:
            client = self.infinity_clients[vessel_ref_code]

            # Step 1: Fetch live position from Infinity
            logger.info("Fetching live position from Infinity...")
            position_xml = client.get_live_position(vessel_ref_code)
            
            # Step 2: Fetch interface status from Infinity
            logger.info("Fetching interface status from Infinity...")
            interface_xml = client.get_vessel_current_interface(vessel_ref_code)
            
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
            error_message = f"Failed to sync {vessel_ref_code}: {str(e)}"
            error_occurred = True
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
            client = self.infinity_clients[vessel_ref_code]

            # Step 1: Fetch history from Infinity
            logger.info("Fetching position history from Infinity...")
            history_xml = client.get_history_positions(vessel_ref_code)
            
            # Step 2: Fetch interface status
            logger.info("Fetching interface status from Infinity...")
            interface_xml = client.get_vessel_current_interface(vessel_ref_code)
            
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
        vessels: List[VesselConfig],
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
        logger.info(f"Starting batch sync | vessels={len(vessels)} | history={sync_history} | dry_run={dry_run}")
        
        results = []

        # Track if any errors occurred
        any_errors = False
        error_messages = []
        
        for vessel in vessels:
            vessel_ref_code = vessel.ref_code
            imo = vessel.imo

            logger.info(f"Processing vessel {vessel_ref_code}...")
            
            if sync_history:
                result = self.sync_vessel_history(vessel_ref_code, imo, dry_run)
            else:
                result = self.sync_vessel_live(vessel_ref_code, imo, dry_run)
            
            results.append(result)

            # Check for errors
            if result['status'] == 'error':
                any_errors = True
                error_msg = result.get('error', 'Unknown error')
                error_messages.append(f"{vessel_ref_code}: {error_msg}")
        
        # Summary
        success_count = sum(1 for r in results if r['status'] in ['success', 'dry_run'])
        error_count = sum(1 for r in results if r['status'] == 'error')
        total_count = len(results)
        
        logger.info("=" * 70)
        logger.info("BATCH SYNC SUMMARY")
        logger.info("=" * 70)
        logger.info(f"Total vessels: {total_count}")
        logger.info(f"Successful: {success_count}/{total_count}")
        logger.info(f"Errors: {error_count}/{total_count}")
        logger.info("=" * 70)

        # Write health status based on results
        if any_errors:
            combined_error = "; ".join(error_messages[:3])  # Limit to first 3 errors
            if len(error_messages) > 3:
                combined_error += f" (and {len(error_messages) - 3} more)"

            logger.warning(f"Writing ERROR health status: {combined_error}")
            self._write_health_status("ERROR", combined_error)
        else:
            logger.info("Writing OK health status")
            self._write_health_status("OK")
        
        return results
