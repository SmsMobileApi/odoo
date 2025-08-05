from odoo import models, fields, api, _
from odoo.exceptions import UserError

class SendInvoiceSmsWizard(models.TransientModel):
    _name = 'sms_mobile_api.send_invoice_sms_wizard'
    _description = 'Send Invoice by SMS Wizard'

    invoice_id = fields.Many2one('account.move', string='Invoice', required=True, readonly=True)
    phone = fields.Char('Phone', required=True)
    message = fields.Text('Message', required=True)
    send_sms_x = fields.Boolean(string="Send by SMS", default=True)
    send_whatsapp_x = fields.Boolean(string="Send by WhatsApp", default=False)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        invoice_id = self.env.context.get('default_invoice_id') or self.env.context.get('active_id')
        if invoice_id:
            invoice = self.env['account.move'].browse(invoice_id)
            partner = invoice.partner_id
            phone = partner.mobile or partner.phone or ''
            company = invoice.company_id.name
            invoice_number = invoice.name or invoice.id
            invoice_date = invoice.invoice_date or ''
            due_date = invoice.invoice_date_due or ''
            amount = invoice.amount_total or 0.0
            currency = invoice.currency_id and invoice.currency_id.symbol or ''
            msg = (
                f"Dear customer, please pay invoice n°{invoice_number} "
                f"dated {invoice_date} for {amount} {currency} before {due_date}.\n"
                f"Best regards,\n{company}"
            )
            res.update({
                'invoice_id': invoice.id,
                'phone': phone,
                'message': msg,
            })
        return res

    def send_sms(self):
        for wizard in self:
            if not wizard.phone or not wizard.message:
                raise UserError(_("Phone and message are required."))

            config = self.env['sms.mobile.api'].search([], limit=1)
            if not config or not config.api_key or not config.phone_number:
                raise UserError(_("No API configuration found. Please configure SMS Mobile API first."))

            # --- Utilisation de la fonction centralisée ---
            result = config.send_sms_mobile_api(
                wizard.phone,
                wizard.message,
                wizard.send_sms_x,
                wizard.send_whatsapp_x
            )

            # --- Analyse du résultat & log ---
            if 'error' in result:
                status_msg = _("Error sending SMS: %s") % result['error']
            elif "'sent': '1'" in str(result.get('result')):
                status_msg = _("SMS sent successfully.")
            else:
                status_msg = _("SMS not sent. Server response: %s") % str(result.get('result'))

            invoice = wizard.invoice_id
            if invoice:
                invoice.message_post(
                    body=_(
                        "SMS sent to %(phone)s: %(msg)s Status:  %(status)s" % {
                            'phone': wizard.phone,
                            'msg': wizard.message.replace('\n', ' '),
                            'status': status_msg
                        }
                    )
                )
        return {'type': 'ir.actions.act_window_close'}
