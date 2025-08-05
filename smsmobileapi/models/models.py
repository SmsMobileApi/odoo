# -*- coding: utf-8 -*-

import json
import requests
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError

class SMSMobileApi(models.Model):
    _name = 'sms.mobile.api'
    _rec_name = 'phone_number'

    api_key = fields.Char(string="API Key", required=True)
    phone_number = fields.Char(string="Phone Number", required=True)
    complete_url = fields.Char(string="Complete Url", compute='_get_complete_url')
    message_status = fields.Text(string="Message Status")

    # Static values
    _api_url_string = 'https://api.smsmobileapi.com/sendsms/'
    _message = 'TEST_FROM_ODOO'

    @api.depends('phone_number', 'api_key')
    
    
    
    
    def send_sms_mobile_api(self, recipient, message, send_sms_x=False, send_whatsapp_x=False):
        self.ensure_one()
        import urllib.parse
        import requests
        
        send_sms_x = "1" if str(send_sms_x).lower() in ("1", "true", "yes") else "0"
        send_whatsapp_x = "1" if str(send_whatsapp_x).lower() in ("1", "true", "yes") else "0"
        
        if not self.api_key or not recipient or not message:
            raise ValueError("API key, recipient and message required.")

        base_url = 'https://api.smsmobileapi.com/sendsms/'
        params = {
            'recipients': recipient,
            'message': message,
            'apikey': self.api_key,
            'from':'odoo',
            'sendsms':send_sms_x,
            'sendwa':send_whatsapp_x,
        }
        url = base_url + '?' + urllib.parse.urlencode(params)
        try:
            response = requests.post(url)
            if response.status_code == 200:
                result = response.json()
                return result
            else:
                return {'error': f"HTTP {response.status_code}"}
        except Exception as e:
            return {'error': str(e)}
    
    
    
    
    
    
    def _get_complete_url(self):
        for record in self:
            record.complete_url = f"{self._api_url_string}?recipients={record.phone_number}&message={self._message}&apikey={record.api_key}&from=odoo"

    
    def test_sms_button(self):
        for record in self:
            # Utilisation du numéro et du message de test
            recipient = record.phone_number
            message = 'TEST_FROM_ODOO'
            result = record.send_sms_mobile_api(recipient, message)
            # Gérer le retour et afficher le statut
            if 'error' in result:
                record.message_status = f"Error: {result['error']}"
            elif "'sent': '1'" in str(result.get('result')):
                record.message_status = "SMS sent successfully."
            else:
                record.message_status = f"SMS not sent. Server response: {result.get('result')}"
            

    @api.model
    def create(self, vals):
        if self.search_count([]) > 0:
            raise UserError(_("Only one configuration allowed. Please edit the existing configuration instead of creating a new one."))
        return super().create(vals)


class ResPartner(models.Model):
    _inherit = 'res.partner'

    def action_open_send_sms_wizard(self):
        self.ensure_one()
        phone_number = self.mobile or self.phone or ''
        return {
            'type': 'ir.actions.act_window',
            'name': 'Send SMS via SMSMobileAPI',
            'res_model': 'sms_mobile_api.send_sms_wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_partner_id': self.id,
                'default_phone': phone_number,
            }
        }
        
        
def action_open_send_invoice_sms_wizard(self):
    self.ensure_one()
    return {
        'type': 'ir.actions.act_window',
        'name': 'Send Invoice by SMS',
        'res_model': 'sms_mobile_api.send_invoice_sms_wizard',
        'view_mode': 'form',
        'target': 'new',
        'context': {
            'default_invoice_id': self.id,
        },
    }
       

class AccountMove(models.Model):
    _inherit = 'account.move'

    def action_open_send_sms_invoice_wizard(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Send Invoice by SMS',
            'res_model': 'sms_mobile_api.send_invoice_sms_wizard',
            'view_mode': 'form',
            'target': 'new',  # Ouvre dans un popup
            'context': {
                'default_invoice_id': self.id
            }
        }        
        
class SendInvoiceSMSWizard(models.TransientModel):
    _name = 'sms_mobile_api.send_invoice_sms_wizard'
    _description = 'Send Invoice by SMS Wizard'

    invoice_id = fields.Many2one('account.move', string='Invoice', required=True)
    phone = fields.Char("Mobile", required=True)
    message = fields.Text("Message", required=True)
    send_sms_x = fields.Boolean(string="Send by SMS", default=True)
    send_whatsapp_x = fields.Boolean(string="Send by WhatsApp", default=False)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        invoice = self.env['account.move'].browse(self.env.context.get('default_invoice_id'))
        partner = invoice.partner_id
        phone = partner.mobile or partner.phone or ''
        company = invoice.company_id.name
        invoice_number = invoice.name or ''
        invoice_date = invoice.invoice_date or ''
        due_date = invoice.invoice_date_due or ''
        msg = (
            f"Dear customer, please pay invoice n°{invoice_number} dated {invoice_date} "
            f"before {due_date}.\nBest regards,\n{company}"
        )
        res.update({
            'invoice_id': invoice.id,
            'phone': phone,
            'message': msg,
        })
        return res

    def send_sms(self):
        self.ensure_one()
        config = self.env['sms.mobile.api'].search([], limit=1)
        if not config or not config.api_key or not config.phone_number:
            raise ValidationError("No API configuration found. Please configure SMS Mobile API first.")
        if not self.phone or not self.message:
            raise ValidationError("Please provide both the phone number and the message.")

        # --- Utilise la fonction centralisée ---
        result = config.send_sms_mobile_api(
            self.phone,
            self.message,
            self.send_sms_x,
            self.send_whatsapp_x
        )
        if 'error' in result and result['error']:
            status_msg = f"Error sending message: {result['error']}"
        elif "'sent': '1'" in str(result.get('result')):
            status_msg = "Message sent successfully."
        else:
            status_msg = f"Not sent. Server response: {str(result.get('result'))}"

        if self.invoice_id:
            self.invoice_id.message_post(
                body=f"Message sent attempt to {self.phone}:<br>{self.message}<br><b>Status:</b> {status_msg}"
            )
        return {'type': 'ir.actions.act_window_close'}
        
        
class SmsMobileApiLog(models.Model):
    _name = 'sms.mobile.api.log'   # ← Ce nom doit correspondre exactement !
    _description = 'SMS Mobile API Log'

    date = fields.Datetime(string='Date')
    phone = fields.Char(string='Phone')
    message = fields.Text(string='Message')
    channel = fields.Selection([('sms', 'SMS'), ('whatsapp', 'WhatsApp')], string='Channel')
    status = fields.Char(string='Status')
