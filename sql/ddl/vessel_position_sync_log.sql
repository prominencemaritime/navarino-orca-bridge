-- sql/ddl/vessel_position_sync_log.sql
CREATE TABLE external.vessel_position_sync_log (
    id              SERIAL          PRIMARY KEY,
    logged_at       TIMESTAMP       WITH TIME ZONE NOT NULL DEFAULT NOW(),
    vessel_name     VARCHAR         NOT NULL,
    imo             VARCHAR         NOT NULL,
    provider        VARCHAR         NOT NULL,
    source_host     VARCHAR,
    interface       VARCHAR,
    position_ts     TIMESTAMP       WITH TIME ZONE,
    lat             DOUBLE PRECISION,
    lon             DOUBLE PRECISION,
    course          REAL,           -- stored as sent; -1 means "no course"
    speed_og        REAL,
    outcome         VARCHAR         NOT NULL
                    CHECK (outcome IN ('posted', 'fetch_failed',
                                       'parse_failed', 'post_failed')),
    orca_status     INTEGER,
    orca_response   TEXT,
    error           TEXT,
    duration_ms     INTEGER,
    payload         JSONB
);
