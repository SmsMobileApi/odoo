import hashlib
import hmac
import logging
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


_logger = logging.getLogger(__name__)

PRODUCTION_API_BASE_URL = "https://api.smsmobileapi.com/"
DATA_CONSENT_VERSION = "1.0"


class SmsMobileApiConfig(models.Model):
    _name = "smsmobileapi.config"
    _description = "SMSMobileAPI Configuration"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _rec_name = "company_id"
    _check_company_auto = True

    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company,
        ondelete="cascade", index=True, tracking=True,
    )
    active = fields.Boolean(default=True, tracking=True)
    api_base_url = fields.Char(
        required=True, default=PRODUCTION_API_BASE_URL,
        groups="sms_mobile_api_call.group_smsmobileapi_manager",
    )
    api_key = fields.Char(required=True, copy=False, groups="sms_mobile_api_call.group_smsmobileapi_manager")
    external_data_consent = fields.Boolean(
        string="I authorize the SMSMobileAPI data exchange",
        default=False,
        tracking=True,
        help=(
            "Required before Odoo can send or retrieve SMS, call, mobile or permission data "
            "through api.smsmobileapi.com."
        ),
    )
    external_data_consent_at = fields.Datetime(
        string="Consent recorded at", readonly=True, copy=False,
    )
    external_data_consent_user_id = fields.Many2one(
        "res.users", string="Consent recorded by", readonly=True, copy=False,
    )
    external_data_consent_version = fields.Char(
        string="Consent version", readonly=True, copy=False,
    )
    default_mobile_id = fields.Many2one(
        "smsmobileapi.mobile", domain="[('company_id', '=', company_id), ('active', '=', True)]",
        check_company=True, tracking=True,
    )
    connection_state = fields.Selection(
        [("not_tested", "Not tested"), ("connected", "Connected"), ("error", "Needs attention")],
        default="not_tested", readonly=True, tracking=True,
    )
    last_connection_test_at = fields.Datetime(readonly=True)
    last_sync_at = fields.Datetime(readonly=True)
    last_sync_status = fields.Selection(
        [("never", "Never"), ("ok", "Successful"), ("partial", "Partial"), ("error", "Failed")],
        default="never", readonly=True,
    )
    last_sync_message = fields.Char(readonly=True)
    last_permission_refresh_at = fields.Datetime(readonly=True)
    mobile_ids = fields.One2many("smsmobileapi.mobile", "config_id", string="Connected mobiles")
    sync_interval_minutes = fields.Integer(default=5, required=True)
    sync_lookback_days = fields.Integer(default=7, required=True)
    auto_sync = fields.Boolean(default=False)
    import_received_sms = fields.Boolean(default=True)
    import_api_sent_sms = fields.Boolean(default=True)
    import_mobile_sent_sms = fields.Boolean(default=True)
    import_missed_calls = fields.Boolean(default=True)
    import_incoming_calls = fields.Boolean(default=True)
    import_outgoing_calls = fields.Boolean(default=True)
    webhook_enabled = fields.Boolean(default=False, tracking=True)
    webhook_path_token = fields.Char(copy=False, readonly=True, groups="sms_mobile_api_call.group_smsmobileapi_manager")
    webhook_signing_secret = fields.Char(copy=False, groups="sms_mobile_api_call.group_smsmobileapi_manager")
    webhook_url = fields.Char(compute="_compute_webhook_url")

    _sql_constraints = [
        ("company_unique", "unique(company_id)", "Only one SMSMobileAPI configuration is allowed per company."),
    ]

    @api.constrains("api_base_url")
    def _constrain_api_base_url(self):
        for record in self:
            record._check_api_base_url()

    @api.constrains("sync_interval_minutes")
    def _constrain_sync_interval(self):
        for record in self:
            if record.sync_interval_minutes < 2 or record.sync_interval_minutes > 1440:
                raise ValidationError(_("The synchronization interval must be between 2 and 1,440 minutes."))

    @api.constrains("sync_lookback_days")
    def _constrain_sync_lookback(self):
        for record in self:
            if record.sync_lookback_days < 1 or record.sync_lookback_days > 7:
                raise ValidationError(_("The synchronization window must be between 1 and 7 days."))

    def _check_api_base_url(self):
        for record in self:
            parsed = urlparse((record.api_base_url or "").strip())
            host = (parsed.hostname or "").lower()
            is_local = host in {"localhost", "127.0.0.1", "::1"}
            if parsed.scheme != "https" and not (is_local and parsed.scheme == "http"):
                raise ValidationError(_("The API URL must use HTTPS."))
            if not host:
                raise ValidationError(_("Enter a valid SMSMobileAPI URL."))
            if not is_local and host != "api.smsmobileapi.com":
                raise ValidationError(_("For security, the API host must be api.smsmobileapi.com."))
            if parsed.username or parsed.password or parsed.query or parsed.fragment:
                raise ValidationError(_("The API base URL cannot contain credentials, parameters or a fragment."))

    @api.depends("webhook_path_token")
    def _compute_webhook_url(self):
        base = self.env["ir.config_parameter"].sudo().get_param("web.base.url", "").rstrip("/")
        for record in self:
            record.webhook_url = (
                "%s/smsmobileapi/webhook/%s" % (base, record.webhook_path_token)
                if base and record.webhook_path_token else False
            )

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su and not self.env.user.has_group("sms_mobile_api_call.group_smsmobileapi_manager"):
            raise AccessError(_("Only an SMSMobileAPI manager can configure the connection."))
        for vals in vals_list:
            # The endpoint is deliberately server-controlled. Users only need
            # their account API key and cannot redirect credentials elsewhere.
            vals["api_base_url"] = PRODUCTION_API_BASE_URL
            vals.setdefault("webhook_path_token", secrets.token_urlsafe(24))
            vals.setdefault("webhook_signing_secret", secrets.token_urlsafe(32))
            if vals.get("external_data_consent"):
                vals.update({
                    "external_data_consent_at": fields.Datetime.now(),
                    "external_data_consent_user_id": self.env.user.id,
                    "external_data_consent_version": DATA_CONSENT_VERSION,
                })
            elif vals.get("auto_sync") or vals.get("webhook_enabled"):
                raise ValidationError(_(
                    "Accept the SMSMobileAPI data disclosure before enabling synchronization or webhooks."
                ))
        return super().create(vals_list)

    def write(self, vals):
        protected = {"api_key", "api_base_url", "webhook_signing_secret", "webhook_path_token"}
        if protected.intersection(vals) and not self.env.su and not self.env.user.has_group("sms_mobile_api_call.group_smsmobileapi_manager"):
            raise AccessError(_("Only an SMSMobileAPI manager can change connection secrets."))
        if "api_base_url" in vals and vals.get("api_base_url") != PRODUCTION_API_BASE_URL:
            raise ValidationError(_("The SMSMobileAPI production endpoint cannot be changed."))
        api_key_changed = (
            "api_key" in vals
            and any(record.api_key != vals.get("api_key") for record in self)
        )
        if api_key_changed and vals.get("external_data_consent") is not True:
            vals.update({
                "external_data_consent": False,
                "external_data_consent_at": False,
                "external_data_consent_user_id": False,
                "external_data_consent_version": False,
                "auto_sync": False,
                "webhook_enabled": False,
            })
        elif vals.get("external_data_consent") is True:
            vals.update({
                "external_data_consent_at": fields.Datetime.now(),
                "external_data_consent_user_id": self.env.user.id,
                "external_data_consent_version": DATA_CONSENT_VERSION,
            })
        elif vals.get("external_data_consent") is False:
            vals.update({
                "external_data_consent_at": False,
                "external_data_consent_user_id": False,
                "external_data_consent_version": False,
                "auto_sync": False,
                "webhook_enabled": False,
            })
        effective_consent = vals.get("external_data_consent") is True or (
            "external_data_consent" not in vals and all(self.mapped("external_data_consent"))
        )
        if (vals.get("auto_sync") or vals.get("webhook_enabled")) and not effective_consent:
            raise ValidationError(_(
                "Accept the SMSMobileAPI data disclosure before enabling synchronization or webhooks."
            ))
        return super().write(vals)

    def _ensure_external_data_consent(self):
        for record in self:
            if not record.external_data_consent:
                raise UserError(_(
                    "Data sharing is not authorized yet. Open SMSMobileAPI Configuration, read the "
                    "data disclosure and actively accept it before using connection, SMS, call or "
                    "mobile synchronization features."
                ))
        return True

    @api.model
    def _smsmobileapi_configuration_action(self, config=False):
        """Open the current company's configuration directly in edit mode."""
        action = self.env["ir.actions.actions"]._for_xml_id(
            "sms_mobile_api_call.action_smsmobileapi_config"
        )
        form_view = self.env.ref("sms_mobile_api_call.view_smsmobileapi_config_form")
        action.update({
            "view_mode": "form",
            "views": [(form_view.id, "form")],
            "target": "current",
            "context": dict(
                self.env.context,
                default_company_id=self.env.company.id,
                form_view_initial_mode="edit",
                smsmobileapi_consent_required=True,
            ),
        })
        if config:
            action["res_id"] = config.id
        else:
            action.pop("res_id", None)
        return action

    @api.model
    def action_open_smsmobileapi_menu(self, target_xmlid=False):
        """Route every SMSMobileAPI menu through the consent checkpoint."""
        config = self.with_context(active_test=False).sudo().search([
            ("company_id", "=", self.env.company.id),
        ], limit=1)
        is_authorized = bool(config and config.active and config.external_data_consent)
        if not is_authorized:
            if not self.env.su and not self.env.user.has_group("sms_mobile_api_call.group_smsmobileapi_manager"):
                raise UserError(_(
                    "SMSMobileAPI data exchange has not been authorized for this company yet. "
                    "Ask an SMSMobileAPI manager to open Configuration and accept the required authorization."
                ))
            return self._smsmobileapi_configuration_action(config=config)

        target_xmlid = target_xmlid or "sms_mobile_api_call.action_smsmobileapi_conversation"
        return self.env["ir.actions.actions"]._for_xml_id(target_xmlid)

    def unlink(self):
        if not self.env.su and not self.env.user.has_group("sms_mobile_api_call.group_smsmobileapi_manager"):
            raise AccessError(_("Only an SMSMobileAPI manager can remove a connection."))
        return super().unlink()

    def action_rotate_webhook_secret(self):
        self.ensure_one()
        if not self.env.su and not self.env.user.has_group("sms_mobile_api_call.group_smsmobileapi_manager"):
            raise AccessError(_("Only an SMSMobileAPI manager can rotate webhook credentials."))
        self.write({
            "webhook_path_token": secrets.token_urlsafe(24),
            "webhook_signing_secret": secrets.token_urlsafe(32),
        })
        return self._notification(_("Webhook credentials rotated"), _("Update the destination in SMSMobileAPI before enabling the webhook."))

    def action_test_connection(self):
        self.ensure_one()
        if not self.env.su and not self.env.user.has_group("sms_mobile_api_call.group_smsmobileapi_manager"):
            raise AccessError(_("Only an SMSMobileAPI manager can test the connection."))
        self._ensure_external_data_consent()
        now = fields.Datetime.now()
        try:
            payload = self.env["smsmobileapi.client"].get(
                self, "/gateway/mobile/list/", operation=_("connection test")
            )
            count = self.env["smsmobileapi.mobile"]._sync_from_payload(self, payload)
            self.write({"connection_state": "connected", "last_connection_test_at": now})
            return self._notification(_("Connection successful"), _("%(count)s mobile gateway(s) synchronized.", count=count))
        except UserError:
            self.write({"connection_state": "error", "last_connection_test_at": now})
            raise

    def action_sync_now(self):
        self.ensure_one()
        if not self.env.su and not self.env.user.has_group("sms_mobile_api_call.group_smsmobileapi_user"):
            raise AccessError(_("You are not allowed to synchronize SMSMobileAPI."))
        self._ensure_external_data_consent()
        result = self._sync_all()
        return self._notification(_("Synchronization complete"), result)

    def action_refresh_mobile_permissions(self):
        self.ensure_one()
        if not self.env.su and not self.env.user.has_group("sms_mobile_api_call.group_smsmobileapi_manager"):
            raise AccessError(_("Only an SMSMobileAPI manager can refresh mobile permissions."))
        self._ensure_external_data_consent()
        rows = self.env["smsmobileapi.client"].mobile_permission_statuses(self)
        updated, total = self.env["smsmobileapi.mobile"]._sync_permission_statuses(self, rows)
        self.write({"last_permission_refresh_at": fields.Datetime.now()})
        if not rows:
            return self._notification(
                _("No permission report yet"),
                _("Open SMSMobileAPI on the mobile, verify the SMS and call access, then refresh again."),
                "warning",
            )
        return self._notification(
            _("Mobile permissions refreshed"),
            _("%(updated)s of %(total)s connected mobile(s) updated.", updated=updated, total=total),
        )

    def _notification(self, title, message, notification_type="success"):
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {"title": title, "message": message, "type": notification_type, "sticky": False},
        }

    @api.model
    def _cron_sync(self):
        now = fields.Datetime.now()
        configs = self.sudo().search([
            ("active", "=", True),
            ("auto_sync", "=", True),
            ("external_data_consent", "=", True),
        ])
        for config in configs:
            due_at = config.last_sync_at + timedelta(minutes=config.sync_interval_minutes) if config.last_sync_at else False
            if due_at and due_at > now:
                continue
            try:
                config._sync_all()
            except Exception:
                _logger.exception("SMSMobileAPI synchronization failed for company %s", config.company_id.id)

    def _sync_all(self):
        self.ensure_one()
        self._ensure_external_data_consent()
        started = fields.Datetime.now()
        messages = []
        errors = []
        try:
            mobile_payload = self.env["smsmobileapi.client"].get(self, "/gateway/mobile/list/", operation=_("mobile synchronization"))
            mobile_count = self.env["smsmobileapi.mobile"]._sync_from_payload(self, mobile_payload)
            messages.append(_("%(count)s mobile gateway(s)", count=mobile_count))
        except Exception as exc:
            errors.append(_("mobiles"))
            _logger.warning("SMSMobileAPI mobile synchronization failed for company %s: %s", self.company_id.id, exc.__class__.__name__)

        jobs = [
            (self.import_received_sms, "received_sms", self.env["smsmobileapi.activity"]._sync_received_sms),
            (self.import_api_sent_sms, "api_sent_sms", self.env["smsmobileapi.activity"]._sync_api_sent_sms),
            (self.import_mobile_sent_sms, "sent_sms", self.env["smsmobileapi.activity"]._sync_mobile_sent_sms),
            (self.import_missed_calls, "missed_calls", self.env["smsmobileapi.activity"]._sync_missed_calls),
            (self.import_incoming_calls, "incoming_calls", self.env["smsmobileapi.activity"]._sync_incoming_calls),
            (self.import_outgoing_calls, "outgoing_calls", self.env["smsmobileapi.activity"]._sync_outgoing_calls),
        ]
        for enabled, label, callback in jobs:
            if not enabled:
                continue
            try:
                count = callback(self)
                messages.append(_("%(count)s %(label)s", count=count, label=label.replace("_", " ")))
            except Exception as exc:
                errors.append(label)
                _logger.warning("SMSMobileAPI %s synchronization failed for company %s: %s", label, self.company_id.id, exc.__class__.__name__)

        state = "partial" if errors and messages else ("error" if errors else "ok")
        detail = ", ".join(messages) if messages else _("No data imported")
        if errors:
            detail = _("%(detail)s. Check: %(errors)s", detail=detail, errors=", ".join(errors))
        self.write({
            "last_sync_at": started,
            "last_sync_status": state,
            "last_sync_message": detail[:255],
            "connection_state": "connected" if state != "error" else "error",
        })
        return detail

    def _verify_webhook_signature(self, raw_body, timestamp, signature):
        self.ensure_one()
        if not self.webhook_enabled or not self.webhook_signing_secret:
            return False
        try:
            sent_at = int(timestamp)
        except (TypeError, ValueError):
            return False
        now = int(datetime.now(timezone.utc).timestamp())
        if abs(now - sent_at) > 300:
            return False
        signed = (str(sent_at) + ".").encode("utf-8") + raw_body
        expected = "v1=" + hmac.new(
            self.webhook_signing_secret.encode("utf-8"), signed, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature or "")
