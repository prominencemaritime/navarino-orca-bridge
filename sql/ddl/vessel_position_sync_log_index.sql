CREATE INDEX vessel_position_sync_log_imo_logged_idx
    ON external.vessel_position_sync_log (imo, logged_at DESC);

CREATE INDEX vessel_position_sync_log_provider_logged_idx
    ON external.vessel_position_sync_log (provider, logged_at DESC);
