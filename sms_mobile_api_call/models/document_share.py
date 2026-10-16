import hashlib
import secrets
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError


class SmsMobileApiDocumentShare(models.Model):
    _name = "smsmobileapi.document.share"
    _description = "SMSMobileAPI Secure Document Link"
    _order = "create_date desc"
    _check_company_auto = True

    name = fields.Char(required=True)
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company,
        ondelete="cascade", index=True,
    )
    partner_id = fields.Many2one("res.partner", ondelete="cascade", check_company=True, index=True)
    attachment_id = fields.Many2one("ir.attachment", required=True, ondelete="cascade")
    token_digest = fields.Char(required=True, copy=False, index=True, groups="base.group_system")
    expires_at = fields.Datetime(required=True, index=True)
    active = fields.Boolean(default=True)
    access_count = fields.Integer(readonly=True)
    last_access_at = fields.Datetime(readonly=True)

    _sql_constraints = [
        ("token_digest_unique", "unique(token_digest)", "The secure document token must be unique."),
    ]

    @api.model
    def create_secure_share(self, attachment, partner, validity_days=7):
        if not self.env.su and not self.env.user.has_group("sms_mobile_api_call.group_smsmobileapi_user"):
            raise AccessError(_("You are not allowed to create SMS document links."))
        attachment.ensure_one()
        if attachment.file_size and attachment.file_size > 10 * 1024 * 1024:
            raise ValidationError(_("Documents sent by secure link are limited to 10 MB."))
        raw_token = secrets.token_urlsafe(32)
        digest = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        share = self.sudo().create({
            "name": attachment.name,
            "company_id": self.env.company.id,
            "partner_id": partner.id,
            "attachment_id": attachment.id,
            "token_digest": digest,
            "expires_at": fields.Datetime.now() + timedelta(days=max(1, min(int(validity_days), 30))),
        })
        base = self.env["ir.config_parameter"].sudo().get_param("web.base.url", "").rstrip("/")
        return share, "%s/smsmobileapi/document/%s" % (base, raw_token)

    @api.model
    def find_valid_share(self, raw_token):
        digest = hashlib.sha256(str(raw_token).encode("utf-8")).hexdigest()
        share = self.sudo().search([
            ("token_digest", "=", digest),
            ("active", "=", True),
            ("expires_at", ">", fields.Datetime.now()),
        ], limit=1)
        return share

    def action_revoke(self):
        self.check_access_rights("write")
        self.write({"active": False})
        return True
