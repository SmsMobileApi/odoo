import hashlib
import hmac
import time
from unittest.mock import Mock, patch

from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestSmsMobileApi(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.config = cls.env["smsmobileapi.config"].create({
            "company_id": cls.env.company.id,
            "api_key": "test-key-never-used-on-network",
            "external_data_consent": True,
            "webhook_enabled": True,
            "webhook_signing_secret": "test-signing-secret",
        })
        cls.partner = cls.env["res.partner"].create({
            "name": "API Test Contact",
            "mobile": "+32470000001",
            "company_id": cls.env.company.id,
        })

    def test_phone_matching_is_exact_and_idempotent(self):
        activity_model = self.env["smsmobileapi.activity"]
        values = {
            "event_type": "sms",
            "direction": "incoming",
            "source": "api",
            "status": "received",
            "phone_number": "+32 470 00 00 01",
            "message": "Hello",
            "activity_at": fields.Datetime.now(),
            "external_ref": "received:test-message",
        }
        first = activity_model._create_imported(self.config, dict(values))
        second = activity_model._create_imported(self.config, dict(values))
        self.assertEqual(first, second)
        self.assertEqual(first.partner_id, self.partner)
        self.assertEqual(first.phone_normalized, "+32470000001")
        self.assertEqual(activity_model.search_count([("external_ref", "=", "received:test-message")]), 1)
        self.partner.invalidate_recordset(["smsmobileapi_activity_count"])
        self.assertEqual(self.partner.smsmobileapi_activity_count, 1)

    def test_external_exchange_requires_explicit_consent(self):
        self.config.write({"external_data_consent": False})
        self.assertFalse(self.config.auto_sync)
        self.assertFalse(self.config.webhook_enabled)
        with self.assertRaises(UserError):
            self.env["smsmobileapi.client"].get(
                self.config, "/gateway/mobile/list/", operation="consent test"
            )

        self.config.write({"external_data_consent": True})
        self.assertTrue(self.config.external_data_consent_at)
        self.assertEqual(self.config.external_data_consent_user_id, self.env.user)
        self.assertEqual(self.config.external_data_consent_version, "1.0")

    def test_menu_routes_to_configuration_until_consent_is_granted(self):
        self.config.write({"external_data_consent": False})
        blocked_action = self.env["smsmobileapi.config"].action_open_smsmobileapi_menu()
        self.assertEqual(blocked_action["res_model"], "smsmobileapi.config")
        self.assertEqual(blocked_action["res_id"], self.config.id)
        self.assertEqual(blocked_action["views"][0][1], "form")
        self.assertEqual(blocked_action["context"]["form_view_initial_mode"], "edit")

        self.config.write({"external_data_consent": True})
        allowed_action = self.env["smsmobileapi.config"].action_open_smsmobileapi_menu()
        self.assertEqual(allowed_action["res_model"], "smsmobileapi.conversation")

    def test_api_key_and_consent_can_be_saved_together(self):
        self.config.write({"external_data_consent": False})
        self.config.write({
            "api_key": "replacement-test-key-never-used-on-network",
            "external_data_consent": True,
        })
        self.assertTrue(self.config.external_data_consent)
        self.assertTrue(self.config.external_data_consent_at)
        self.assertEqual(self.config.external_data_consent_user_id, self.env.user)
        self.assertEqual(self.config.external_data_consent_version, "1.0")

    def test_mojibake_is_repaired_without_damaging_unicode(self):
        activity_model = self.env["smsmobileapi.activity"]
        broken = (
            "Salut \u00c3\u00a7a va, d\u00c3\u00a9sol\u00c3\u00a9, "
            "apr\u00c3\u00a8s \u00f0\u009f\u00a4\u00a3"
        )
        self.assertEqual(
            activity_model._repair_text_encoding(broken),
            "Salut ça va, désolé, après 🤣",
        )
        self.assertEqual(
            activity_model._repair_text_encoding("Déjà correct — 日本語"),
            "Déjà correct — 日本語",
        )

        activity = activity_model._create_imported(self.config, {
            "event_type": "sms",
            "direction": "incoming",
            "source": "api",
            "status": "received",
            "phone_number": "+32470000001",
            "message": broken,
            "activity_at": fields.Datetime.now(),
            "external_ref": "received:encoding-test",
        })
        self.assertEqual(activity.message, "Salut ça va, désolé, après 🤣")

    def test_existing_activity_text_is_repaired_on_resynchronization(self):
        activity_model = self.env["smsmobileapi.activity"]
        activity = activity_model.sudo().create({
            "company_id": self.env.company.id,
            "config_id": self.config.id,
            "event_type": "sms",
            "direction": "incoming",
            "source": "api",
            "status": "received",
            "phone_number": "+32470000001",
            "phone_normalized": "+32470000001",
            "message": "D\u00c3\u00a9j\u00c3\u00a0 import\u00c3\u00a9",
            "activity_at": fields.Datetime.now(),
            "external_ref": "received:existing-encoding-test",
        })
        activity_model._create_imported(self.config, {
            "event_type": "sms",
            "direction": "incoming",
            "source": "api",
            "status": "received",
            "phone_number": "+32470000001",
            "message": "D\u00c3\u00a9j\u00c3\u00a0 import\u00c3\u00a9",
            "activity_at": activity.activity_at,
            "external_ref": activity.external_ref,
        })
        activity.invalidate_recordset(["message"])
        self.assertEqual(activity.message, "Déjà importé")

    def test_shared_conversation_tracks_unread_events_and_quick_reply(self):
        activity_model = self.env["smsmobileapi.activity"]
        incoming = activity_model._create_imported(self.config, {
            "event_type": "sms",
            "direction": "incoming",
            "source": "api",
            "status": "received",
            "phone_number": "+32470000001",
            "message": "Can you call me back?",
            "activity_at": fields.Datetime.now(),
            "external_ref": "received:shared-inbox-sms",
        })
        missed_call = activity_model._create_imported(self.config, {
            "event_type": "call_missed",
            "direction": "incoming",
            "source": "mobile",
            "status": "missed",
            "phone_number": "+32470000001",
            "activity_at": fields.Datetime.now(),
            "external_ref": "call:shared-inbox-missed",
        })

        self.assertTrue(incoming.conversation_id)
        self.assertEqual(incoming.conversation_id, missed_call.conversation_id)
        self.assertFalse(incoming.is_read)
        self.assertFalse(missed_call.is_read)
        incoming.conversation_id.invalidate_recordset(["unread_count", "activity_count"])
        self.assertEqual(incoming.conversation_id.unread_count, 2)
        self.assertEqual(incoming.conversation_id.activity_count, 2)

        reply_action = incoming.action_reply()
        self.assertEqual(reply_action["res_model"], "smsmobileapi.send.wizard")
        self.assertEqual(reply_action["context"]["default_recipient_phone"], "+32470000001")
        incoming.invalidate_recordset(["is_read"])
        self.assertTrue(incoming.is_read)

        incoming.conversation_id.action_assign_to_me()
        self.assertEqual(incoming.conversation_id.assigned_user_id, self.env.user)
        incoming.conversation_id.action_mark_read()
        missed_call.invalidate_recordset(["is_read"])
        self.assertTrue(missed_call.is_read)

    def test_business_actions_are_created_from_mobile_activity(self):
        activity = self.env["smsmobileapi.activity"]._create_imported(self.config, {
            "event_type": "sms",
            "direction": "incoming",
            "source": "api",
            "status": "received",
            "phone_number": "+32470000001",
            "message": "Please send me a quotation and call tomorrow.",
            "activity_at": fields.Datetime.now(),
            "external_ref": "received:business-actions",
        })
        wizard_model = self.env["smsmobileapi.business.action.wizard"]
        common = {
            "activity_id": activity.id,
            "company_id": self.env.company.id,
            "partner_id": self.partner.id,
            "phone_number": activity.phone_number,
            "name": "Customer follow-up",
            "description": "Created from the SMS conversation.",
            "assigned_user_id": self.env.user.id,
            "deadline": fields.Date.today(),
        }

        opportunity_wizard = wizard_model.create(dict(common, action_type="opportunity"))
        opportunity_action = opportunity_wizard.action_create()
        self.assertEqual(opportunity_action["res_model"], "crm.lead")
        activity.invalidate_recordset(["crm_lead_id"])
        self.assertEqual(activity.crm_lead_id.partner_id, self.partner)

        task_wizard = wizard_model.create(dict(common, action_type="task"))
        task_action = task_wizard.action_create()
        self.assertEqual(task_action["res_model"], "project.task")
        activity.invalidate_recordset(["project_task_id"])
        self.assertEqual(activity.project_task_id.partner_id, self.partner)

        followup_wizard = wizard_model.create(dict(common, action_type="followup"))
        followup_action = followup_wizard.action_create()
        self.assertEqual(followup_action["res_model"], "mail.activity")
        activity.invalidate_recordset(["followup_activity_id"])
        self.assertTrue(activity.followup_activity_id)

        quotation_wizard = wizard_model.create(dict(common, action_type="quotation"))
        quotation_action = quotation_wizard.action_create()
        self.assertEqual(quotation_action["res_model"], "sale.order")
        activity.invalidate_recordset(["sale_order_id"])
        self.assertEqual(activity.sale_order_id.partner_id, self.partner)

        support_wizard = wizard_model.create(dict(common, action_type="support", priority="2"))
        support_action = support_wizard.action_create()
        self.assertEqual(support_action["res_model"], "smsmobileapi.support.ticket")
        activity.invalidate_recordset(["support_ticket_id"])
        self.assertEqual(activity.support_ticket_id.conversation_id, activity.conversation_id)
        self.assertEqual(activity.support_ticket_id.priority, "2")

    def test_ambiguous_contact_number_is_not_linked(self):
        activity = self.env["smsmobileapi.activity"]._create_imported(self.config, {
            "event_type": "sms",
            "direction": "incoming",
            "source": "api",
            "status": "received",
            "phone_number": "+32470000001",
            "message": "Private message",
            "activity_at": fields.Datetime.now(),
            "external_ref": "received:duplicate-number-test",
        })
        self.assertEqual(activity.partner_id, self.partner)
        self.env["res.partner"].create({
            "name": "Duplicate Number Contact",
            "mobile": "+32470000001",
            "company_id": self.env.company.id,
        })
        activity.invalidate_recordset(["partner_id"])
        partner = self.env["smsmobileapi.activity"]._partner_for_phone(
            self.env.company, "+32470000001"
        )
        self.assertFalse(partner)
        self.assertFalse(activity.partner_id)

    def test_contact_creation_links_previously_synchronized_activity(self):
        activity = self.env["smsmobileapi.activity"].sudo().create({
            "company_id": self.env.company.id,
            "config_id": self.config.id,
            "event_type": "call_missed",
            "direction": "incoming",
            "source": "mobile",
            "status": "missed",
            "phone_number": "+32470000999",
            "phone_normalized": "+32470000999",
            "activity_at": fields.Datetime.now(),
            "external_ref": "call:historical-before-contact",
        })
        self.assertFalse(activity.partner_id)

        partner = self.env["res.partner"].create({
            "name": "Later Contact",
            "phone": "+32 470 00 09 99",
            "company_id": self.env.company.id,
        })

        activity.invalidate_recordset(["partner_id"])
        partner.invalidate_recordset(["smsmobileapi_activity_count"])
        self.assertEqual(activity.partner_id, partner)
        self.assertEqual(partner.smsmobileapi_activity_count, 1)

    def test_contact_matches_phone_when_mobile_is_also_defined(self):
        activity = self.env["smsmobileapi.activity"].sudo().create({
            "company_id": self.env.company.id,
            "config_id": self.config.id,
            "event_type": "sms",
            "direction": "incoming",
            "source": "api",
            "status": "received",
            "phone_number": "+32470000888",
            "phone_normalized": "+32470000888",
            "activity_at": fields.Datetime.now(),
            "external_ref": "sms:secondary-phone-before-contact",
        })
        partner = self.env["res.partner"].create({
            "name": "Two Numbers Contact",
            "mobile": "+32470000777",
            "phone": "+32470000888",
            "company_id": self.env.company.id,
        })

        activity.invalidate_recordset(["partner_id"])
        self.assertEqual(activity.partner_id, partner)

    def test_webhook_signature(self):
        raw = b'{"event":"sms.received"}'
        timestamp = str(int(time.time()))
        signed = timestamp.encode("utf-8") + b"." + raw
        signature = "v1=" + hmac.new(
            b"test-signing-secret", signed, hashlib.sha256
        ).hexdigest()
        self.assertTrue(self.config._verify_webhook_signature(raw, timestamp, signature))
        self.assertFalse(self.config._verify_webhook_signature(raw + b"x", timestamp, signature))
        self.assertFalse(self.config._verify_webhook_signature(raw, "1", signature))

    def test_secure_share_stores_only_token_digest(self):
        attachment = self.env["ir.attachment"].create({
            "name": "test.txt",
            "raw": b"private content",
            "mimetype": "text/plain",
        })
        share, url = self.env["smsmobileapi.document.share"].create_secure_share(
            attachment, self.partner, 2
        )
        raw_token = url.rsplit("/", 1)[-1]
        self.assertNotEqual(share.token_digest, raw_token)
        self.assertEqual(share.token_digest, hashlib.sha256(raw_token.encode()).hexdigest())
        self.assertEqual(self.env["smsmobileapi.document.share"].find_valid_share(raw_token), share)

    def test_api_host_is_pinned(self):
        with self.assertRaises(ValidationError):
            self.config.api_base_url = "https://example.invalid/"

    def test_connected_mobiles_use_production_gateway_payload(self):
        payload = {
            "success": True,
            "connected_now": 2,
            "items": [
                {
                    "sid": "odoo-test-mobile-online",
                    "label": "Office mobile",
                    "phone_number": "+32470000002",
                    "last_check": {
                        "date": "2026-10-15",
                        "time": "23:29:54",
                        "last_connexion_ok_time": 1792099794,
                        "diff_minutes": 0,
                        "status": "green",
                    },
                    "battery_percent": 29,
                    "app_version": "6.1.0.0",
                },
                {
                    "sid": "odoo-test-mobile-offline",
                    "label": "Backup mobile",
                    "last_check": {"status": "red"},
                    "battery_percent": 74,
                },
            ],
        }

        count = self.env["smsmobileapi.mobile"]._sync_from_payload(self.config, payload)

        online = self.env["smsmobileapi.mobile"].search([
            ("company_id", "=", self.env.company.id),
            ("sid", "=", "odoo-test-mobile-online"),
        ])
        offline = self.env["smsmobileapi.mobile"].search([
            ("company_id", "=", self.env.company.id),
            ("sid", "=", "odoo-test-mobile-offline"),
        ])
        self.assertEqual(count, 2)
        self.assertEqual(online.name, "Office mobile")
        self.assertTrue(online.is_online)
        self.assertEqual(online.battery_level, 29)
        self.assertEqual(online.app_version, "6.1.0.0")
        self.assertTrue(online.last_seen_at)
        self.assertFalse(offline.is_online)
        self.assertEqual(offline.battery_level, 74)

    def test_permission_refresh_maps_each_mobile_channel_without_content(self):
        reported = self.env["smsmobileapi.mobile"].create({
            "company_id": self.env.company.id,
            "config_id": self.config.id,
            "sid": "permission-mobile-reported",
            "name": "Permission mobile",
            "active": True,
        })
        not_reported = self.env["smsmobileapi.mobile"].create({
            "company_id": self.env.company.id,
            "config_id": self.config.id,
            "sid": "permission-mobile-without-report",
            "name": "Waiting mobile",
            "active": True,
            "permission_sms_received": "granted",
        })
        response = Mock()
        response.status_code = 200
        response.is_redirect = False
        response.content = b'{"ok":true,"statuses":[]}'
        response.json.return_value = {
            "ok": True,
            "statuses": [{
                "device_id": reported.sid,
                "sms_received_granted": 1,
                "call_missed_granted": 0,
                "call_incoming_granted": "1",
                "call_outgoing_granted": "0",
                "app_version": "6.1.0.0",
                "checked_at": "2026-10-15 20:00:00",
            }],
        }

        with patch(
            "odoo.addons.sms_mobile_api_call.models.api_client.requests.request",
            return_value=response,
        ) as request_call:
            result = self.config.action_refresh_mobile_permissions()

        reported.invalidate_recordset()
        not_reported.invalidate_recordset()
        self.assertEqual(reported.permission_sms_received, "granted")
        self.assertEqual(reported.permission_call_missed, "missing")
        self.assertEqual(reported.permission_call_incoming, "granted")
        self.assertEqual(reported.permission_call_outgoing, "missing")
        self.assertEqual(reported.app_version, "6.1.0.0")
        self.assertTrue(reported.permission_checked_at)
        self.assertEqual(not_reported.permission_sms_received, "unknown")
        self.assertEqual(result["params"]["type"], "success")

        call = request_call.call_args
        self.assertEqual(
            call.args[1],
            "https://dashboard.smsmobileapi.com/api/integrations/mobile-permission-statuses",
        )
        self.assertEqual(call.kwargs["data"], {"api_key": "test-key-never-used-on-network"})
        self.assertNotIn("message", call.kwargs["data"])
        self.assertNotIn("phone_number", call.kwargs["data"])

    def test_send_sms_creates_queued_activity_without_exposing_key(self):
        mobile = self.env["smsmobileapi.mobile"].create({
            "company_id": self.env.company.id,
            "config_id": self.config.id,
            "sid": "remembered-mobile",
            "name": "Remembered mobile",
            "active": True,
        })
        wizard = self.env["smsmobileapi.send.wizard"].create({
            "partner_id": self.partner.id,
            "recipient_phone": "+32470000001",
            "company_id": self.env.company.id,
            "mobile_id": mobile.id,
            "message": "A safe test message",
        })
        response = Mock()
        response.status_code = 200
        response.is_redirect = False
        response.content = b'{"result":{"error":0,"sent":"1","id":"test-guid"}}'
        response.json.return_value = {"result": {"error": 0, "sent": "1", "id": "test-guid"}}
        with patch("odoo.addons.sms_mobile_api_call.models.api_client.requests.request", return_value=response) as request_call:
            wizard.action_send()
        self.assertEqual(wizard.state, "sent")
        self.assertEqual(wizard.sent_activity_id.external_ref, "odoo:test-guid")
        self.assertNotIn("test-key-never-used-on-network", wizard.sent_activity_id.message)
        self.assertEqual(request_call.call_args.kwargs["data"]["apikey"], "test-key-never-used-on-network")
        self.assertEqual(request_call.call_args.kwargs["data"]["sIdentifiant"], mobile.sid)

        next_wizard = self.env["smsmobileapi.send.wizard"].create({
            "partner_id": self.partner.id,
            "recipient_phone": "+32470000001",
            "company_id": self.env.company.id,
            "message": "The next message",
        })
        self.assertEqual(next_wizard.mobile_id, mobile)

        mobile.active = False
        defaults = self.env["smsmobileapi.send.wizard"].default_get(["company_id", "mobile_id"])
        self.assertFalse(defaults.get("mobile_id"))
