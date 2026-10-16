from psycopg2 import IntegrityError

from odoo import _, api, fields, models
from odoo.exceptions import AccessError


class SmsMobileApiConversation(models.Model):
    _name = "smsmobileapi.conversation"
    _description = "SMSMobileAPI Conversation"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "last_activity_at desc, id desc"
    _check_company_auto = True

    name = fields.Char(compute="_compute_name", store=True)
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company,
        ondelete="cascade", index=True,
    )
    partner_id = fields.Many2one(
        "res.partner", string="Contact", ondelete="set null", check_company=True,
        index=True, tracking=True,
    )
    phone_number = fields.Char(required=True, index=True)
    phone_normalized = fields.Char(required=True, index=True)
    assigned_user_id = fields.Many2one(
        "res.users", string="Assigned to", ondelete="set null", index=True, tracking=True,
        domain="[('share', '=', False)]",
    )
    state = fields.Selection([
        ("new", "New"),
        ("open", "In progress"),
        ("done", "Resolved"),
        ("archived", "Archived"),
    ], default="new", required=True, tracking=True, index=True)
    priority = fields.Selection([
        ("0", "Normal"),
        ("1", "Important"),
        ("2", "Urgent"),
        ("3", "Critical"),
    ], default="0", required=True, tracking=True, index=True)
    event_ids = fields.One2many(
        "smsmobileapi.activity", "conversation_id", string="SMS and call timeline"
    )
    activity_count = fields.Integer(compute="_compute_summary", store=True)
    unread_count = fields.Integer(compute="_compute_summary", store=True, index=True)
    last_activity_at = fields.Datetime(compute="_compute_summary", store=True, index=True)
    last_message_preview = fields.Char(compute="_compute_summary", store=True)
    last_event_type = fields.Selection([
        ("sms", "SMS"),
        ("call_missed", "Missed call"),
        ("call_incoming", "Incoming call"),
        ("call_outgoing", "Outgoing call"),
    ], compute="_compute_summary", store=True)
    last_direction = fields.Selection([
        ("incoming", "Incoming"),
        ("outgoing", "Outgoing"),
    ], compute="_compute_summary", store=True)
    last_mobile_id = fields.Many2one(
        "smsmobileapi.mobile", compute="_compute_summary", store=True, check_company=True,
    )
    mobile_filter_id = fields.Many2one(
        "smsmobileapi.mobile", string="Filter by mobile", check_company=True,
        domain="[('company_id', '=', company_id), ('active', '=', True)]",
        help="Leave empty to display activity from every connected mobile.",
    )
    filtered_activity_ids = fields.Many2many(
        "smsmobileapi.activity", compute="_compute_filtered_activity_ids",
        string="Filtered timeline",
    )
    message_search = fields.Char(
        string="Message content", compute="_compute_message_search",
        search="_search_message_content",
    )

    _sql_constraints = [
        (
            "company_phone_unique",
            "unique(company_id, phone_normalized)",
            "A conversation already exists for this phone number in this company.",
        ),
    ]

    @api.depends("partner_id", "partner_id.display_name", "phone_number")
    def _compute_name(self):
        for conversation in self:
            conversation.name = (
                "%s — %s" % (conversation.partner_id.display_name, conversation.phone_number)
                if conversation.partner_id else conversation.phone_number
            )

    @api.depends(
        "event_ids", "event_ids.activity_at", "event_ids.message",
        "event_ids.event_type", "event_ids.direction", "event_ids.mobile_id",
        "event_ids.is_read",
    )
    def _compute_summary(self):
        for conversation in self:
            activities = conversation.event_ids
            latest = activities.sorted(lambda activity: (activity.activity_at, activity.id), reverse=True)[:1]
            conversation.activity_count = len(activities)
            conversation.unread_count = len(activities.filtered(
                lambda activity: activity.direction == "incoming" and not activity.is_read
            ))
            conversation.last_activity_at = latest.activity_at if latest else False
            conversation.last_event_type = latest.event_type if latest else False
            conversation.last_direction = latest.direction if latest else False
            conversation.last_mobile_id = latest.mobile_id if latest else False
            if latest:
                preview = latest.message if latest.event_type == "sms" else latest.display_name
                conversation.last_message_preview = (preview or "")[:180]
            else:
                conversation.last_message_preview = False

    @api.depends("event_ids", "mobile_filter_id")
    def _compute_filtered_activity_ids(self):
        for conversation in self:
            activities = conversation.event_ids
            if conversation.mobile_filter_id:
                activities = activities.filtered(
                    lambda activity: activity.mobile_id == conversation.mobile_filter_id
                )
            conversation.filtered_activity_ids = activities

    def _compute_message_search(self):
        for conversation in self:
            conversation.message_search = False

    @api.model
    def _search_message_content(self, operator, value):
        activities = self.env["smsmobileapi.activity"].search([
            ("message", operator, value), ("conversation_id", "!=", False),
        ])
        return [("id", "in", activities.mapped("conversation_id").ids)]

    @api.model
    def _get_or_create(self, company, phone_number, partner=None):
        normalized = self.env["smsmobileapi.activity"]._normalize_phone(phone_number)
        if not normalized:
            return self.browse()
        domain = [("company_id", "=", company.id), ("phone_normalized", "=", normalized)]
        conversation = self.sudo().search(domain, limit=1)
        partner = partner if partner and partner.exists() else self.env["res.partner"]
        if conversation:
            if partner and conversation.partner_id != partner:
                conversation.write({"partner_id": partner.id})
            return conversation
        values = {
            "company_id": company.id,
            "phone_number": normalized,
            "phone_normalized": normalized,
            "partner_id": partner.id or False,
        }
        try:
            with self.env.cr.savepoint():
                return self.sudo().create(values)
        except IntegrityError:
            return self.sudo().search(domain, limit=1)

    @api.model
    def _check_user_access(self):
        if not self.env.su and not self.env.user.has_group(
            "sms_mobile_api_call.group_smsmobileapi_user"
        ):
            raise AccessError(_("You are not allowed to manage SMS conversations."))

    def action_open(self):
        self.ensure_one()
        self.action_mark_read()
        return {
            "name": self.display_name,
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_mark_read(self):
        self._check_user_access()
        for conversation in self:
            unread = conversation.event_ids.filtered(
                lambda activity: activity.direction == "incoming" and not activity.is_read
            )
            if unread:
                unread.sudo().write({"is_read": True})
            if conversation.state == "new":
                conversation.sudo().write({"state": "open"})
        return True

    def action_assign_to_me(self):
        self._check_user_access()
        self.sudo().write({"assigned_user_id": self.env.user.id, "state": "open"})
        return True

    def action_mark_done(self):
        self._check_user_access()
        self.sudo().write({"state": "done"})
        return True

    def action_archive(self):
        self._check_user_access()
        self.sudo().write({"state": "archived"})
        return True

    def action_reopen(self):
        self._check_user_access()
        self.sudo().write({"state": "open"})
        return True

    def action_reply(self):
        self.ensure_one()
        self._check_user_access()
        self.action_mark_read()
        latest = self.event_ids.filtered(
            lambda activity: activity.event_type == "sms" and activity.direction == "incoming"
        ).sorted(lambda activity: (activity.activity_at, activity.id), reverse=True)[:1]
        return self.env["smsmobileapi.send.wizard"]._action_for_conversation(
            self, latest or False
        )

    def action_create_business_action(self):
        self.ensure_one()
        self._check_user_access()
        latest = self.event_ids.filtered(
            lambda activity: activity.direction == "incoming"
        ).sorted(lambda activity: (activity.activity_at, activity.id), reverse=True)[:1]
        if not latest:
            latest = self.event_ids.sorted(
                lambda activity: (activity.activity_at, activity.id), reverse=True
            )[:1]
        return (latest or self.event_ids[:1]).action_create_business_action()
