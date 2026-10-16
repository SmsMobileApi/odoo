# SMSMobileAPI for Odoo 17

This repository contains the free `sms_mobile_api_call` add-on for Odoo 17.

It connects Odoo to a physical mobile registered with SMSMobileAPI so teams can:

- send SMS from contacts, invoices, quotations, sales orders and purchase orders;
- synchronize received and sent SMS with the matching contact;
- synchronize missed, incoming and outgoing call metadata;
- work from a shared SMS inbox;
- turn mobile events into Odoo opportunities, tasks, follow-ups, quotations or support tickets.

## Requirements

- Odoo 17 Community or Enterprise on Odoo.sh or a self-hosted server;
- a SMSMobileAPI account and API key;
- the official SMSMobileAPI mobile application connected to the account;
- the required SMS, call-log and background permissions enabled on the mobile.

The module contains Python code and therefore cannot be installed on standard Odoo Online.

## Installation

1. Place `sms_mobile_api_call` in an Odoo addons path.
2. Restart Odoo and update the Apps list.
3. Install **SMSMobileAPI SMS & Calls**.
4. Open **SMSMobileAPI → Configuration**.
5. Read and accept the data-exchange disclosure, paste the API key, save, and test the connection.

## External service and consent

The add-on communicates over HTTPS with `api.smsmobileapi.com`. Before any connection test, SMS send, synchronization, permission refresh or webhook ingestion, an administrator must explicitly accept the in-product disclosure. The consent user, time and disclosure version are recorded. Withdrawing consent stops automatic synchronization and webhook ingestion.

The Marketplace description and the in-product disclosure list the exact data transmitted and retrieved. No call audio is accessed or transferred.

## Support and security

- Support: support@smsmobileapi.com
- Product documentation: https://smsmobileapi.com/odoo/
- Privacy policy: https://smsmobileapi.com/privacy-policy/

Please report security issues privately to support@smsmobileapi.com and never include production API keys or customer message content in a public issue.

## License

LGPL-3.0. See `sms_mobile_api_call/LICENSE`.
