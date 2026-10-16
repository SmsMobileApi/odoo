# SMSMobileAPI for Odoo 17

Send SMS from Odoo through a real mobile connected to SMSMobileAPI, then synchronize received SMS and missed, incoming and outgoing calls back to the matching contact.

## Main features

- Send a free-form SMS from a contact or from the SMSMobileAPI application.
- Send invoices, payment reminders, quotations, sales orders and purchase orders by SMS.
- Add an optional secure, expiring document link to a message.
- Choose the connected mobile or let SMSMobileAPI use the first available gateway.
- Schedule a message and optionally shorten URLs.
- Synchronize incoming SMS, API-originated SMS, SMS sent directly from the mobile, and three call types.
- Display the complete timeline on the contact form and in dedicated list, graph and pivot views.
- Use signed Webhook V2 delivery for real-time events with scheduled synchronization as a recovery path.
- Support multiple Odoo companies with isolated configurations and records.

## Requirements

- Odoo 17 Community or Enterprise.
- A SMSMobileAPI account with an active API key.
- The SMSMobileAPI mobile app connected to that account.
- SMS/call synchronization permissions enabled in the mobile app for every channel you want to import.
- A public HTTPS Odoo URL when using Webhook V2 or secure document links.

## Installation

1. Copy the `sms_mobile_api_call` directory to an Odoo addons path.
2. Restart Odoo.
3. Update the Apps list.
4. Search for `SMSMobileAPI` and install the module.
5. Grant the **SMSMobileAPI User** or **SMSMobileAPI Manager** group to authorized users.

## Configuration

1. Open **SMSMobileAPI → Configuration**.
2. Create one configuration for the current company.
3. Paste the SMSMobileAPI account API key. It is stored server-side and is restricted to managers.
4. Read the in-app data disclosure and actively select **I authorize the SMSMobileAPI data exchange**.
5. Click **Test connection** to synchronize connected mobiles.
6. Enable only the SMS and call-log channels required by your organization.

The production API endpoint and webhook details are managed automatically on the server. They are intentionally not displayed or editable in the Odoo interface.

## Privacy and security

- No SMS, call, mobile or permission data is sent or retrieved until a manager actively accepts the in-app disclosure.
- Consent date, user and disclosure version are recorded in Odoo. Withdrawing consent immediately disables automatic synchronization and webhook ingestion.
- To send SMS, Odoo transmits the API credential, recipient number, message text, selected mobile identifier and send options to `api.smsmobileapi.com` over HTTPS.
- For enabled channels, Odoo retrieves SMS content, correspondent numbers, message state and timestamps; call-log type, number, time and duration; and connected-mobile identifiers, status and permission state. Call audio is never accessed.
- The API key is never sent to browser JavaScript and is not written to activity logs or chatter.
- API traffic must use HTTPS and the production host is pinned to `api.smsmobileapi.com` (plain HTTP is accepted only for localhost development).
- Webhooks require HMAC-SHA256 signatures and timestamps no older than five minutes.
- Duplicate webhook/API events are ignored through unique external references.
- Contact matching requires one exact international number. Ambiguous duplicate numbers are deliberately left unmatched.
- Secure document URLs use random tokens, store only the token hash, expire automatically and return `Cache-Control: no-store`.
- Odoo ACLs and multi-company record rules isolate configuration, devices, activities and document links.

## Support

- Product: <https://smsmobileapi.com/>
- API documentation: <https://api.smsmobileapi.com/>
- Support: <https://smsmobileapi.com/help/>
- Email: support@smsmobileapi.com
- Privacy policy: <https://smsmobileapi.com/privacy-policy/>
