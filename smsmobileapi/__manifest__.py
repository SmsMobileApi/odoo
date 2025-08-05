# -*- coding: utf-8 -*-
{
    'name': "SMS Mobile API",
    'summary': "Easily send SMS directly from Odoo via your own mobile and the SMSMobileAPI service.",
'description': """
<p><strong>SMS Mobile API</strong> allows you to send SMS directly from Odoo using your own mobile phone, thanks to the official SMSMobileAPI mobile app.</p>

<p><strong>💡 How it works:</strong></p>
<p>All SMS messages sent via this module are sent <strong>from your own mobile device</strong> using your existing mobile plan. This means:</p>

<ul>
  <li><strong>No additional cost</strong> for sending SMS – you use your own mobile plan.</li>
  <li><strong>Recipients see your personal phone number</strong> – not a random or shared number.</li>
  <li><strong>Replies come directly to your phone</strong> – just like a normal SMS conversation.</li>
  <li>No external SMS gateway or third-party provider is required.</li>
</ul>

<p><strong>Requirements:</strong></p>
<ul>
  <li>A free account on <a href="https://smsmobileapi.com" target="_blank">smsmobileapi.com</a> (no credit card required)</li>
  <li>The <strong>SMSMobileAPI mobile app</strong> must be installed on your phone (Android or iOS)</li>
</ul>

<p>Each account comes with a <strong>3-day free trial</strong> to test the service without commitment.</p>

<hr/>
<h3>❗ License & Legal Notice</h3>
<p>This module is <strong>proprietary and protected by copyright</strong>.</p>

<p>Reproduction, distribution, modification, or use of this code without a valid license agreement is strictly prohibited.</p>

<p>To obtain a commercial license or ask questions, please contact us:</p>
<ul>
  <li>📧 <a href="mailto:info@smsmobileapi.com">info@smsmobileapi.com</a></li>
  <li>🌐 <a href="https://www.smsmobileapi.com" target="_blank">https://www.smsmobileapi.com</a></li>
</ul>
""",


    'author': "SMSMobileAPI Team",
    'website': "https://www.smsmobileapi.com/plugin-odoo",
    'category': 'Tools',
    'version': '1.0',
    'depends': ['base', 'account'],
    'data': [
        'security/ir.model.access.csv',
        'views/views.xml',
        'views/sms_mobile_api_menus.xml',
        'views/send_sms_wizard.xml',
        'views/send_invoice_sms_wizard.xml',        # <-- à ajouter (wizard d'envoi facture)
    ],
    'demo': [
        'demo/demo.xml',
    ],
    
    'assets': {
    'web.assets_backend': [
        'sms_mobile_api/static/src/css/custom.css',
    ],
},
    'images': [
        'static/description/icon.png',
        'static/description/banner.png',
    ],
    'license': 'Other proprietary',
    'installable': True,
    'application': True,
    'auto_install': False,
    'sequence': 1,
    # Note: the 'default' key is not supported by Odoo, it will be ignored.
    # 'default': 'sms_mobile_api.sms_mobile_api_action',
}
