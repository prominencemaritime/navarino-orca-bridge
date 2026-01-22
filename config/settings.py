#config/settings.py

from dataclasses import dataclass
from typing import Optional, List, Dict
from decouple import config
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

@dataclass
class BridgeConfig:

    # Project structure
    project_root: Path
    logs_dir: Path
    data_dir: Path

    # Bridge Operation Mode
    dry_run: bool

    # Email settings
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_pass: str
    enable_email_alert: bool
    email_routing: Dict[str, List[str]]

    # Infinity Web Services
    infinity_base_url: str
    infinity_token: str
    vessel_identifiers: Dict[str, int]

    # ORCA API
    orca_test: bool
    orca_base_url_test: str
    orca_base_url_live: str
    orca_x_api_key: str

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

        # Ensure directories exist
        logs_dir.mkdir(exist_ok=True)
        data_dir.mkdir(exist_ok=True)

        # Load email routing config if enabled
        enable_email_alert = config('ENABLE_EMAIL_ALERT', default=False, cast=bool)

        if enable_email_alert:
            email_routing = cls._load_email_routing()
            smtp_host=config('SMTP_HOST')
            smtp_port=config('SMTP_PORT', default=465, cast=int)
            smtp_user=config('SMTP_USER')
            smtp_pass=config('SMTP_PASS')
        else:
            email_routing = {'to': [], 'cc': []}
            smtp_host = smtp_user = smtp_pass = ''
            smtp_port = 465


        # Parse vessel ref codes and imos
        vessel_identifiers = cls._load_vessel_identifiers()

        return cls(
            # Project Directories
            project_root=project_root,
            logs_dir=logs_dir,
            data_dir=data_dir,

            # Bridge Operation Mode
            dry_run=config('DRY_RUN'),

            # Email Configuration
            smtp_host=smtp_host,
            smtp_port=smtp_port,
            smtp_user=smtp_user,
            smtp_pass=smtp_pass,
            enable_email_alert=enable_email_alert,
            email_routing=email_routing,    # {'to': [...], 'cc': [...]}

            # Infinity Web Services
            infinity_base_url=config('INFINITY_BASE_URL'),
            infinity_token=config('INFINITY_TOKEN'),
            vessel_identifiers=vessel_identifiers,  # {'vessel_ref_code': 'vessel_IMO', }

            # ORCA API
            orca_test=config('ORCA_TEST', default=True, cast=bool),
            orca_base_url_test=config('ORCA_BASE_URL_TEST'),
            orca_base_url_live=config('ORCA_BASE_URL_LIVE'),
            orca_x_api_key=config('ORCA_X_API_KEY'),

            # Scheduling
            sync_interval_minutes=int(config('SYNC_INTERVAL_MINUTES', default=5)),
            timezone=config('TIMEZONE', default='UTC'),

            # Logs
            log_file=logs_dir / config('LOG_FILE', default='bridge.log'),
            log_level=config('LOG_LEVEL', default='INFO'),
            request_timeout=config("REQUEST_TIMEOUT", default=30, cast=int),
            debug=config('DEBUG', default=False, cast=bool)
        )


    @staticmethod
    def _parse_email_list(env_var: str) -> List[str]:
        """Parse comma-separated email list from environment variable."""
        email_string = config(env_var, default='')
        if not email_string:
            return []
        return [email.strip() for email in config(env_var, default='').split(',') if email.strip()]


    @staticmethod
    def _load_email_routing() -> Dict[str, List[str]]:
        """Load and parse email routing from environment"""
        return {
            'to': BridgeConfig._parse_email_list('TO_RECIPIENTS'),
            'cc': BridgeConfig._parse_email_list('CC_RECIPIENTS')
        }

    @staticmethod
    def _parse_csv_env_entry(env_var: str) -> List[str]:
        """Parse comma-separated entry list from environment variable."""
        return [entry.strip() for entry in config(env_var).split(',') if entry.strip()]

    @staticmethod
    def _load_vessel_identifiers() -> Dict[str, int]:
        """Load vessel ref code to IMO Dict

        Returns dict:
            {
                'mountfu': 9509011,
                'other_vessel_ref_code': other_vessel_IMO,
                ...
            }
        """
        keys = BridgeConfig._parse_csv_env_entry('VESSEL_REF_CODE')
        values = BridgeConfig._parse_csv_env_entry('VESSEL_IMO')
        if len(keys) != len(values):
            logger.error("VESSEL_REF_CODE and VESSEL_IMO entries in .env have a different number of entries.")
            raise ValueError("There should be one vessel_ref_code for each IMO number, but the number of entries do not match.")
        return {key: int(value) for key, value in zip(keys, values)}


    def validate(self) -> None:
        """Validate configuration values"""
        logger.info("Validating configuration...")
        
        # Email validation
        if self.enable_email_alert:
            if not self.email_routing['to']:
                logger.error("Email alerts enabled but TO_RECIPIENTS missing")
                raise ValueError("Email alerts enabled but TO_RECIPIENTS missing")
            if not self.smtp_host or not self.smtp_user or not self.smtp_pass:
                logger.error("Email alerts enabled but SMTP credentials incomplete")
                raise ValueError("Email alerts enabled but SMTP credentials incomplete")
            logger.info(f"Email: {len(self.email_routing['to'])} TO, {len(self.email_routing['cc'])} CC | {self.smtp_host}:{self.smtp_port}")
        else:
            logger.info("Email: disabled")
        
        # Infinity validation
        if not self.infinity_base_url or not self.infinity_token:
            logger.error("Infinity credentials incomplete")
            raise ValueError("Infinity credentials incomplete")
        logger.info(f"Infinity: {self.infinity_base_url} | vessel{'' if len(self.vessel_identifiers)==1 else 's'}={self.vessel_identifiers.keys()}")

        # IMO Validation (should be 7 digits)
        for ref_code, imo in self.vessel_identifiers.items():
            if not (1000000 <= imo <= 9999999):
                raise ValueError(f"Invalid IMO {imo} for vessel {ref_code}. IMO must be 7 digits long.")

        # Validate URLs
        import re
        url_pattern = re.compile(r'^https?://')
        if not url_pattern.match(self.infinity_base_url):
            raise ValueError("Infinity base URL must start with http:// or https://")
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


# Singleton instance
_config_instance: Optional[BridgeConfig] = None


def get_config() -> BridgeConfig:
    """Get or create singleton configuration instance"""
    global _config_instance
    if _config_instance is None:
        _config_instance = BridgeConfig.from_env()

        # Setup logging before validation
        from config.logging_config import setup_logging
        setup_logging(_config_instance.log_file, _config_instance.log_level)

        _config_instance.validate()
    return _config_instance
