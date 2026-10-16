from odoo import fields, models


class SmsMobileApiQuickReply(models.Model):
    _name = "smsmobileapi.quick.reply"
    _description = "SMSMobileAPI Quick Reply"
    _order = "sequence, name"
    _check_company_auto = True

    name = fields.Char(required=True, translate=True)
    message = fields.Text(required=True, translate=True)
    sequence = fields.Integer(default=10)
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company,
        ondelete="cascade", index=True,
    )
    active = fields.Boolean(default=True)
