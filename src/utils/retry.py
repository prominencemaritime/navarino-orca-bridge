# src/utils/retry.py

import time
import logging
from functools import wraps
from typing import Callable, TypeVar, Any
import requests

logger = logging.getLogger(__name__)

T = TypeVar('T')


def retry_with_backoff(
    max_retries: int = 3,
    backoff_factor: float = 2.0,
    retry_on_status_codes: tuple = (500, 502, 503, 504)
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator for retry logic with exponential backoff
    
    Args:
        max_retries: Maximum number of retry attempts (default: 3)
        backoff_factor: Multiplier for exponential backoff (default: 2.0)
        retry_on_status_codes: HTTP status codes to retry on (default: 5xx errors)
    
    Returns:
        Decorated function with retry logic
    
    Example:
        @retry_with_backoff(max_retries=3, backoff_factor=2)
        def fetch_data():
            response = requests.get(url)
            response.raise_for_status()
            return response.json()
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception = None
            
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                
                except (requests.exceptions.Timeout, 
                        requests.exceptions.ConnectionError) as e:
                    last_exception = e
                    
                    if attempt == max_retries - 1:
                        logger.error(f"Max retries ({max_retries}) reached for {func.__name__}")
                        raise
                    
                    wait_time = backoff_factor ** attempt
                    logger.warning(
                        f"{func.__name__} | Attempt {attempt + 1}/{max_retries} failed | "
                        f"Retrying in {wait_time}s | Error: {type(e).__name__}: {e}"
                    )
                    time.sleep(wait_time)
                
                except requests.exceptions.HTTPError as e:
                    last_exception = e
                    
                    # Only retry on specific status codes (default: 5xx)
                    if (hasattr(e, 'response') and 
                        e.response is not None and
                        e.response.status_code in retry_on_status_codes and 
                        attempt < max_retries - 1):
                        
                        wait_time = backoff_factor ** attempt
                        logger.warning(
                            f"{func.__name__} | HTTP {e.response.status_code} | "
                            f"Attempt {attempt + 1}/{max_retries} | "
                            f"Retrying in {wait_time}s"
                        )
                        time.sleep(wait_time)
                    else:
                        # Don't retry on 4xx errors or if max retries reached
                        logger.error(
                            f"{func.__name__} | HTTP error {e.response.status_code if hasattr(e, 'response') else 'unknown'} | "
                            f"Not retrying"
                        )
                        raise
            
            # This should never be reached, but just in case
            if last_exception:
                raise last_exception
            
        return wrapper
    return decorator
