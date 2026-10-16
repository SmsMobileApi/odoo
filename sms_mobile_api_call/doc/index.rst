SMSMobileAPI for Odoo
=====================

SMSMobileAPI connects Odoo to the mobile you already use. Send an SMS from a contact, invoice, quotation, sales order or purchase order, then keep incoming replies and call activity attached to the right contact.

Quick start
-----------

#. Install the SMSMobileAPI mobile app and connect it to your SMSMobileAPI account.
#. In the mobile app, enable synchronization for received SMS and the call channels you want to share.
#. In Odoo, grant an administrator the **SMSMobileAPI Manager** access group.
#. Open **SMSMobileAPI > Configuration** and read the data-exchange disclosure.
#. Actively select **I authorize the SMSMobileAPI data exchange**, paste the account API key, and save.
#. Test the connection and verify the connected mobiles and enabled channels.
#. Grant day-to-day operators the **SMSMobileAPI User** group.
#. Open a contact and click **Send SMS**.

What users can do
-----------------

* Write a free-form SMS and select the sending mobile.
* Leave the mobile empty to use the first available gateway.
* Schedule an SMS for later.
* Send invoices, reminders, quotations and orders through secure portal links.
* Add an arbitrary document through an expiring, random HTTPS link.
* Read received and sent SMS on the contact form.
* Review missed, incoming and outgoing calls, including duration when supplied by the mobile.
* Analyze communication volume in list, graph and pivot views.

Delivery model
--------------

A successful API response means that SMSMobileAPI accepted the message. The connected phone then processes the queued SMS. Mobile operating-system background restrictions and the carrier may introduce a short delay.

Synchronization can use both mechanisms:

* **Signed Webhook V2** for immediate event delivery.
* **Scheduled recovery synchronization** to recover events after connectivity interruptions.

Security
--------

The account API key is available only to SMSMobileAPI managers and is used exclusively on the Odoo server. Webhook requests require a valid HMAC-SHA256 signature and a fresh timestamp. Contact matching is exact and intentionally refuses ambiguous duplicate phone numbers.

Document links store only a SHA-256 token digest, expire after a configurable period and are served with no-cache/no-store browser headers.

Troubleshooting
---------------

No received SMS or calls
~~~~~~~~~~~~~~~~~~~~~~~~

Open the SMSMobileAPI mobile app and verify that each required channel is enabled. Confirm that Android permits the required SMS, call-log and background permissions, then run **Synchronize now** in Odoo.

No contact match
~~~~~~~~~~~~~~~~

Store the contact number in international E.164 format, for example ``+32470000000``. If two contacts share the same normalized number, the activity stays unassigned to prevent accidental disclosure.

SMS queued but not visible on the phone
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Verify that a connected mobile is online and allowed to run in the background. The API queue and the mobile carrier can require a short processing time.
