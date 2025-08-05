from odoo import models, fields, _
from odoo.exceptions import UserError

class SendSmsWizard(models.TransientModel):
    _name = 'sms_mobile_api.send_sms_wizard'
    _description = 'Send SMS via SMSMobileAPI'

    partner_id = fields.Many2one('res.partner', string='Contact')
    phone = fields.Char(string='Phone Number', required=True)
    message = fields.Text(string='Message', required=True)
    
    
    send_sms_x = fields.Boolean(string="Send by SMS", default=True)
    send_whatsapp_x = fields.Boolean(string="Send by WhatsApp", default=False)

    def send_sms(self):
        config = self.env['sms.mobile.api'].search([], limit=1)
        if not config or not config.api_key:
            raise UserError(_("Please configure your SMSMobileAPI settings first (API Key missing)."))

        for wizard in self:
            if not wizard.phone or not wizard.message:
                raise UserError(_("Phone and message are required!"))
            # Appel de la fonction centralisée
            result = config.send_sms_mobile_api(wizard.phone, wizard.message, wizard.send_sms_x, wizard.send_whatsapp_x)
            # Gestion du retour
            if 'error' in result:
                raise UserError(_("Error sending SMS: %s") % result['error'])
            elif "'sent': '1'" in str(result.get('result')):
                # Ajoute une note dans l'historique du partenaire
                if wizard.partner_id:
                    wizard.partner_id.message_post(
                        body=(
                            "SMS sent via SMSMobileAPI: "
                            " To:  %s "
                            " Content:  %s"
                        ) % (wizard.phone, wizard.message.replace('\n', ' ')),
                        subject="SMS sent"
                    )
            else:
                raise UserError(_("SMS not sent. Server response: %s") % str(result.get('result')))
        return {'type': 'ir.actions.act_window_close'}
