from odoo import _, models
from odoo.exceptions import AccessError


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    def action_smsmobileapi_send_document(self):
        self.ensure_one()
        if not self.env.su and not self.env.user.has_group("sms_mobile_api_call.group_smsmobileapi_user"):
            raise AccessError(_("You are not allowed to send SMS."))
        self.check_access_rights("read")
        self.check_access_rule("read")
        return self.env["smsmobileapi.send.wizard"]._action_for_record(self, "purchase_order")
