import json
import logging
from urllib.parse import urljoin

import requests

from odoo import _, models
from odoo.exceptions import UserError


_logger = logging.getLogger(__name__)

MOBILE_PERMISSION_STATUS_URL = (
    "https://dashboard.smsmobileapi.com/api/integrations/mobile-permission-statuses"
)


class SmsMobileApiClient(models.AbstractModel):
    _name = "smsmobileapi.client"
    _description = "SMSMobileAPI HTTP Client"

    def _safe_error(self, operation, response=None):
        status = response.status_code if response is not None else None
        if status:
            return _("SMSMobileAPI could not complete %(operation)s (HTTP %(status)s).", operation=operation, status=status)
        return _("SMSMobileAPI could not complete %(operation)s.", operation=operation)

    def _request(self, config, method, endpoint, *, params=None, data=None, operation=None):
        config.ensure_one()
        config._ensure_external_data_consent()
        config._check_api_base_url()
        operation = operation or endpoint
        payload = dict(data or {})
        query = dict(params or {})
        if method.upper() == "GET":
            query["apikey"] = config.api_key
        else:
            payload["apikey"] = config.api_key

        url = urljoin(config.api_base_url.rstrip("/") + "/", endpoint.lstrip("/"))
        try:
            response = requests.request(
                method.upper(),
                url,
                params=query,
                data=payload,
                headers={
                    "Accept": "application/json",
                    "User-Agent": "SMSMobileAPI-Odoo/17.0",
                },
                timeout=(5, 25),
                allow_redirects=False,
            )
        except requests.RequestException as exc:
            _logger.warning("SMSMobileAPI transport error during %s: %s", operation, exc.__class__.__name__)
            raise UserError(self._safe_error(operation)) from None

        if response.is_redirect:
            _logger.warning("SMSMobileAPI rejected redirect during %s", operation)
            raise UserError(self._safe_error(operation, response))
        if response.status_code < 200 or response.status_code >= 300:
            _logger.warning("SMSMobileAPI HTTP %s during %s", response.status_code, operation)
            raise UserError(self._safe_error(operation, response))
        if len(response.content) > 5 * 1024 * 1024:
            raise UserError(_("SMSMobileAPI returned an unexpectedly large response."))
        try:
            body = response.json()
        except (ValueError, json.JSONDecodeError):
            raise UserError(_("SMSMobileAPI returned an unreadable response.")) from None

        if isinstance(body, dict):
            result = body.get("result")
            error = body.get("error")
            if isinstance(result, dict) and result.get("error"):
                error = result.get("error")
            if error:
                raise UserError(_("SMSMobileAPI rejected the request. Check the account key and configuration."))
        return body

    def get(self, config, endpoint, params=None, operation=None):
        return self._request(config, "GET", endpoint, params=params, operation=operation)

    def post(self, config, endpoint, data=None, operation=None):
        return self._request(config, "POST", endpoint, data=data, operation=operation)

    def mobile_permission_statuses(self, config):
        config.ensure_one()
        config._ensure_external_data_consent()
        operation = _("mobile permission refresh")
        try:
            response = requests.request(
                "POST",
                MOBILE_PERMISSION_STATUS_URL,
                data={"api_key": config.api_key},
                headers={
                    "Accept": "application/json",
                    "User-Agent": "SMSMobileAPI-Odoo/17.0",
                },
                timeout=(5, 20),
                allow_redirects=False,
            )
        except requests.RequestException as exc:
            _logger.warning(
                "SMSMobileAPI permission transport error: %s", exc.__class__.__name__
            )
            raise UserError(self._safe_error(operation)) from None

        if response.is_redirect or response.status_code < 200 or response.status_code >= 300:
            raise UserError(self._safe_error(operation, response))
        if len(response.content) > 1024 * 1024:
            raise UserError(_("SMSMobileAPI returned an unexpectedly large response."))
        try:
            body = response.json()
        except (ValueError, json.JSONDecodeError):
            raise UserError(_("SMSMobileAPI returned an unreadable response.")) from None
        if not isinstance(body, dict) or not body.get("ok") or not isinstance(body.get("statuses"), list):
            raise UserError(_("SMSMobileAPI could not refresh the mobile permission status."))
        return body["statuses"]
