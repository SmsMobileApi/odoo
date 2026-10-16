import json
import logging

from odoo import http
from odoo.http import request


_logger = logging.getLogger(__name__)


class SmsMobileApiWebhookController(http.Controller):
    @http.route(
        "/smsmobileapi/webhook/<string:path_token>",
        type="http", auth="public", methods=["POST"], csrf=False, sitemap=False,
    )
    def webhook(self, path_token, **kwargs):
        if not path_token or len(path_token) > 256:
            return self._json_response({"ok": False, "error": "NOT_FOUND"}, 404)
        request_length = request.httprequest.content_length or 0
        if request_length > 1024 * 1024:
            return self._json_response({"ok": False, "error": "PAYLOAD_TOO_LARGE"}, 413)
        raw_body = request.httprequest.get_data(cache=True)
        if len(raw_body) > 1024 * 1024:
            return self._json_response({"ok": False, "error": "PAYLOAD_TOO_LARGE"}, 413)
        config = request.env["smsmobileapi.config"].sudo().search([
            ("webhook_path_token", "=", path_token),
            ("webhook_enabled", "=", True),
            ("external_data_consent", "=", True),
            ("active", "=", True),
        ], limit=1)
        if not config:
            return self._json_response({"ok": False, "error": "NOT_FOUND"}, 404)
        timestamp = request.httprequest.headers.get("X-SMSMobileAPI-Timestamp")
        signature = request.httprequest.headers.get("X-SMSMobileAPI-Signature")
        if not config._verify_webhook_signature(raw_body, timestamp, signature):
            _logger.warning("Rejected SMSMobileAPI webhook signature for company %s", config.company_id.id)
            return self._json_response({"ok": False, "error": "INVALID_SIGNATURE"}, 401)
        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            return self._json_response({"ok": False, "error": "INVALID_JSON"}, 400)
        event_name = request.httprequest.headers.get("X-SMSMobileAPI-Event") or payload.get("event")
        event_id = request.httprequest.headers.get("X-SMSMobileAPI-Event-ID") or payload.get("event_id")
        try:
            request.env["smsmobileapi.activity"].sudo().ingest_webhook(config, event_name, event_id, payload)
        except Exception:
            _logger.exception("SMSMobileAPI webhook ingestion failed for company %s", config.company_id.id)
            return self._json_response({"ok": False, "error": "PROCESSING_FAILED"}, 500)
        return self._json_response({"ok": True}, 200)

    def _json_response(self, payload, status):
        return request.make_response(
            json.dumps(payload, separators=(",", ":")),
            headers=[
                ("Content-Type", "application/json; charset=utf-8"),
                ("Cache-Control", "no-store"),
                ("X-Content-Type-Options", "nosniff"),
            ],
            status=status,
        )
