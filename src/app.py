# src/app.py
"""Application bootstrap for Navarino ORCA Bridge"""

import logging
from dataclasses import dataclass
from typing import Optional, Dict


from config.settings import BridgeConfig, VesselConfig
from config.logging_config import setup_logging
from src.clients.infinity import InfinityWebServiceClient
from src.clients.orca import ORCAClient
from src.bridge import InfinityORCABridge

logger = logging.getLogger(__name__)


@dataclass
class AppContext:
    """
    Application context holding all initialised components.

    Created once at startup and passed to all jobs/functions.
    Thread-safe because it is immutable after construction.
    """
    config: BridgeConfig
    infinity_clients: Dict[str, InfinityWebServiceClient]
    orca_client: ORCAClient
    bridge: InfinityORCABridge


def initialise_app() -> AppContext:
    """
    Initialise application components exactly once.

    This is the only place where:
    - Configuration is loaded
    - Logging is configured
    - Clients are created

    Returns:
        AppContext with all components ready to use
    """
    # Step 1: Load configuration
    config = BridgeConfig.from_env()

    # Step 2: Setup logging (before validation so validation logs work)
    setup_logging(
        log_file=config.log_file,
        log_level=config.log_level
    )

    # Step 3: Validate configuration
    config.validate()

    # Step 4: Initialise clients (once, reused across all jobs)
    logger.info("Initialising API clients")

    infinity_clients = {
        vessel.ref_code: InfinityWebServiceClient(
            base_url=vessel.infinity_base_url,
            token=vessel.infinity_token,
            timeout=config.request_timeout
        )
        for vessel in config.vessels
    }

    orca_client = ORCAClient(
        base_url=config.orca_base_url,
        api_key=config.orca_x_api_key,
        x_source=config.orca_x_source,
        x_organization=config.orca_x_organization,
        timeout=config.request_timeout
    )

    # Step 5: Initialise bridge
    bridge = InfinityORCABridge(
            infinity_clients,
            orca_client,
            timezone=config.timezone,
            logs_dir=config.logs_dir
    )

    logger.info("Application initialised successfully")

    return AppContext(
        config=config,
        infinity_clients=infinity_clients,
        orca_client=orca_client,
        bridge=bridge
    )
