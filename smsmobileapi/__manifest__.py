# -*- coding: utf-8 -*-
{
    'name': "SMS Mobile API",
    'summary': "Easily send SMS directly from Odoo via your own mobile and the SMSMobileAPI service.",
    'description': """
SMS Mobile API empowers your Odoo with seamless SMS messaging.
Send and track SMS directly from contacts, invoices, and other objects using your own mobile and the SMSMobileAPI platform.
Features include:
- Simple API configuration
- One-click SMS sending from contact pages
- Full history of sent messages in Odoo's chatter
- No third-party SMS gateways: use your own device and plan
- Perfect for notifications, alerts, and two-way communications
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

    
    'installable': True,
    'application': True,
    'auto_install': False,
    'sequence': 1,
    # Note: the 'default' key is not supported by Odoo, it will be ignored.
    # 'default': 'sms_mobile_api.sms_mobile_api_action',
}
