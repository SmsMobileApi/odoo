from markupsafe import Markup, escape

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError


class SmsMobileApiBusinessActionWizard(models.TransientModel):
    _name = "smsmobileapi.business.action.wizard"
    _description = "Create an Odoo action from mobile activity"

    activity_id = fields.Many2one("smsmobileapi.activity", required=True, readonly=True)
    company_id = fields.Many2one("res.company", required=True, readonly=True)
    partner_id = fields.Many2one("res.partner", string="Contact", readonly=True)
    phone_number = fields.Char(readonly=True)
    action_type = fields.Selection([
        ("opportunity", "CRM opportunity"),
        ("task", "Project task"),
        ("followup", "Follow-up activity"),
        ("quotation", "Quotation"),
        ("support", "Support ticket"),
        ("link", "Link an existing document"),
    ], required=True, default="opportunity")
    name = fields.Char(required=True)
    description = fields.Html()
    assigned_user_id = fields.Many2one(
        "res.users", string="Assigned to", default=lambda self: self.env.user,
        domain="[('share', '=', False)]",
    )
    deadline = fields.Date(default=lambda self: fields.Date.context_today(self))
    project_id = fields.Many2one(
        "project.project", domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]"
    )
    priority = fields.Selection([
        ("0", "Normal"),
        ("1", "Important"),
        ("2", "Urgent"),
        ("3", "Critical"),
    ], default="0", required=True)
    sale_order_id = fields.Many2one(
        "sale.order", string="Quotation / Sales order",
        domain="[('company_id', '=', company_id), ('partner_id', 'child_of', partner_id)]",
    )
    invoice_id = fields.Many2one(
        "account.move", string="Invoice",
        domain="[('company_id', '=', company_id), ('partner_id', 'child_of', partner_id), ('move_type', 'in', ('out_invoice', 'out_refund'))]",
    )

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        activity = self.env["smsmobileapi.activity"].browse(
            self.env.context.get("default_activity_id") or values.get("activity_id")
        ).exists()
        if activity:
            event_label = dict(activity._fields["event_type"].selection).get(activity.event_type)
            contact = activity.partner_id.display_name if activity.partner_id else activity.phone_number
            values.update({
                "activity_id": activity.id,
                "company_id": activity.company_id.id,
                "partner_id": activity.partner_id.id or False,
                "phone_number": activity.phone_number,
                "name": _("Follow up %(event)s from %(contact)s", event=event_label, contact=contact),
                "description": self._description_for_activity(activity),
            })
        return values

    @api.model
    def _description_for_activity(self, activity):
        message = escape(activity.message or "")
        return Markup(
            "<p><strong>%s</strong> — %s</p><p>%s</p>"
        ) % (
            escape(dict(activity._fields["event_type"].selection).get(activity.event_type)),
            escape(activity.phone_number),
            message,
        )

    def _check_access(self):
        if not self.env.su and not self.env.user.has_group(
            "sms_mobile_api_call.group_smsmobileapi_user"
        ):
            raise AccessError(_("You are not allowed to create actions from mobile activity."))

    def _open_record(self, record):
        return {
            "name": record.display_name,
            "type": "ir.actions.act_window",
            "res_model": record._name,
            "res_id": record.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_create(self):
        self.ensure_one()
        self._check_access()
        activity = self.activity_id
        if activity.company_id != self.company_id:
            raise AccessError(_("The selected activity belongs to another company."))

        common_note = self.description or self._description_for_activity(activity)
        if self.action_type == "opportunity":
            record = self.env["crm.lead"].create({
                "name": self.name,
                "type": "opportunity",
                "partner_id": self.partner_id.id or False,
                "contact_name": self.partner_id.name if self.partner_id else False,
                "phone": self.phone_number,
                "description": common_note,
                "user_id": self.assigned_user_id.id or False,
                "company_id": self.company_id.id,
                "priority": self.priority,
            })
            activity.sudo().write({"crm_lead_id": record.id})
        elif self.action_type == "task":
            record = self.env["project.task"].create({
                "name": self.name,
                "description": common_note,
                "project_id": self.project_id.id or False,
                "partner_id": self.partner_id.id or False,
                "user_ids": [(6, 0, self.assigned_user_id.ids)],
                "company_id": self.company_id.id,
                "priority": "1" if self.priority != "0" else "0",
                "date_deadline": self.deadline,
            })
            activity.sudo().write({"project_task_id": record.id})
        elif self.action_type == "followup":
            if not self.partner_id:
                raise UserError(_("Create or link a contact before scheduling a follow-up."))
            record = self.partner_id.activity_schedule(
                "mail.mail_activity_data_todo",
                date_deadline=self.deadline,
                summary=self.name,
                note=common_note,
                user_id=self.assigned_user_id.id or self.env.user.id,
            )
            activity.sudo().write({"followup_activity_id": record.id})
        elif self.action_type == "quotation":
            if not self.partner_id:
                raise UserError(_("Create or link a contact before creating a quotation."))
            record = self.env["sale.order"].create({
                "partner_id": self.partner_id.id,
                "company_id": self.company_id.id,
                "user_id": self.assigned_user_id.id or self.env.user.id,
                "note": common_note,
                "origin": _("SMSMobileAPI activity %(reference)s", reference=activity.id),
            })
            activity.sudo().write({"sale_order_id": record.id})
        elif self.action_type == "support":
            record = self.env["smsmobileapi.support.ticket"].create({
                "name": self.name,
                "company_id": self.company_id.id,
                "partner_id": self.partner_id.id or False,
                "phone_number": self.phone_number,
                "description": common_note,
                "assigned_user_id": self.assigned_user_id.id or self.env.user.id,
                "priority": self.priority,
                "source_activity_id": activity.id,
                "conversation_id": activity.conversation_id.id or False,
            })
            activity.sudo().write({"support_ticket_id": record.id})
        else:
            if not self.sale_order_id and not self.invoice_id:
                raise UserError(_("Select a quotation, sales order or invoice to link."))
            activity.sudo().write({
                "sale_order_id": self.sale_order_id.id or False,
                "invoice_id": self.invoice_id.id or False,
            })
            record = self.sale_order_id or self.invoice_id

        activity.sudo().write({"is_read": True})
        if activity.conversation_id.state == "new":
            activity.conversation_id.sudo().write({"state": "open"})
        return self._open_record(record)
