# Changelog

## 17.0.1.2.3

- Replace non-ASCII presentation symbols with HTML entities for consistent rendering on Odoo Apps.

## 17.0.1.2.2

- Prepared the add-on metadata and documentation for Odoo Apps publication.
- Clarified the mandatory consent-first setup sequence.
- Aligned the Marketplace description with Odoo external-link rules.
- Kept the in-product privacy disclosure and consent guard unchanged.

## 17.0.1.2.1 — 2026-10-16

- Makes the required SMSMobileAPI data-exchange authorization checkbox prominent and action-oriented.
- Opens Configuration directly in edit mode whenever authorization is still missing.
- Routes the SMSMobileAPI application and its feature menus through the authorization checkpoint.
- Keeps regular users blocked with a clear instruction until a manager grants authorization.

## 17.0.1.2.0 — 2026-10-16

- Adds a prominent in-app disclosure before any exchange with api.smsmobileapi.com.
- Requires explicit, recorded user consent before connection tests, synchronization, webhooks or mobile-permission checks.
- Lets administrators withdraw consent at any time, automatically stopping background synchronization and webhook ingestion.
- Revokes consent when the account API key changes so the new connection must be authorized deliberately.
- Documents exactly which SMS, call-log, mobile and permission data is transmitted or retrieved, and confirms that call audio is never accessed.
- States that a SMSMobileAPI account and the official mobile application are required.
- Adds six anonymized, real-product screenshots and a complete English Marketplace presentation.
- Adds support contact support@smsmobileapi.com.

## 17.0.1.1.0 — 2026-10-16

- Adds a shared SMS inbox grouped by contact and international phone number.
- Adds a professional SMS and call conversation timeline inside every contact.
- Adds quick replies, direct response actions and per-mobile timeline filtering.
- Tracks unread incoming events, assignment, priority, resolution and archiving.
- Adds internal team notes and Odoo follow-up activities to every conversation.
- Creates CRM opportunities, project tasks, reminders, quotations and support tickets from incoming events.
- Links SMS and calls to existing quotations, sales orders and customer invoices.
- Adds delivered SMS status support and refreshes queued statuses during synchronization.
- Migrates historical activity into conversations without producing false unread alerts.

## 17.0.1.0.7 — 2026-10-16

- Repairs malformed accents and emojis returned by upstream SMS history endpoints.
- Preserves already-correct Unicode text while normalizing only valid mojibake sequences.
- Refreshes existing activity text safely when the same SMS is synchronized again.

## 17.0.1.0.6 — 2026-10-15

- Adds a per-mobile access status table to Configuration.
- Shows whether received SMS and missed, incoming and outgoing calls are allowed.
- Adds a manual refresh action backed by a content-free authenticated endpoint.
- Never retrieves message bodies, phone numbers, contacts or call content for this check.

## 17.0.1.0.5 — 2026-10-15

- Remembers the last mobile explicitly used by each Odoo user and company.
- Preselects that mobile for the next SMS, including after a new login.
- Safely falls back to the company default or automatic selection when the remembered mobile is unavailable.

## 17.0.1.0.4 — 2026-10-15

- Automatically links previously synchronized SMS and call activity when a matching contact is created.
- Reconciles activity when a contact phone, mobile, company or archive state changes.
- Keeps activity unassigned when the same number belongs to multiple contacts.
- Matches both the mobile and phone fields independently.

## 17.0.1.0.3 — 2026-10-15

- Fixed connected mobile synchronization with the current production gateway response.
- Added online status, battery percentage and last-contact mapping for connected mobiles.

## 17.0.1.0.0 — 2026-10-15

- First Odoo 17 release.
- Free-form SMS sending from contacts and the dedicated SMSMobileAPI app.
- SMS delivery for invoices, payment reminders, quotations, sales orders and purchase orders.
- Optional secure, expiring document links.
- Received SMS, API-sent SMS and mobile-sent SMS synchronization.
- Missed, incoming and outgoing call synchronization.
- Contact timeline, dedicated activity views, graphs and pivot analysis.
- Connected mobile selection and automatic gateway fallback.
- Scheduled sending and URL shortening.
- Signed Webhook V2 endpoint plus scheduled recovery synchronization.
- Multi-company ACLs and record rules.
- Exact, ambiguity-safe phone matching.
- English source interface and French translation.
