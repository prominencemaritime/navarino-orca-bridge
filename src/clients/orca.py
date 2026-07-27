# src/clients/orca.py

import requests
import json
import logging
from typing import Dict, Any
from src.utils.retry import retry_with_backoff

logger = logging.getLogger(__name__)


class ORCAClient:
    """Client for ORCA Vessel Tracking Service API"""
    
    def __init__(self, base_url: str, api_key: str, x_source: str, x_organization: str, timeout: int = 30):
        """
        Initialize ORCA API client
        
        Args:
            base_url: ORCA API base URL (test or live)
            api_key: ORCA API key
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.timeout = timeout
        self.x_source = x_source
        self.x_organization = x_organization
        
        logger.info(f"Initialized ORCA client | url={self.base_url}")
    
    @retry_with_backoff(max_retries=3, backoff_factor=2)
    def post_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        POST vessel data to ORCA API
        
        Args:
            data: Vessel data in ORCA format
            
        Returns:
            Response from ORCA API
            
        Raises:
            requests.exceptions.RequestException: On network/HTTP errors
        """
        url = f"{self.base_url}/data"
        headers = {
            "Content-Type": "application/json",
            "X-API-KEY": self.api_key,
            "X-Source": self.x_source,
            "X-Organization": self.x_organization
        }
        
        # Count vessels and values for logging
        vessel_count = len(data.get('data', []))
        total_values = sum(len(v.get('values', [])) for v in data.get('data', []))
        
        logger.info(f"Posting to ORCA | vessels={vessel_count} | values={total_values}")
        logger.debug(f"POST {url}")
        
        try:
            response = requests.post(
                url,
                json=data,
                headers=headers,
                timeout=self.timeout
            )
            
            logger.info(f"ORCA response | status={response.status_code}")
            
            # Handle different response codes
            if response.status_code in [200, 201, 204]:
                logger.info(f"[Status Code: {response.status_code}] ✓ Data saved successfully to ORCA")

                # Parse JSON safely
                try:
                    return response.json() if response.text else {"status": "success", "code": response.status_code}
                except json.JSONDecodeError:
                    logger.warning("ORCA returned non-JSON response")
                    return {"status": "success", "code": response.status_code, "raw": response.text}
            
            elif response.status_code == 403:
                logger.error("[Status Code: 403] ORCA authentication failed | Check x-api-key header")
                response.raise_for_status()
            
            elif response.status_code == 404:
                logger.error("[Status Code: 404] ORCA vessel not found | Check IMO number")
                response.raise_for_status()
            
            elif response.status_code == 422:
                # Parse validation errors if available
                try:
                    error_detail = response.json()
                    logger.error(f"[Status Code: 422] ORCA invalid data | errors={error_detail}")
                except:
                    logger.error(f"[Status Code: 422] ORCA invalid data | response={response.text}")
                raise requests.exceptions.HTTPError(f"422 Unprocessable: {response.text}", response=response)
            
            else:
                logger.warning(f"Unexpected ORCA response | status={response.status_code}")
                response.raise_for_status()
            
            return response.json() if response.text else {}
            
        except requests.exceptions.Timeout:
            logger.error(f"ORCA request timeout after {self.timeout}s")
            raise
        
        except requests.exceptions.HTTPError as e:
            logger.error(f"ORCA HTTP error | status={response.status_code} | response={response.text[:200]}")
            raise
        
        except requests.exceptions.ConnectionError as e:
            logger.error(f"ORCA connection error | url={url}")
            raise
        
        except Exception as e:
            logger.error(f"Unexpected error posting to ORCA | error={e}")
            raise
    
    def get_data(self, imo: int, date_from: str, date_to: str) -> Dict[str, Any]:
        """
        GET vessel data from ORCA (for debugging)
        
        Args:
            imo: Vessel IMO number
            date_from: Start date (ISO format)
            date_to: End date (ISO format)
            
        Returns:
            Vessel data from ORCA
        """
        url = f"{self.base_url}/data"
        headers = {
            "Content-Type": "application/json",
            "X-API-KEY": self.api_key,
            "X-Source": self.x_source,
            "X-Organization": self.x_organization
        }
        params = {
            "imo": imo,
            "dates[from]": date_from,
            "dates[to]": date_to
        }
        
        logger.info(f"Fetching from ORCA | imo={imo} | from={date_from} | to={date_to}")
        
        try:
            response = requests.get(
                url,
                params=params,
                headers=headers,
                timeout=self.timeout
            )
            response.raise_for_status()
            
            logger.info(f"ORCA GET response | status={response.status_code}")
            return response.json()
            
        except Exception as e:
            logger.error(f"Error fetching from ORCA | error={e}")
            raise
