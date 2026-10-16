from odoo import fields, models


class SmsMobileApiSupportTicket(models.Model):
    _name = "smsmobileapi.support.ticket"
    _description = "SMSMobileAPI Support Ticket"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "priority desc, create_date desc"
    _check_company_auto = True

    name = fields.Char(required=True, tracking=True)
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company,
        ondelete="cascade", index=True,
    )
    partner_id = fields.Many2one(
        "res.partner", string="Contact", ondelete="set null", check_company=True,
        tracking=True, index=True,
    )
    phone_number = fields.Char(index=True)
    description = fields.Html()
    assigned_user_id = fields.Many2one(
        "res.users", string="Assigned to", default=lambda self: self.env.user,
        tracking=True, index=True,
    )
    state = fields.Selection([
        ("new", "New"),
        ("progress", "In progress"),
        ("resolved", "Resolved"),
        ("cancelled", "Cancelled"),
    ], default="new", required=True, tracking=True, index=True)
    priority = fields.Selection([
        ("0", "Normal"),
        ("1", "Important"),
        ("2", "Urgent"),
        ("3", "Critical"),
    ], default="0", required=True, tracking=True, index=True)
    source_activity_id = fields.Many2one(
        "smsmobileapi.activity", ondelete="set null", check_company=True, index=True,
    )
    conversation_id = fields.Many2one(
        "smsmobileapi.conversation", ondelete="set null", check_company=True, index=True,
    )

    def action_start(self):
        self.write({"state": "progress"})
        return True

    def action_resolve(self):
        self.write({"state": "resolved"})
        return True

    def action_reopen(self):
        self.write({"state": "progress"})
        return True
