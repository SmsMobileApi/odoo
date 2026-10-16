from odoo import fields, http
from odoo.http import content_disposition, request


class SmsMobileApiDocumentController(http.Controller):
    @http.route(
        "/smsmobileapi/document/<string:token>",
        type="http", auth="public", methods=["GET"], csrf=False, sitemap=False,
    )
    def secure_document(self, token, **kwargs):
        if not token or len(token) > 256:
            return request.not_found()
        share = request.env["smsmobileapi.document.share"].sudo().find_valid_share(token)
        if not share or not share.attachment_id:
            return request.not_found()
        attachment = share.attachment_id.sudo()
        share.write({
            "access_count": share.access_count + 1,
            "last_access_at": fields.Datetime.now(),
        })
        headers = [
            ("Content-Type", attachment.mimetype or "application/octet-stream"),
            ("Content-Disposition", content_disposition(attachment.name or "document")),
            ("Cache-Control", "no-store, private, max-age=0"),
            ("Pragma", "no-cache"),
            ("X-Content-Type-Options", "nosniff"),
            ("Referrer-Policy", "no-referrer"),
            ("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'"),
        ]
        return request.make_response(attachment.raw or b"", headers=headers)
