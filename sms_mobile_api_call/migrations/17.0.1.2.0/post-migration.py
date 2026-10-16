def migrate(cr, version):
    """Require a fresh, auditable opt-in after installing the disclosure."""
    cr.execute(
        """
        UPDATE smsmobileapi_config
           SET external_data_consent = FALSE,
               external_data_consent_at = NULL,
               external_data_consent_user_id = NULL,
               external_data_consent_version = NULL,
               auto_sync = FALSE,
               webhook_enabled = FALSE
        """
    )
