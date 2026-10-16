from datetime import datetime, timezone

from odoo import api, fields, models


class SmsMobileApiMobile(models.Model):
    _name = "smsmobileapi.mobile"
    _description = "SMSMobileAPI Mobile Gateway"
    _order = "is_online desc, name, id"
    _check_company_auto = True

    name = fields.Char(required=True)
    sid = fields.Char(required=True, index=True, readonly=True)
    phone_number = fields.Char(readonly=True)
    is_online = fields.Boolean(readonly=True)
    app_version = fields.Char(readonly=True)
    battery_level = fields.Integer(readonly=True)
    last_seen_at = fields.Datetime(readonly=True)
    permission_sms_received = fields.Selection(
        [("unknown", "Not reported"), ("granted", "Allowed"), ("missing", "Not allowed")],
        string="Received SMS", default="unknown", readonly=True,
    )
    permission_call_missed = fields.Selection(
        [("unknown", "Not reported"), ("granted", "Allowed"), ("missing", "Not allowed")],
        string="Missed calls", default="unknown", readonly=True,
    )
    permission_call_incoming = fields.Selection(
        [("unknown", "Not reported"), ("granted", "Allowed"), ("missing", "Not allowed")],
        string="Incoming calls", default="unknown", readonly=True,
    )
    permission_call_outgoing = fields.Selection(
        [("unknown", "Not reported"), ("granted", "Allowed"), ("missing", "Not allowed")],
        string="Outgoing calls", default="unknown", readonly=True,
    )
    permission_checked_at = fields.Datetime(string="Permissions checked at", readonly=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company,
        ondelete="cascade", index=True,
    )
    config_id = fields.Many2one(
        "smsmobileapi.config", required=True, ondelete="cascade", check_company=True, index=True,
    )

    _sql_constraints = [
        ("company_sid_unique", "unique(company_id, sid)", "This mobile is already registered for the company."),
    ]

    @api.model
    def _extract_rows(self, payload):
        if not isinstance(payload, dict):
            return []
        result = payload.get("result")
        containers = [payload, result] if isinstance(result, dict) else [payload]
        for container in containers:
            for key in ("items", "mobiles", "mobile", "devices", "gateways", "data", "rows"):
                value = container.get(key)
                if isinstance(value, list):
                    return value
                if isinstance(value, dict):
                    return [value]
        if isinstance(result, list):
            return result
        return []

    @api.model
    def _sync_from_payload(self, config, payload):
        config.ensure_one()
        rows = self._extract_rows(payload)
        seen = set()
        for row in rows:
            if not isinstance(row, dict):
                continue
            sid = str(
                row.get("sid") or row.get("sIdentifiant") or row.get("sIdentifiantPhone")
                or row.get("device_id") or ""
            ).strip()
            if not sid:
                continue
            seen.add(sid)
            label = str(row.get("label") or row.get("name") or row.get("device_name") or sid)
            last_check = row.get("last_check") if isinstance(row.get("last_check"), dict) else {}
            online_value = row.get(
                "online",
                row.get("is_online", row.get("connected", last_check.get("status", False))),
            )
            vals = {
                "name": label[:128],
                "phone_number": str(row.get("phone_number") or row.get("number") or "")[:64],
                "is_online": str(online_value).lower() in {
                    "1", "true", "yes", "online", "connected", "green",
                },
                "app_version": str(row.get("app_version") or row.get("version") or "")[:64],
                "battery_level": self._safe_int(
                    row.get("battery_percent", row.get("battery") or row.get("battery_level"))
                ),
                "last_seen_at": self._last_seen_at(row, last_check),
                "active": True,
            }
            mobile = self.sudo().search([
                ("company_id", "=", config.company_id.id), ("sid", "=", sid)
            ], limit=1)
            if mobile:
                mobile.write(vals)
            else:
                vals.update({"sid": sid, "company_id": config.company_id.id, "config_id": config.id})
                self.sudo().create(vals)
        if seen:
            self.sudo().search([
                ("config_id", "=", config.id), ("sid", "not in", list(seen))
            ]).write({"active": False, "is_online": False})
        return len(seen)

    @api.model
    def _sync_permission_statuses(self, config, rows):
        config.ensure_one()
        mobiles = self.sudo().search([("config_id", "=", config.id), ("active", "=", True)])
        mobiles.write({
            "permission_sms_received": "unknown",
            "permission_call_missed": "unknown",
            "permission_call_incoming": "unknown",
            "permission_call_outgoing": "unknown",
            "permission_checked_at": False,
        })
        updated = 0
        by_sid = {mobile.sid: mobile for mobile in mobiles}
        for row in rows if isinstance(rows, list) else []:
            if not isinstance(row, dict):
                continue
            sid = str(row.get("device_id") or "").strip()
            mobile = by_sid.get(sid)
            if not mobile:
                continue
            vals = {
                "permission_sms_received": self._permission_value(row, "sms_received_granted"),
                "permission_call_missed": self._permission_value(row, "call_missed_granted"),
                "permission_call_incoming": self._permission_value(row, "call_incoming_granted"),
                "permission_call_outgoing": self._permission_value(row, "call_outgoing_granted"),
                "permission_checked_at": self._permission_datetime(row.get("checked_at")),
            }
            app_version = str(row.get("app_version") or "").strip()
            if app_version:
                vals["app_version"] = app_version[:64]
            mobile.write(vals)
            updated += 1
        return updated, len(mobiles)

    @api.model
    def _permission_value(self, row, key):
        if key not in row or row.get(key) is None:
            return "unknown"
        granted = str(row.get(key)).strip().lower() in {"1", "true", "yes", "on"}
        return "granted" if granted else "missing"

    @api.model
    def _permission_datetime(self, value):
        if not value:
            return False
        try:
            return fields.Datetime.to_datetime(str(value).replace("T", " ").replace("Z", ""))
        except (TypeError, ValueError):
            return False

    @api.model
    def _last_seen_at(self, row, last_check):
        timestamp = (
            last_check.get("last_connexion_ok_time")
            or row.get("last_seen_timestamp")
            or row.get("last_seen_at")
        )
        try:
            if timestamp not in (None, ""):
                return datetime.fromtimestamp(float(timestamp), tz=timezone.utc).replace(tzinfo=None)
        except (OSError, OverflowError, TypeError, ValueError):
            pass

        date_value = str(last_check.get("date") or "").strip()
        time_value = str(last_check.get("time") or "").strip()
        if date_value:
            try:
                return fields.Datetime.to_datetime(
                    "%s %s" % (date_value, time_value or "00:00:00")
                )
            except (TypeError, ValueError):
                pass
        return False

    @api.model
    def _safe_int(self, value):
        try:
            parsed = int(float(value))
        except (TypeError, ValueError):
            return 0
        return max(0, min(parsed, 100))
