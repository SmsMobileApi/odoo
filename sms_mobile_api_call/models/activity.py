import hashlib
import json
import re
from datetime import datetime, timedelta, timezone

from markupsafe import Markup, escape

from odoo import _, api, fields, models
from odoo.exceptions import AccessError


class SmsMobileApiActivity(models.Model):
    _name = "smsmobileapi.activity"
    _description = "SMSMobileAPI Activity"
    _order = "activity_at desc, id desc"
    _check_company_auto = True

    name = fields.Char(compute="_compute_name", store=True)
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company,
        ondelete="cascade", index=True,
    )
    config_id = fields.Many2one(
        "smsmobileapi.config", required=True, ondelete="cascade", check_company=True, index=True,
    )
    partner_id = fields.Many2one("res.partner", ondelete="set null", check_company=True, index=True)
    mobile_id = fields.Many2one("smsmobileapi.mobile", ondelete="set null", check_company=True, index=True)
    conversation_id = fields.Many2one(
        "smsmobileapi.conversation", ondelete="set null", check_company=True, index=True,
    )
    event_type = fields.Selection([
        ("sms", "SMS"),
        ("call_missed", "Missed call"),
        ("call_incoming", "Incoming call"),
        ("call_outgoing", "Outgoing call"),
    ], required=True, index=True)
    direction = fields.Selection([
        ("incoming", "Incoming"),
        ("outgoing", "Outgoing"),
    ], required=True, index=True)
    source = fields.Selection([
        ("odoo", "Sent from Odoo"),
        ("api", "SMSMobileAPI API"),
        ("mobile", "Connected mobile"),
        ("webhook", "Webhook V2"),
    ], required=True, default="api", index=True)
    phone_number = fields.Char(required=True, index=True)
    phone_normalized = fields.Char(required=True, index=True)
    message = fields.Text()
    activity_at = fields.Datetime(required=True, default=fields.Datetime.now, index=True)
    duration_seconds = fields.Integer()
    external_ref = fields.Char(required=True, index=True)
    status = fields.Selection([
        ("queued", "Queued"),
        ("sent", "Sent"),
        ("delivered", "Delivered"),
        ("received", "Received"),
        ("completed", "Completed"),
        ("missed", "Missed"),
        ("error", "Error"),
    ], required=True, default="completed", index=True)
    error_message = fields.Char()
    is_read = fields.Boolean(default=True, index=True)
    document_model = fields.Char(index=True)
    document_id = fields.Integer(index=True)
    crm_lead_id = fields.Many2one("crm.lead", string="Opportunity", ondelete="set null", check_company=True)
    project_task_id = fields.Many2one("project.task", string="Task", ondelete="set null", check_company=True)
    followup_activity_id = fields.Many2one("mail.activity", string="Follow-up", ondelete="set null")
    support_ticket_id = fields.Many2one(
        "smsmobileapi.support.ticket", string="Support ticket", ondelete="set null", check_company=True,
    )
    sale_order_id = fields.Many2one(
        "sale.order", string="Quotation / Sales order", ondelete="set null", check_company=True,
    )
    invoice_id = fields.Many2one(
        "account.move", string="Invoice", ondelete="set null", check_company=True,
        domain="[('move_type', 'in', ('out_invoice', 'out_refund'))]",
    )

    _sql_constraints = [
        (
            "company_external_ref_unique",
            "unique(company_id, external_ref)",
            "This SMS or call activity has already been imported.",
        ),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        prepared = []
        conversations_to_reopen = self.env["smsmobileapi.conversation"]
        for incoming_vals in vals_list:
            vals = dict(incoming_vals)
            normalized = vals.get("phone_normalized") or self._normalize_phone(vals.get("phone_number"))
            if normalized:
                vals["phone_normalized"] = normalized
                vals["phone_number"] = normalized
            company = self.env["res.company"].browse(
                vals.get("company_id") or self.env.company.id
            ).exists()
            partner = self.env["res.partner"].browse(vals.get("partner_id") or False).exists()
            if normalized and company and not vals.get("conversation_id"):
                conversation = self.env["smsmobileapi.conversation"]._get_or_create(
                    company, normalized, partner
                )
                vals["conversation_id"] = conversation.id or False
                if vals.get("direction") == "incoming" and conversation.state in ("done", "archived"):
                    conversations_to_reopen |= conversation
            if "is_read" not in vals:
                vals["is_read"] = vals.get("direction") != "incoming"
            prepared.append(vals)
        records = super().create(prepared)
        if conversations_to_reopen:
            conversations_to_reopen.sudo().write({"state": "new"})
        return records

    @api.depends("event_type", "direction", "phone_number")
    def _compute_name(self):
        labels = dict(self._fields["event_type"].selection)
        for record in self:
            record.name = "%s · %s" % (labels.get(record.event_type, record.event_type), record.phone_number or "")

    @api.model
    def _normalize_phone(self, value):
        value = str(value or "").strip()
        if not value:
            return False
        leading_plus = value.startswith("+")
        digits = re.sub(r"\D", "", value)
        if not leading_plus or len(digits) < 7 or len(digits) > 15:
            return False
        return "+" + digits

    @api.model
    def _partner_for_phone(self, company, normalized):
        if not normalized:
            return self.env["res.partner"]
        partners = self.env["res.partner"].sudo().with_company(company).search([
            "&",
            "|",
            ("smsmobileapi_mobile_normalized", "=", normalized),
            ("smsmobileapi_phone_normalized", "=", normalized),
            "|", ("company_id", "=", False), ("company_id", "=", company.id),
        ], limit=2)
        # Avoid disclosing one contact's activity on another contact when a number is duplicated.
        return partners[:1] if len(partners) == 1 else self.env["res.partner"]

    @api.model
    def _reconcile_partner_links(self, normalized_numbers, company_ids):
        numbers = sorted({number for number in normalized_numbers if number})
        companies = self.env["res.company"].sudo().browse(list(company_ids)).exists()
        if not numbers or not companies:
            return 0

        activities = self.sudo().search([
            ("company_id", "in", companies.ids),
            ("phone_normalized", "in", numbers),
        ])
        buckets = {}
        for activity in activities:
            buckets.setdefault(
                (activity.company_id.id, activity.phone_normalized), self.browse()
            )
            buckets[(activity.company_id.id, activity.phone_normalized)] |= activity

        updated = 0
        for (company_id, normalized), records in buckets.items():
            company = companies.filtered(lambda item: item.id == company_id)
            partner = self._partner_for_phone(company, normalized)
            partner_id = partner.id or False
            changed = records.filtered(lambda record: record.partner_id.id != partner_id)
            if changed:
                changed.write({"partner_id": partner_id})
                updated += len(changed)
            conversations = self.env["smsmobileapi.conversation"].sudo().search([
                ("company_id", "=", company_id), ("phone_normalized", "=", normalized),
            ])
            conversations.filtered(
                lambda conversation: conversation.partner_id.id != partner_id
            ).write({"partner_id": partner_id})
        return updated

    @api.model
    def _mobile_for_sid(self, config, sid):
        if not sid:
            return self.env["smsmobileapi.mobile"]
        return self.env["smsmobileapi.mobile"].sudo().search([
            ("config_id", "=", config.id), ("sid", "=", str(sid))
        ], limit=1)

    @api.model
    def _to_datetime(self, *values):
        for value in values:
            if value in (None, ""):
                continue
            try:
                if isinstance(value, (int, float)) or (isinstance(value, str) and value.isdigit()):
                    number = float(value)
                    if number > 10_000_000_000:
                        number /= 1000
                    return datetime.fromtimestamp(number, tz=timezone.utc).replace(tzinfo=None)
                parsed = fields.Datetime.to_datetime(str(value).replace("T", " ").replace("Z", ""))
                if parsed:
                    return parsed
            except (TypeError, ValueError, OverflowError):
                continue
        return fields.Datetime.now()

    @api.model
    def _external_ref(self, prefix, row, explicit=None):
        if explicit:
            return "%s:%s" % (prefix, str(explicit)[:180])
        canonical = json.dumps(row, sort_keys=True, separators=(",", ":"), default=str)
        return "%s:%s" % (prefix, hashlib.sha256(canonical.encode("utf-8")).hexdigest())

    @api.model
    def _repair_text_encoding(self, value):
        """Repair UTF-8 bytes that an upstream service decoded as Latin-1/CP1252.

        The gateway can return mixed text: already-correct Unicode next to sequences
        such as ``Ã§`` or ``â€™``. Re-encoding the complete string would damage the
        correct part, so only valid UTF-8 byte sequences are repaired in place.
        """
        if not isinstance(value, str) or not value:
            return value

        def legacy_byte(character):
            codepoint = ord(character)
            if codepoint <= 0xFF:
                return codepoint
            try:
                encoded = character.encode("cp1252")
            except (UnicodeEncodeError, LookupError):
                return None
            return encoded[0] if len(encoded) == 1 else None

        repaired = value
        # A second pass also repairs values that were accidentally decoded twice.
        for _iteration in range(3):
            output = []
            index = 0
            changed = False
            while index < len(repaired):
                first = legacy_byte(repaired[index])
                expected = (
                    2 if first is not None and 0xC2 <= first <= 0xDF else
                    3 if first is not None and 0xE0 <= first <= 0xEF else
                    4 if first is not None and 0xF0 <= first <= 0xF4 else
                    0
                )
                if expected and index + expected <= len(repaired):
                    sequence = [legacy_byte(character) for character in repaired[index:index + expected]]
                    if (
                        all(byte is not None for byte in sequence)
                        and all(0x80 <= byte <= 0xBF for byte in sequence[1:])
                    ):
                        try:
                            decoded = bytes(sequence).decode("utf-8")
                        except UnicodeDecodeError:
                            decoded = None
                        if decoded is not None:
                            output.append(decoded)
                            index += expected
                            changed = True
                            continue
                output.append(repaired[index])
                index += 1
            candidate = "".join(output)
            if not changed or candidate == repaired:
                break
            repaired = candidate
        return repaired

    @api.model
    def _repair_existing_message_encoding(self, company=None):
        """Repair previously imported activity text in bounded batches."""
        domain = [("message", "!=", False)]
        if company:
            domain.append(("company_id", "=", company.id))
        changed = 0
        last_id = 0
        while True:
            records = self.sudo().search(
                domain + [("id", ">", last_id)], order="id", limit=500
            )
            if not records:
                break
            for record in records:
                fixed_message = self._repair_text_encoding(record.message)
                fixed_error = self._repair_text_encoding(record.error_message)
                updates = {}
                if fixed_message != record.message:
                    updates["message"] = fixed_message
                if fixed_error != record.error_message:
                    updates["error_message"] = fixed_error
                if updates:
                    record.write(updates)
                    changed += 1
            last_id = records[-1].id
        return changed

    @api.model
    def _backfill_conversations(self):
        """Attach historical activity to one shared conversation per company and number."""
        last_id = 0
        linked = 0
        while True:
            records = self.sudo().search([
                ("id", ">", last_id), ("conversation_id", "=", False),
            ], order="id", limit=500)
            if not records:
                break
            for record in records:
                conversation = self.env["smsmobileapi.conversation"]._get_or_create(
                    record.company_id, record.phone_normalized or record.phone_number,
                    record.partner_id,
                )
                if conversation:
                    # Historical rows predate the inbox and must not create a false unread flood.
                    record.write({"conversation_id": conversation.id, "is_read": True})
                    linked += 1
            last_id = records[-1].id
        return linked

    @api.model
    def _create_imported(self, config, vals):
        normalized = self._normalize_phone(vals.get("phone_number"))
        if not normalized:
            return self.env["smsmobileapi.activity"]
        if vals.get("message"):
            vals["message"] = self._repair_text_encoding(vals["message"])
        if vals.get("error_message"):
            vals["error_message"] = self._repair_text_encoding(vals["error_message"])
        vals.update({
            "phone_normalized": normalized,
            "phone_number": normalized,
            "company_id": config.company_id.id,
            "config_id": config.id,
        })
        vals.setdefault("partner_id", self._partner_for_phone(config.company_id, normalized).id or False)
        existing = self.sudo().search([
            ("company_id", "=", config.company_id.id),
            ("external_ref", "=", vals["external_ref"]),
        ], limit=1)
        if existing:
            partner_id = vals.get("partner_id") or False
            updates = {}
            if existing.partner_id.id != partner_id:
                updates["partner_id"] = partner_id
            if vals.get("message") and existing.message != vals["message"]:
                updates["message"] = vals["message"]
            if vals.get("error_message") and existing.error_message != vals["error_message"]:
                updates["error_message"] = vals["error_message"]
            if vals.get("status") and existing.status != vals["status"]:
                updates["status"] = vals["status"]
            if vals.get("mobile_id") and existing.mobile_id.id != vals["mobile_id"]:
                updates["mobile_id"] = vals["mobile_id"]
            if not existing.conversation_id:
                conversation = self.env["smsmobileapi.conversation"]._get_or_create(
                    config.company_id, normalized,
                    self.env["res.partner"].browse(partner_id).exists(),
                )
                updates["conversation_id"] = conversation.id or False
            if updates:
                existing.write(updates)
            return existing.with_context(smsmobileapi_was_created=False)
        record = self.sudo().create(vals)
        record._post_to_partner_chatter()
        return record.with_context(smsmobileapi_was_created=True)

    def _post_to_partner_chatter(self):
        subtype = self.env.ref("mail.mt_note")
        for record in self.filtered("partner_id"):
            if record.event_type == "sms":
                label = _("Incoming SMS") if record.direction == "incoming" else _("Outgoing SMS")
                body = Markup("<strong>%s</strong><br/>%s") % (escape(label), escape(record.message or ""))
            else:
                label = dict(record._fields["event_type"].selection).get(record.event_type)
                duration = _(" · %(seconds)s seconds", seconds=record.duration_seconds) if record.duration_seconds else ""
                body = Markup("<strong>%s</strong>%s<br/>%s") % (
                    escape(label), escape(duration), escape(fields.Datetime.to_string(record.activity_at))
                )
            record.partner_id.sudo().message_post(
                body=body,
                message_type="comment",
                subtype_id=subtype.id,
                author_id=self.env.user.partner_id.id,
            )

    @api.model
    def _result_rows(self, payload, keys=("sms", "data", "rows")):
        if not isinstance(payload, dict):
            return []
        containers = [payload]
        if isinstance(payload.get("result"), dict):
            containers.insert(0, payload["result"])
        for container in containers:
            for key in keys:
                if isinstance(container.get(key), list):
                    return container[key]
        return []

    @api.model
    def _sync_received_sms(self, config):
        # Re-read the configured recovery window on every run. Unique external references
        # make this safe and prevent losing replies after a temporary outage.
        since = fields.Datetime.now() - timedelta(days=config.sync_lookback_days)
        payload = self.env["smsmobileapi.client"].get(config, "/getsms/", {
            "after_timestamp_unix": int(fields.Datetime.to_datetime(since).replace(tzinfo=timezone.utc).timestamp()),
        }, operation=_("received SMS synchronization"))
        created = 0
        for row in self._result_rows(payload):
            ref = row.get("guid") or row.get("guid_message") or row.get("id")
            record = self._create_imported(config, {
                "event_type": "sms", "direction": "incoming", "source": "api", "status": "received",
                "phone_number": row.get("number"), "message": row.get("message") or row.get("sms"),
                "activity_at": self._to_datetime(row.get("timestamp_unix"), row.get("time_received"), row.get("date")),
                "external_ref": self._external_ref("received", row, ref),
                "mobile_id": self._mobile_for_sid(config, row.get("sIdentifiantPhone") or row.get("mobile_sid")).id or False,
            })
            created += bool(record and record.env.context.get("smsmobileapi_was_created"))
        return created

    @api.model
    def _sync_api_sent_sms(self, config):
        payload = self.env["smsmobileapi.client"].get(
            config, "/log/sent/sms/", operation=_("sent SMS synchronization")
        )
        created = 0
        for row in self._result_rows(payload):
            ref = row.get("guid_message") or row.get("guid") or row.get("id")
            error = row.get("error_api") or row.get("send_from_mobile_erreur")
            raw_status = str(
                row.get("delivery_status") or row.get("status") or ""
            ).strip().lower()
            if error:
                status = "error"
            elif raw_status in ("delivered", "delivery_success", "received"):
                status = "delivered"
            elif row.get("send_from_mobile") or raw_status in ("sent", "success", "completed"):
                status = "sent"
            else:
                status = "queued"
            record = self._create_imported(config, {
                "event_type": "sms", "direction": "outgoing", "source": "api",
                "status": status,
                "phone_number": row.get("recipients") or row.get("number"),
                "message": row.get("sms") or row.get("message"),
                "activity_at": self._to_datetime(row.get("timestamp_unix"), row.get("datetime"), row.get("created_at")),
                "external_ref": self._external_ref("api-sent", row, ref),
                "error_message": str(error)[:255] if error else False,
                "mobile_id": self._mobile_for_sid(config, row.get("sIdentifiantPhone") or row.get("sIdentifiant")).id or False,
            })
            created += bool(record and record.env.context.get("smsmobileapi_was_created"))
        return created

    @api.model
    def _sync_mobile_sent_sms(self, config):
        period = "last_24h" if config.sync_lookback_days == 1 else (
            "last_3days" if config.sync_lookback_days <= 3 else "last_7days"
        )
        payload = self.env["smsmobileapi.client"].get(config, "/log/sent/frommobile/", {
            "period": period,
            "sort_by": "mobile_date_ms", "sort_order": "DESC", "limit": 200,
        }, operation=_("mobile-sent SMS synchronization"))
        created = 0
        for row in self._result_rows(payload):
            ref = row.get("guid") or row.get("guid_message") or row.get("id")
            record = self._create_imported(config, {
                "event_type": "sms", "direction": "outgoing", "source": "mobile", "status": "sent",
                "phone_number": row.get("number") or row.get("recipients"),
                "message": row.get("message") or row.get("sms"),
                "activity_at": self._to_datetime(row.get("mobile_date_ms"), row.get("mobile_date_formatted"), row.get("synchro_time")),
                "external_ref": self._external_ref("mobile-sent", row, ref),
                "mobile_id": self._mobile_for_sid(config, row.get("sIdentifiant") or row.get("device_id")).id or False,
            })
            created += bool(record and record.env.context.get("smsmobileapi_was_created"))
        return created

    @api.model
    def _sync_missed_calls(self, config):
        date_from = (fields.Date.context_today(self) - timedelta(days=config.sync_lookback_days)).isoformat()
        payload = self.env["smsmobileapi.client"].get(config, "/call/missed/list/", {
            "offset": 0, "limit": 500, "date_start": date_from,
        }, operation=_("missed call synchronization"))
        return self._import_call_rows(config, payload, "call_missed", "incoming", "missed")

    @api.model
    def _sync_incoming_calls(self, config):
        since = fields.Datetime.now() - timedelta(days=config.sync_lookback_days)
        payload = self.env["smsmobileapi.client"].get(config, "/call/incoming/list/", {
            "offset": 0, "limit": 200, "sort_by": "call_date_ms", "sort_dir": "desc",
            "date_from_ms": int(since.replace(tzinfo=timezone.utc).timestamp() * 1000),
        }, operation=_("incoming call synchronization"))
        return self._import_call_rows(config, payload, "call_incoming", "incoming", "completed")

    @api.model
    def _sync_outgoing_calls(self, config):
        since = fields.Datetime.now() - timedelta(days=config.sync_lookback_days)
        payload = self.env["smsmobileapi.client"].get(config, "/call/outgoing/list/", {
            "offset": 0, "limit": 200, "sort_by": "call_date_ms", "sort_dir": "desc",
            "date_from_ms": int(since.replace(tzinfo=timezone.utc).timestamp() * 1000),
        }, operation=_("outgoing call synchronization"))
        return self._import_call_rows(config, payload, "call_outgoing", "outgoing", "completed")

    @api.model
    def _import_call_rows(self, config, payload, event_type, direction, status):
        created = 0
        for row in self._result_rows(payload, keys=("data", "rows")):
            ref = row.get("guid") or row.get("id") or row.get("call_id")
            record = self._create_imported(config, {
                "event_type": event_type, "direction": direction, "source": "mobile", "status": status,
                "phone_number": row.get("phone_number") or row.get("number"),
                "activity_at": self._to_datetime(row.get("call_date_ms"), row.get("call_datetime_utc"), row.get("date")),
                "duration_seconds": self._safe_duration(row.get("duration_sec") or row.get("duration")),
                "external_ref": self._external_ref(event_type, row, ref),
                "mobile_id": self._mobile_for_sid(config, row.get("sIdentifiant") or row.get("device_id") or row.get("mobile_sid")).id or False,
            })
            created += bool(record and record.env.context.get("smsmobileapi_was_created"))
        return created

    @api.model
    def _safe_duration(self, value):
        try:
            return max(0, int(float(value)))
        except (TypeError, ValueError):
            return 0

    @api.model
    def _check_user_access(self):
        if not self.env.su and not self.env.user.has_group(
            "sms_mobile_api_call.group_smsmobileapi_user"
        ):
            raise AccessError(_("You are not allowed to manage SMS and call activity."))

    def action_mark_read(self):
        self._check_user_access()
        self.sudo().write({"is_read": True})
        return True

    def action_reply(self):
        self.ensure_one()
        self._check_user_access()
        self.sudo().write({"is_read": True})
        if self.conversation_id.state == "new":
            self.conversation_id.sudo().write({"state": "open"})
        return self.env["smsmobileapi.send.wizard"]._action_for_activity(self)

    def action_create_business_action(self):
        self.ensure_one()
        self._check_user_access()
        return {
            "name": _("Create an Odoo action"),
            "type": "ir.actions.act_window",
            "res_model": "smsmobileapi.business.action.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_activity_id": self.id},
        }

    @api.model
    def ingest_webhook(self, config, event_name, event_id, payload):
        if not isinstance(payload, dict):
            return self.env["smsmobileapi.activity"]
        event_map = {
            "sms.received": ("sms", "incoming", "received"),
            "sms.mobile.sent": ("sms", "outgoing", "sent"),
            "sms.sent": ("sms", "outgoing", "sent"),
            "call.missed": ("call_missed", "incoming", "missed"),
            "call.incoming": ("call_incoming", "incoming", "completed"),
            "call.outgoing": ("call_outgoing", "outgoing", "completed"),
        }
        if event_name not in event_map:
            return self.env["smsmobileapi.activity"]
        data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
        event_type, direction, status = event_map[event_name]
        phone = data.get("phone_number") or data.get("number") or data.get("from") or data.get("to") or data.get("recipients")
        return self._create_imported(config, {
            "event_type": event_type,
            "direction": direction,
            "source": "webhook",
            "status": status,
            "phone_number": phone,
            "message": data.get("message") or data.get("sms") or data.get("body"),
            "activity_at": self._to_datetime(
                data.get("timestamp_unix"), data.get("call_date_ms"), data.get("timestamp_utc"),
                data.get("call_datetime_utc"), data.get("date"), payload.get("created_at")
            ),
            "duration_seconds": self._safe_duration(data.get("duration_sec") or data.get("duration")),
            "external_ref": self._external_ref("webhook", data, event_id or data.get("guid") or data.get("id")),
            "mobile_id": self._mobile_for_sid(
                config, data.get("mobile_sid") or data.get("device_id") or data.get("sIdentifiantPhone")
            ).id or False,
        })
