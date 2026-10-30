# src/db/datalab.py
"""
Datalab (RDS PostgreSQL) connection for the bridge.

Adapted from the risk engine's db/connections/datalab.py. Same IAM
authentication (fresh token per physical connection) and verify-full SSL.
Differences:
  - no search_path: the bridge only touches schema-qualified tables
  - short connect and statement timeouts, so a slow datalab can never
    stall a sync cycle
  - small pool: one sequential writer
"""

import logging
from contextlib import contextmanager

import boto3
from decouple import config
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

DB_HOST     = config("DB_DATALAB_HOST")
DB_PORT     = config("DB_DATALAB_PORT", cast=int)
DB_NAME     = config("DB_DATALAB_NAME")
DB_USER     = config("DB_DATALAB_USER")
DB_REGION   = config("DB_DATALAB_REGION")
DB_SSL_CERT = config("DB_DATALAB_SSL_CERT")

DB_CONNECT_TIMEOUT_S    = config("DB_DATALAB_CONNECT_TIMEOUT", default=5, cast=int)
DB_STATEMENT_TIMEOUT_MS = config("DB_DATALAB_STATEMENT_TIMEOUT_MS", default=5000, cast=int)


def _get_iam_token() -> str:
    """Generate a short-lived (15 min) IAM auth token for RDS."""
    client = boto3.client("rds", region_name=DB_REGION)
    return client.generate_db_auth_token(
        DBHostname=DB_HOST,
        Port=DB_PORT,
        DBUsername=DB_USER,
    )


def _make_engine() -> Engine:
    engine = create_engine(
        f"postgresql+psycopg2://{DB_USER}@{DB_HOST}:{DB_PORT}/{DB_NAME}",
        connect_args={
            "sslmode":          "verify-full",
            "sslrootcert":      DB_SSL_CERT,
            "connect_timeout":  DB_CONNECT_TIMEOUT_S,
            "application_name": "navarino-orca-bridge",
            "options":          f"-c statement_timeout={DB_STATEMENT_TIMEOUT_MS}",
        },
        pool_size=1,
        max_overflow=1,
        pool_pre_ping=True,
        pool_recycle=840,   # 14 min, token TTL is 15 min
    )

    @event.listens_for(engine, "do_connect")
    def provide_iam_token(dialect, conn_rec, cargs, cparams):
        cparams["password"] = _get_iam_token()

    return engine


_engine: Engine | None = None


def _get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = _make_engine()
    return _engine


@contextmanager
def get_db_transaction():
    """Transactional connection: commits on clean exit, rolls back on error."""
    with _get_engine().begin() as conn:
        yield conn


def check_db_connection() -> bool:
    """Return True if datalab is reachable. Logs the reason if not."""
    try:
        with _get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(f"datalab connection check failed | error={e}")
        return False
