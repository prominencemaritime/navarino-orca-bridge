#config/settings.py

from dataclasses import dataclass
from typing import Optional, List, Dict
from decouple import config
from pathlib import Path
import logging
import yaml

logger = logging.getLogger(__name__)

@dataclass
class VesselConfig:

    # Vessel identifiers
    ref_code: str
    imo: str
    infinity_base_url: str
    infinity_token: str


@dataclass
class BridgeConfig:

    # Project structure
    project_root: Path
    logs_dir: Path
    data_dir: Path

    # Bridge Operation Mode
    dry_run: bool

    # Infinity Web Services
    vessels: List[VesselConfig]

    # ORCA API
    orca_test: bool
    orca_base_url_test: str
    orca_base_url_live: str
    orca_x_api_key: str
    orca_x_source: str
    orca_x_organization: str

    # Scheduling
    sync_interval_minutes: int
    timezone: str

    # Logs
    log_file: Path
    log_level: str
    request_timeout: int
    debug: bool


    @property
    def orca_base_url(self) -> str:
        """Return appropriate ORCA URL based on test/live mode"""
        return self.orca_base_url_test if self.orca_test else self.orca_base_url_live


    @classmethod
    def from_env(cls, project_root: Optional[Path] = None) -> 'BridgeConfig':
        """
        Load configuration from environment variables

        Args:
            project_root: Override project root path (default: auto-detect)

        Returns:
            Bridge Config instance with all settings loaded
        """
        if project_root is None:
            # Assume this file is in config/, so project root is 1 level up
            project_root = Path(__file__).resolve().parent.parent

        # Directory Structure
        logs_dir = project_root / 'logs'
        data_dir = project_root / 'data'

        return cls(
            # Project Directories
            project_root=project_root,
            logs_dir=logs_dir,
            data_dir=data_dir,

            # Bridge Operation Mode
            dry_run=config('DRY_RUN', cast=bool, default=True),

            # This replaces the Infinity extractions
            vessels=cls._load_vessels_from_yaml(project_root / 'vessels.yaml'),

            # ORCA API
            orca_test=config('ORCA_TEST', default=True, cast=bool),
            orca_base_url_test=config('ORCA_BASE_URL_TEST'),
            orca_base_url_live=config('ORCA_BASE_URL_LIVE'),
            orca_x_api_key=config('ORCA_X_API_KEY'),
            orca_x_source=config('ORCA_X_SOURCE'),
            orca_x_organization=config('ORCA_X_ORGANIZATION'),

            # Scheduling
            sync_interval_minutes=int(config('SYNC_INTERVAL_MINUTES', default=5)),
            timezone=config('TIMEZONE', default='UTC'),

            # Logs
            log_file=logs_dir / config('LOG_FILE', default='bridge.log'),
            log_level=config('LOG_LEVEL', default='INFO'),
            request_timeout=config("REQUEST_TIMEOUT", default=30, cast=int),
            debug=config('DEBUG', default=False, cast=bool)
        )

    @classmethod
    def _load_vessels_from_yaml(cls, yaml_path: Path) -> List['VesselConfig']:
        """Load vessel configuration from vessels.yaml"""
        if not yaml_path.exists():
            raise FileNotFoundError(
                f"Vessel config file not found: {yaml_path}\n"
                f"Copy vessels.yaml.example to vessels.yaml and fill in your credentials."
            )
        with open(yaml_path) as f:
            data = yaml.safe_load(f)
        vessels = []
        for v in data.get('vessels', []):
            vessels.append(VesselConfig(
                ref_code=v['ref_code'],
                imo=str(v['imo']),
                infinity_base_url=v['infinity_base_url'],
                infinity_token=v['infinity_token']
            ))
        if not vessels:
            raise ValueError("No vessels defined in vessels.yaml")
        return vessels


    def validate(self) -> None:
        """Validate configuration values"""
        logger.info("Validating configuration...")
        
        # Ensure directories exist
        self.logs_dir.mkdir(exist_ok=True)
        self.data_dir.mkdir(exist_ok=True)

        # Infinity validation
        for vessel in self.vessels:
            if not vessel.infinity_base_url or not vessel.infinity_token:
                raise ValueError(f"Infinity credentials incomplete for vessel {vessel.ref_code}")
            if not (vessel.imo.isdigit() and len(vessel.imo) == 7):
                raise ValueError(f"Invalid IMO {vessel.imo} for vessel {vessel.ref_code}. IMO must be 7 digits.")

        vessel_count = len(self.vessels)
        ref_codes = [v.ref_code for v in self.vessels]
        logger.info(f"Vessels: {vessel_count} configured | {ref_codes}")

        # Validate URLs
        import re
        url_pattern = re.compile(r'^https?://')
        if not url_pattern.match(self.orca_base_url):
            raise ValueError("ORCA base URL must start with http:// or https://")
        
        # ORCA validation
        if not self.orca_x_api_key:
            logger.error("ORCA API key missing")
            raise ValueError("ORCA API key missing")
        
        mode = "TEST" if self.orca_test else "LIVE"
        if self.orca_test and not self.orca_base_url_test:
            logger.error("ORCA test mode enabled but test URL missing")
            raise ValueError("ORCA test mode enabled but test URL missing")
        if not self.orca_test and not self.orca_base_url_live:
            logger.error("ORCA live mode but live URL missing")
            raise ValueError("ORCA live mode but live URL missing")
        
        logger.info(f"ORCA: {mode} mode | {self.orca_base_url}")
        if not self.orca_test:
            logger.warning("ORCA LIVE mode - production changes will be made!")
        
        # Other settings
        logger.info(f"Sync: every {self.sync_interval_minutes}min | timezone={self.timezone}")
        logger.info(f"Logs: {self.log_level} | file={self.log_file.name}")

        # Operation mode
        mode = "DRY RUN" if self.dry_run else "LIVE MODE"
        logger.info(f"Operation: {mode}")
        if not self.dry_run:
            logger.warning("⚠️  DRY_RUN=False - Real data will be posted to ORCA")
        
        logger.info("Configuration validated successfully")
