# 📲 SMSMobileAPI – Odoo Integration

Official Odoo module to send SMS directly from your Odoo instance using [SMSMobileAPI](https://smsmobileapi.com/plugin-odoo/).

## 🚀 Features

- ✅ Send SMS from:
  - **Contacts (res.partner)**: directly from the contact form or list view
  - **Invoices (account.move)**: pre-filled message with all invoice details
- ✅ Uses your **SMSMobileAPI account** and your **own mobile phone**
- ✅ Configuration via Odoo Settings
- ✅ Works with the default Odoo database structure

## 🛠️ Setup Instructions

1. Copy the `smsmobileapi` module into your Odoo `addons` folder.
2. Restart Odoo and update the apps list.
3. Install the module `SMSMobileAPI`.
4. Go to **Settings > SMS Mobile API** to configure:
   - Your **API Key**
   - Your **linked mobile number**

## 📝 Usage

- Open any **Contact** or **Invoice**
- Click the **"Send SMS"** button
- A pop-up will show:
  - The phone number (pre-filled)
  - A default message based on contact or invoice data
- You can edit the message before sending

> 💡 SMS are sent **via your mobile phone**, not through a third-party SMS gateway.

## 🧪 Current Limitations

- ❌ SMS can only be sent from Contacts and Invoices
- ❌ No custom templates (yet)
- ❌ No logging/tracking inside Odoo (for now)

## 🔜 Coming Soon

The next version will include:
- SMS from **any model or custom document**
- Message templates
- History of sent SMS
- Automated SMS via server actions or workflows

## 📦 Compatibility

- Odoo 17 (Community & Enterprise)

## 🔐 License

**Proprietary license** – all rights reserved.

You are not allowed to reuse or distribute this code without permission.  
For commercial usage, please contact: [info@smsmobileapi.com](mailto:info@smsmobileapi.com)

## 🔗 Related Integrations

- ✅ WooCommerce Plugin  
- ✅ Shopify App  
- ✅ Zapier Integration  
- ✅ Python Library  
- ✅ Mobile App (Android & iOS)

---

Made with ❤️ by [SMSMobileAPI](https://smsmobileapi.com)
