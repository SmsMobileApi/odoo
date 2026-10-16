from odoo import _, api, fields, models
from odoo.exceptions import AccessError


class ResPartner(models.Model):
    _inherit = "res.partner"

    smsmobileapi_mobile_normalized = fields.Char(
        compute="_compute_smsmobileapi_normalized_numbers", store=True, index=True,
    )
    smsmobileapi_phone_normalized = fields.Char(
        compute="_compute_smsmobileapi_normalized_numbers", store=True, index=True,
    )
    smsmobileapi_activity_count = fields.Integer(compute="_compute_smsmobileapi_activity_count")
    smsmobileapi_unread_count = fields.Integer(compute="_compute_smsmobileapi_activity_count")
    smsmobileapi_conversation_count = fields.Integer(compute="_compute_smsmobileapi_activity_count")
    smsmobileapi_activity_ids = fields.One2many(
        "smsmobileapi.activity", "partner_id", string="SMS & call activity"
    )
    smsmobileapi_mobile_filter_id = fields.Many2one(
        "smsmobileapi.mobile", string="Filter by mobile", check_company=True,
        domain="[('company_id', '=', company_id), ('active', '=', True)]",
        help="Leave empty to display activity from every connected mobile.",
    )
    smsmobileapi_filtered_activity_ids = fields.Many2many(
        "smsmobileapi.activity", compute="_compute_smsmobileapi_filtered_activity_ids",
        string="Conversation timeline",
    )

    @api.depends("mobile", "phone", "country_id")
    def _compute_smsmobileapi_normalized_numbers(self):
        normalize = self.env["smsmobileapi.activity"]._normalize_phone
        for partner in self:
            mobile = partner._phone_format(fname="mobile") if partner.mobile else False
            phone = partner._phone_format(fname="phone") if partner.phone else False
            partner.smsmobileapi_mobile_normalized = normalize(mobile or partner.mobile)
            partner.smsmobileapi_phone_normalized = normalize(phone or partner.phone)

    def _smsmobileapi_numbers(self):
        return {
            number
            for partner in self
            for number in (
                partner.smsmobileapi_mobile_normalized,
                partner.smsmobileapi_phone_normalized,
            )
            if number
        }

    def _smsmobileapi_company_ids(self):
        return {
            partner.company_id.id or self.env.company.id
            for partner in self
        }

    def _smsmobileapi_reconcile_activity(self, numbers=None, company_ids=None):
        numbers = numbers if numbers is not None else self._smsmobileapi_numbers()
        company_ids = company_ids if company_ids is not None else self._smsmobileapi_company_ids()
        return self.env["smsmobileapi.activity"]._reconcile_partner_links(numbers, company_ids)

    @api.model_create_multi
    def create(self, vals_list):
        partners = super().create(vals_list)
        partners._smsmobileapi_reconcile_activity()
        return partners

    def write(self, vals):
        tracked = {"mobile", "phone", "country_id", "company_id", "active"}
        should_reconcile = bool(tracked.intersection(vals))
        old_numbers = self._smsmobileapi_numbers() if should_reconcile else set()
        old_company_ids = self._smsmobileapi_company_ids() if should_reconcile else set()
        result = super().write(vals)
        if should_reconcile:
            self.invalidate_recordset([
                "smsmobileapi_mobile_normalized", "smsmobileapi_phone_normalized",
            ])
            self._smsmobileapi_reconcile_activity(
                old_numbers | self._smsmobileapi_numbers(),
                old_company_ids | self._smsmobileapi_company_ids(),
            )
        return result

    def unlink(self):
        numbers = self._smsmobileapi_numbers()
        company_ids = self._smsmobileapi_company_ids()
        result = super().unlink()
        self.env["smsmobileapi.activity"]._reconcile_partner_links(numbers, company_ids)
        return result

    def _compute_smsmobileapi_activity_count(self):
        counts = self.env["smsmobileapi.activity"]._read_group(
            [("partner_id", "in", self.ids)], ["partner_id"], ["__count"]
        ) if self.ids else []
        mapped = {partner.id: count for partner, count in counts}
        unread = self.env["smsmobileapi.activity"]._read_group(
            [
                ("partner_id", "in", self.ids),
                ("direction", "=", "incoming"),
                ("is_read", "=", False),
            ], ["partner_id"], ["__count"]
        ) if self.ids else []
        unread_mapped = {partner.id: count for partner, count in unread}
        conversations = self.env["smsmobileapi.conversation"]._read_group(
            [("partner_id", "in", self.ids)], ["partner_id"], ["__count"]
        ) if self.ids else []
        conversation_mapped = {partner.id: count for partner, count in conversations}
        for partner in self:
            partner.smsmobileapi_activity_count = mapped.get(partner.id, 0)
            partner.smsmobileapi_unread_count = unread_mapped.get(partner.id, 0)
            partner.smsmobileapi_conversation_count = conversation_mapped.get(partner.id, 0)

    @api.depends(
        "smsmobileapi_mobile_filter_id", "smsmobileapi_activity_ids",
        "smsmobileapi_activity_ids.mobile_id",
    )
    def _compute_smsmobileapi_filtered_activity_ids(self):
        for partner in self:
            activities = partner.smsmobileapi_activity_ids
            if partner.smsmobileapi_mobile_filter_id:
                activities = activities.filtered(
                    lambda activity: activity.mobile_id == partner.smsmobileapi_mobile_filter_id
                )
            partner.smsmobileapi_filtered_activity_ids = activities

    def action_smsmobileapi_send_sms(self):
        self.ensure_one()
        if not self.env.su and not self.env.user.has_group("sms_mobile_api_call.group_smsmobileapi_user"):
            raise AccessError(_("You are not allowed to send SMS."))
        return self.env["smsmobileapi.send.wizard"]._action_for_record(self, "free")

    def action_smsmobileapi_view_activity(self):
        self.ensure_one()
        action = self.env.ref("sms_mobile_api_call.action_smsmobileapi_activity").read()[0]
        action["domain"] = [("partner_id", "=", self.id)]
        action["context"] = {"default_partner_id": self.id, "search_default_partner_id": self.id}
        return action

    def action_smsmobileapi_open_conversations(self):
        self.ensure_one()
        conversations = self.env["smsmobileapi.conversation"].search([
            ("partner_id", "=", self.id),
        ])
        if len(conversations) == 1:
            return conversations.action_open()
        action = self.env.ref("sms_mobile_api_call.action_smsmobileapi_conversation").read()[0]
        action["domain"] = [("partner_id", "=", self.id)]
        action["context"] = {"search_default_partner_id": self.id}
        return action
