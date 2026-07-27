# src/transformers/orca_formatter.py

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone


logger = logging.getLogger(__name__)


class ORCAFormatter:
    """Format vessel data for ORCA API"""
    
    @staticmethod
    def format_vessel_data(
        imo: int,
        positions: List[Dict[str, Any]],
        internet_connection_status: Optional[str] = None
    ) -> Dict:
        """
        Format vessel positions for ORCA API
        
        Args:
            imo: Vessel IMO number
            positions: List of position dicts with keys: timestamp, lat, lon, course, speed_og
            internet_connection_status: Current internet connection (e.g., "Starlink")
            
        Returns:
            Dict in ORCA API format
        """
        logger.debug(f"Formatting {len(positions)} position(s) for IMO {imo}")
        
        # Add internet_connection_status to each position
        values = []
        for pos in positions:
            # Skip positions without required fields
            if pos.get('lat') is None or pos.get('lon') is None:
                logger.warning(f"Skipping position with missing lat/lon: {pos}")
                continue
            
            value = {
                'timestamp': ORCAFormatter._format_timestamp(pos['timestamp']),
                'lat': pos['lat'],
                'lon': pos['lon']
            }
            
            # Add optional fields only if present
            if pos.get('course') is not None:
                value['course'] = pos['course']
            
            if pos.get('speed_og') is not None:
                value['speed'] = round(pos['speed_og'], 3)
            
            values.append(value)
        
        result = {
            "data": [{
                "imo": str(imo),
                "values": values
            }]
        }
        
        logger.info(f"Formatted {len(values)} value(s) for ORCA | IMO={imo}")
        return result
    
    @staticmethod
    def format_multiple_vessels(
        vessel_data: List[Dict[str, Any]]
    ) -> Dict:
        """
        Format multiple vessels for ORCA API
        
        Args:
            vessel_data: List of dicts with keys: imo, positions, internet_connection_status
            
        Returns:
            Dict in ORCA API format with all vessels
        """
        all_data = []
        
        for vessel in vessel_data:
            imo = vessel['imo']
            positions = vessel.get('positions', [])
            status = vessel.get('internet_connection_status')
            
            formatted = ORCAFormatter.format_vessel_data(imo, positions, status)
            all_data.extend(formatted['data'])
        
        return {"data": all_data}

    @staticmethod
    def _format_timestamp(ts: str) -> str:
        """Convert ISO 8601 to ORCA format: 'yyyy-mm-dd HH:MM:SS'"""
        dt = datetime.fromisoformat(ts)
        dt_utc = dt.astimezone(timezone.utc)
        return dt_utc.strftime('%Y-%m-%d %H:%M:%S')
