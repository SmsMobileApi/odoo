from odoo import _, models
from odoo.exceptions import AccessError, UserError


class AccountMove(models.Model):
    _inherit = "account.move"

    def action_smsmobileapi_send_invoice(self):
        self.ensure_one()
        self._smsmobileapi_check_document_access()
        if self.move_type not in ("out_invoice", "out_refund"):
            raise UserError(_("SMS invoice links are available only for customer invoices and credit notes."))
        return self.env["smsmobileapi.send.wizard"]._action_for_record(self, "invoice")

    def action_smsmobileapi_payment_reminder(self):
        self.ensure_one()
        self._smsmobileapi_check_document_access()
        if self.move_type != "out_invoice":
            raise UserError(_("Payment reminders are available only for customer invoices."))
        return self.env["smsmobileapi.send.wizard"]._action_for_record(self, "payment_reminder")

    def _smsmobileapi_check_document_access(self):
        if not self.env.su and not self.env.user.has_group("sms_mobile_api_call.group_smsmobileapi_user"):
            raise AccessError(_("You are not allowed to send SMS."))
        self.check_access_rights("read")
        self.check_access_rule("read")
