import secrets
from datetime import timezone
from urllib.parse import urljoin

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


class SmsMobileApiSendWizard(models.TransientModel):
    _name = "smsmobileapi.send.wizard"
    _description = "Send an SMS with SMSMobileAPI"

    partner_id = fields.Many2one("res.partner", string="Contact")
    recipient_phone = fields.Char(required=True)
    mobile_id = fields.Many2one(
        "smsmobileapi.mobile", string="Mobile used to send",
        default=lambda self: self._default_mobile_id(),
        domain="[('company_id', '=', company_id), ('active', '=', True)]",
        help="Leave empty to use the first available connected mobile.",
    )
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)
    message = fields.Text(required=True)
    quick_reply_id = fields.Many2one(
        "smsmobileapi.quick.reply", string="Quick reply",
        domain="[('company_id', '=', company_id), ('active', '=', True)]",
    )
    reply_to_activity_id = fields.Many2one("smsmobileapi.activity", readonly=True)
    send_at = fields.Datetime(string="Schedule from")
    shorten_urls = fields.Boolean(default=False)
    source_model = fields.Char(readonly=True)
    source_id = fields.Integer(readonly=True)
    source_reference = fields.Char(readonly=True)
    message_kind = fields.Selection([
        ("free", "Free-form SMS"),
        ("invoice", "Invoice"),
        ("payment_reminder", "Payment reminder"),
        ("sale_order", "Quotation / Sales order"),
        ("purchase_order", "Purchase order"),
        ("document", "Secure document"),
    ], default="free", required=True)
    upload = fields.Binary(string="Document")
    upload_filename = fields.Char()
    secure_link_days = fields.Integer(default=7)
    state = fields.Selection([("draft", "Draft"), ("sent", "Sent")], default="draft", readonly=True)
    sent_activity_id = fields.Many2one("smsmobileapi.activity", readonly=True)

    @api.model
    def _default_mobile_id(self, company=None):
        company = company or self.env.company
        config = self.env["smsmobileapi.config"].sudo().search([
            ("company_id", "=", company.id), ("active", "=", True)
        ], limit=1)
        mobile = config.default_mobile_id
        return mobile.id if mobile and mobile.active else False

    @api.model
    def default_get(self, fields_list):
        defaults = super().default_get(fields_list)
        if "mobile_id" not in fields_list:
            return defaults

        company_id = defaults.get("company_id") or self.env.company.id
        company = self.env["res.company"].browse(company_id).exists()
        mobile = self.env["smsmobileapi.mobile"].sudo().browse(
            defaults.get("mobile_id") or False
        ).exists()
        if not mobile or not mobile.active or mobile.company_id != company:
            defaults["mobile_id"] = self._default_mobile_id(company)
        return defaults

    def _remember_mobile_for_user(self):
        self.ensure_one()
        if not self.mobile_id:
            return
        self.env["ir.default"].sudo().set(
            self._name,
            "mobile_id",
            self.mobile_id.id,
            user_id=self.env.uid,
            company_id=self.company_id.id,
        )

    @api.onchange("partner_id")
    def _onchange_partner_id(self):
        if self.partner_id:
            self.recipient_phone = self.partner_id.mobile or self.partner_id.phone or ""

    @api.onchange("quick_reply_id")
    def _onchange_quick_reply_id(self):
        if self.quick_reply_id:
            self.message = self.quick_reply_id.message

    @api.model
    def _action_for_record(self, record, kind="free"):
        if not self.env.su and not self.env.user.has_group("sms_mobile_api_call.group_smsmobileapi_user"):
            raise AccessError(_("You are not allowed to send SMS."))
        record.ensure_one()
        partner = record if record._name == "res.partner" else record.partner_id
        defaults = self._defaults_for_record(record, partner, kind)
        return {
            "name": _("Send SMS with SMSMobileAPI"),
            "type": "ir.actions.act_window",
            "res_model": "smsmobileapi.send.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_%s" % key: value for key, value in defaults.items()},
        }

    @api.model
    def _action_for_activity(self, activity):
        activity.ensure_one()
        return {
            "name": _("Reply by SMS"),
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_partner_id": activity.partner_id.id or False,
                "default_recipient_phone": activity.phone_number,
                "default_company_id": activity.company_id.id,
                "default_message": "",
                "default_message_kind": "free",
                "default_source_model": activity._name,
                "default_source_id": activity.id,
                "default_source_reference": activity.display_name,
                "default_reply_to_activity_id": activity.id,
            },
        }

    @api.model
    def _action_for_conversation(self, conversation, activity=False):
        conversation.ensure_one()
        action = {
            "name": _("Reply by SMS"),
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_partner_id": conversation.partner_id.id or False,
                "default_recipient_phone": conversation.phone_number,
                "default_company_id": conversation.company_id.id,
                "default_message": "",
                "default_message_kind": "free",
                "default_source_model": conversation._name,
                "default_source_id": conversation.id,
                "default_source_reference": conversation.display_name,
            },
        }
        if activity:
            action["context"]["default_reply_to_activity_id"] = activity.id
        return action

    @api.model
    def _defaults_for_record(self, record, partner, kind):
        company = record.company_id if "company_id" in record._fields and record.company_id else self.env.company
        phone = partner.mobile or partner.phone or ""
        reference = record.display_name
        base = self.env["ir.config_parameter"].sudo().get_param("web.base.url", "").rstrip("/")
        url = ""
        if kind != "free" and hasattr(record, "get_portal_url"):
            url = urljoin(base + "/", record.get_portal_url().lstrip("/"))
        if kind == "invoice":
            message = _("Hello %(name)s, your invoice %(reference)s is available here: %(url)s", name=partner.name, reference=reference, url=url)
        elif kind == "payment_reminder":
            due = fields.Date.to_string(record.invoice_date_due) if record.invoice_date_due else _("the due date")
            message = _("Hello %(name)s, this is a reminder that invoice %(reference)s was due on %(due)s. View it securely: %(url)s", name=partner.name, reference=reference, due=due, url=url)
        elif kind == "sale_order":
            label = _("quotation") if record.state in ("draft", "sent") else _("order")
            message = _("Hello %(name)s, your %(label)s %(reference)s is available here: %(url)s", name=partner.name, label=label, reference=reference, url=url)
        elif kind == "purchase_order":
            message = _("Hello %(name)s, purchase order %(reference)s is available here: %(url)s", name=partner.name, reference=reference, url=url)
        else:
            message = _("Hello %(name)s, ", name=partner.name)
        return {
            "partner_id": partner.id,
            "recipient_phone": phone,
            "company_id": company.id,
            "message": message,
            "message_kind": kind,
            "source_model": record._name,
            "source_id": record.id,
            "source_reference": reference,
        }

    def action_send(self):
        self.ensure_one()
        if not self.env.su and not self.env.user.has_group("sms_mobile_api_call.group_smsmobileapi_user"):
            raise AccessError(_("You are not allowed to send SMS."))
        if self.state != "draft":
            raise UserError(_("This SMS has already been submitted."))
        normalized = self.env["smsmobileapi.activity"]._normalize_phone(self.recipient_phone)
        if not normalized:
            raise ValidationError(_("Enter the recipient number in international format, for example +32470000000."))
        if len((self.message or "").strip()) > 5000:
            raise ValidationError(_("The message cannot exceed 5,000 characters."))

        message = (self.message or "").strip()
        attachment = False
        share = False
        if self.upload:
            if len(self.upload) > 14 * 1024 * 1024:
                raise ValidationError(_("The encoded document is too large. Upload a file smaller than 10 MB."))
            attachment = self.env["ir.attachment"].create({
                "name": self.upload_filename or _("Document"),
                "datas": self.upload,
                "res_model": self.source_model or "res.partner",
                "res_id": self.source_id or self.partner_id.id,
                "company_id": self.company_id.id,
            })
            share, secure_url = self.env["smsmobileapi.document.share"].create_secure_share(
                attachment, self.partner_id, self.secure_link_days
            )
            message = "%s %s" % (message, secure_url)

        config = self.env["smsmobileapi.config"].sudo().search([
            ("company_id", "=", self.company_id.id), ("active", "=", True)
        ], limit=1)
        if not config:
            raise UserError(_("Configure SMSMobileAPI for this company before sending an SMS."))

        data = {"recipients": normalized, "message": message, "shorturl": "1" if self.shorten_urls else "0"}
        if self.mobile_id:
            if self.mobile_id.company_id != self.company_id:
                raise AccessError(_("The selected mobile does not belong to this company."))
            data["sIdentifiant"] = self.mobile_id.sid
        if self.send_at:
            if self.send_at <= fields.Datetime.now():
                raise ValidationError(_("The scheduled date must be in the future."))
            data["schedule_timestamp"] = int(
                fields.Datetime.to_datetime(self.send_at).replace(tzinfo=timezone.utc).timestamp()
            )

        payload = self.env["smsmobileapi.client"].post(config, "/sendsms/", data, operation=_("SMS sending"))
        result = payload.get("result", {}) if isinstance(payload, dict) else {}
        external_id = result.get("id") or result.get("guid_message") or secrets.token_hex(16)
        activity = self.env["smsmobileapi.activity"].sudo().create({
            "company_id": self.company_id.id,
            "config_id": config.id,
            "partner_id": self.partner_id.id,
            "mobile_id": self.mobile_id.id or False,
            "event_type": "sms",
            "direction": "outgoing",
            "source": "odoo",
            "phone_number": normalized,
            "phone_normalized": normalized,
            "message": message,
            "activity_at": fields.Datetime.now(),
            "external_ref": "odoo:%s" % external_id,
            "status": "queued",
            "document_model": self.source_model,
            "document_id": self.source_id,
        })
        activity._post_to_partner_chatter()
        if self.reply_to_activity_id:
            self.reply_to_activity_id.sudo().write({"is_read": True})
        self._remember_mobile_for_user()
        self.write({"state": "sent", "sent_activity_id": activity.id})
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("SMS submitted"),
                "message": _("The SMS is queued for the connected mobile. Mobile processing can take a short time."),
                "type": "success",
                "sticky": False,
                "next": {"type": "ir.actions.act_window_close"},
            },
        }
