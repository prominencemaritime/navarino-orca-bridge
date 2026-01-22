# src/clients/infinity.py

import requests
import time
from functools import wraps
import logging
from typing import Optional
from src.utils.retry import retry_with_backoff

logger = logging.getLogger(__name__)


class InfinityWebServiceClient:
    """Client for Infinity XML Web Services"""
    
    def __init__(self, base_url: str, token: str, timeout: int = 30):
        """
        Initialize Infinity Web Service client
        
        Args:
            base_url: Base URL for Infinity services
            token: Authentication token
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip('/')
        self.token = token
        self.timeout = timeout
        
        logger.info(f"Initialized Infinity client | url={self.base_url}")

    @retry_with_backoff(max_retries=3, backoff_factor=2)
    def _make_soap_request(self, endpoint: str, soap_action: str, body: str) -> str:
        """
        Make SOAP request and return response text
        
        Args:
            endpoint: API endpoint path
            soap_action: SOAP action string
            body: SOAP request body XML
            
        Returns:
            Response XML as string
            
        Raises:
            requests.exceptions.RequestException: On network/HTTP errors
        """
        url = f"{self.base_url}{endpoint}"
        headers = {
            "Content-Type": "text/xml; charset=UTF-8",
            "SOAPAction": f'"{soap_action}"',
            "x-http-auth": self.token
        }
        
        logger.debug(f"SOAP request | url={url} | action={soap_action}")
        
        try:
            # Use tuple for (connect_timeout, read_timeout)
            response = requests.post(
                url, 
                data=body, 
                headers=headers, 
                timeout=(10, self.timeout)
            )
            
            # Log response before raising for debugging
            if not response.ok:
                logger.error(f"HTTP {response.status_code} | response_body={response.text[:500]}")
            
            response.raise_for_status()
            
            logger.debug(f"SOAP response | status={response.status_code} | size={len(response.text)} bytes")
            return response.text
            
        except requests.exceptions.Timeout:
            logger.error(f"Request timeout after {self.timeout}s | url={url}")
            raise
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error {response.status_code} | url={url} | body={response.text[:200]}")
            raise
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection error | url={url} | error={e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error | url={url} | error={e}")
            raise

    
    def get_live_position(self, vessel_ref_code: str) -> str:
        """
        Get current position of vessel
        
        Args:
            vessel_ref_code: Vessel reference code
            
        Returns:
            XML response string
        """
        if not vessel_ref_code:
            raise ValueError("vessel_ref_code cannot be empty")

        vessel_ref_code = vessel_ref_code.strip()
        
        logger.info(f"Fetching live position | vessel={vessel_ref_code}")
        
        endpoint = "/pub/ws/positionsws.php"
        soap_action = "InfinityPositionsWsdl#getLivePosition"
        
        body = f"""<Envelope xmlns="http://schemas.xmlsoap.org/soap/envelope/">
            <Body>
                <getLivePosition xmlns="InfinityPositionsWsdl">
                    <vessel_ref_key>{vessel_ref_code}</vessel_ref_key>
                </getLivePosition>
            </Body>
        </Envelope>"""
        
        return self._make_soap_request(endpoint, soap_action, body)
    
    def get_last_history_position(self, vessel_ref_code: str) -> str:
        """
        Get last recorded position of vessel
        
        Args:
            vessel_ref_code: Vessel reference code
            
        Returns:
            XML response string
        """
        if not vessel_ref_code:
            raise ValueError("vessel_ref_code cannot be empty")

        vessel_ref_code = vessel_ref_code.strip()
        
        logger.info(f"Fetching last history position | vessel={vessel_ref_code}")
        
        endpoint = "/pub/ws/positionsws.php"
        soap_action = "InfinityPositionsWsdl#getLastHistoryPosition"
        
        body = f"""<Envelope xmlns="http://schemas.xmlsoap.org/soap/envelope/">
            <Body>
                <getLastHistoryPosition xmlns="InfinityPositionsWsdl">
                    <vessel_ref_key>{vessel_ref_code}</vessel_ref_key>
                </getLastHistoryPosition>
            </Body>
        </Envelope>"""
        
        return self._make_soap_request(endpoint, soap_action, body)
    
    def get_history_positions(self, vessel_ref_code: str) -> str:
        """
        Get historical positions for vessel
        
        Args:
            vessel_ref_code: Vessel reference code
            
        Returns:
            XML response string
        """
        if not vessel_ref_code:
            raise ValueError("vessel_ref_code cannot be empty")

        vessel_ref_code = vessel_ref_code.strip()

        logger.info(f"Fetching position history | vessel={vessel_ref_code}")
        
        endpoint = "/pub/ws/positionsws.php"
        soap_action = "InfinityPositionsWsdl#getHistoryPositions"
        
        body = f"""<Envelope xmlns="http://schemas.xmlsoap.org/soap/envelope/">
            <Body>
                <getHistoryPositions xmlns="InfinityPositionsWsdl">
                    <vessel_ref_key>{vessel_ref_code}</vessel_ref_key>
                </getHistoryPositions>
            </Body>
        </Envelope>"""
        
        return self._make_soap_request(endpoint, soap_action, body)
    
    def get_vessel_current_interface(self, vessel_ref_code: str) -> str:
        """
        Get current internet connection interface
        
        Args:
            vessel_ref_code: Vessel reference code
            
        Returns:
            XML response string
        """
        if not vessel_ref_code:
            raise ValueError("vessel_ref_code cannot be empty")
        
        logger.info(f"Fetching current interface | vessel={vessel_ref_code}")
        
        endpoint = "/pub/ws/vesselsws.php"
        soap_action = "InfinityVesselsWsdl#getVesselsCurrentInterface"
        
        body = f"""<Envelope xmlns="http://schemas.xmlsoap.org/soap/envelope/">
            <Body>
                <getVesselsCurrentInterface xmlns="InfinityVesselsWsdl">
                    <vessel>{vessel_ref_code}</vessel>
                </getVesselsCurrentInterface>
            </Body>
        </Envelope>"""
        
        return self._make_soap_request(endpoint, soap_action, body)
