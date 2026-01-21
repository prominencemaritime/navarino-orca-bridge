# src/parsers/infinity_parser.py

import xml.etree.ElementTree as ET
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class InfinityParser:
    """Parser for Infinity Web Services XML responses"""
    
    def __init__(self):
        self.namespaces = {
            'SOAP-ENV': 'http://schemas.xmlsoap.org/soap/envelope/',
            'ns1': 'InfinityPositionsWsdl',
            'ns2': 'InfinityVesselsWsdl',
            'xsi': 'http://www.w3.org/2001/XMLSchema-instance'
        }
    
    def _safe_float(self, value: Optional[str]) -> Optional[float]:
        """Safely convert string to float"""
        if value is None or value == '':
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            logger.warning(f"Could not convert to float: {value}")
            return None
    
    def _parse_timestamp(self, timestamp_str: str) -> str:
        """
        Parse timestamp from Infinity format to ISO format
        
        Input: "2026-01-21 17:25:53+00"
        Output: "2026-01-21T17:25:53+00:00"
        """
        try:
            # Replace space with T and format timezone
            if '+' in timestamp_str:
                dt_part, tz_part = timestamp_str.rsplit('+', 1)
                # Pad timezone if needed
                if len(tz_part) == 2:
                    tz_part = f"{tz_part}:00"
                return f"{dt_part.replace(' ', 'T')}+{tz_part}"
            else:
                return timestamp_str.replace(' ', 'T')
        except Exception as e:
            logger.warning(f"Error parsing timestamp '{timestamp_str}': {e}")
            return timestamp_str
    
    def parse_live_position(self, xml_response: str) -> Optional[Dict[str, Any]]:
        """
        Parse getLivePosition response
        
        Returns:
            Dict with keys: timestamp, lat, lon, course, speed_og
            or None if parsing fails
        """
        try:
            root = ET.fromstring(xml_response)
            
            # Find the return element
            return_elem = root.find('.//ns1:getLivePositionResponse/return', self.namespaces)
            if return_elem is None:
                logger.error("No return element found in live position response")
                return None
            
            # Extract fields
            v_date = return_elem.find('v_date').text if return_elem.find('v_date') is not None else None
            latitude = return_elem.find('latitude').text if return_elem.find('latitude') is not None else None
            longitude = return_elem.find('longitude').text if return_elem.find('longitude') is not None else None
            heading = return_elem.find('heading').text if return_elem.find('heading') is not None else None
            speed = return_elem.find('speed').text if return_elem.find('speed') is not None else None
            
            # Validate required fields
            if not latitude or not longitude:
                logger.error("Missing required lat/lon in live position")
                return None
            
            result = {
                'timestamp': self._parse_timestamp(v_date) if v_date else datetime.utcnow().isoformat(),
                'lat': self._safe_float(latitude),
                'lon': self._safe_float(longitude),
                'course': self._safe_float(heading),
                'speed_og': self._safe_float(speed)
            }
            
            logger.debug(f"Parsed live position | lat={result['lat']}, lon={result['lon']}")
            return result
            
        except ET.ParseError as e:
            logger.error(f"XML parse error in live position: {e}")
            return None
        except Exception as e:
            logger.error(f"Error parsing live position: {e}")
            return None
    
    def parse_history_positions(self, xml_response: str) -> List[Dict[str, Any]]:
        """
        Parse getHistoryPositions response
        
        Returns:
            List of position dicts, ordered from newest to oldest
        """
        positions = []
        
        try:
            root = ET.fromstring(xml_response)
            
            # Find all position items
            items = root.findall('.//ns1:getHistoryPositionsResponse/return/item', self.namespaces)
            
            logger.info(f"Found {len(items)} history position(s)")
            
            for item in items:
                date = item.find('date').text if item.find('date') is not None else None
                latitude = item.find('latitude').text if item.find('latitude') is not None else None
                longitude = item.find('longitude').text if item.find('longitude') is not None else None
                heading = item.find('heading').text if item.find('heading') is not None else None
                speed = item.find('speed').text if item.find('speed') is not None else None
                
                # Skip if missing required fields
                if not latitude or not longitude:
                    logger.warning("Skipping history position with missing lat/lon")
                    continue
                
                position = {
                    'timestamp': self._parse_timestamp(date) if date else None,
                    'lat': self._safe_float(latitude),
                    'lon': self._safe_float(longitude),
                    'course': self._safe_float(heading),
                    'speed_og': self._safe_float(speed)
                }
                
                positions.append(position)
            
            logger.debug(f"Parsed {len(positions)} valid history position(s)")
            return positions
            
        except ET.ParseError as e:
            logger.error(f"XML parse error in history positions: {e}")
            return []
        except Exception as e:
            logger.error(f"Error parsing history positions: {e}")
            return []
    
    def parse_current_interface(self, xml_response: str) -> Optional[str]:
        """
        Parse getVesselsCurrentInterface response
        
        Returns:
            Interface profile name (e.g., "Starlink") or None
        """
        try:
            root = ET.fromstring(xml_response)
            
            # Find the interface profile
            profile_elem = root.find('.//ns2:getVesselsCurrentInterfaceResponse/return/item/profile', self.namespaces)
            
            if profile_elem is not None and profile_elem.text:
                profile = profile_elem.text
                logger.debug(f"Parsed interface profile: {profile}")
                return profile
            
            logger.warning("No interface profile found in response")
            return None
            
        except ET.ParseError as e:
            logger.error(f"XML parse error in interface: {e}")
            return None
        except Exception as e:
            logger.error(f"Error parsing interface: {e}")
            return None
