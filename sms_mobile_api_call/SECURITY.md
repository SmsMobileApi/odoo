# Security policy

## Supported version

Security fixes are applied to the latest `17.0.x` release of this module.

## Reporting a vulnerability

Please report security issues privately through the support channel at <https://smsmobileapi.com/help/>. Do not include production API keys, passwords, message content or customer data in the report.

## Security model

- The SMSMobileAPI account key is used only by server-side Python code.
- Production API requests are pinned to `https://api.smsmobileapi.com` and redirects are rejected.
- Only members of the SMSMobileAPI Manager group can read or change connection credentials.
- Webhook V2 requests require HMAC-SHA256 signatures and a timestamp within five minutes.
- The webhook payload is limited to 1 MB and duplicate event references are rejected.
- Secure document URLs store only a SHA-256 token digest, expire automatically and use no-store response headers.
- Exact E.164 matching and duplicate-number rejection prevent an activity from being attached to an ambiguous contact.
- Company-scoped access rules isolate configurations, devices, activities and shared documents.
