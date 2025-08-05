# -*- coding: utf-8 -*-
# from odoo import http


# class SmsMobileApi(http.Controller):
#     @http.route('/sms_mobile_api/sms_mobile_api', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/sms_mobile_api/sms_mobile_api/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('sms_mobile_api.listing', {
#             'root': '/sms_mobile_api/sms_mobile_api',
#             'objects': http.request.env['sms_mobile_api.sms_mobile_api'].search([]),
#         })

#     @http.route('/sms_mobile_api/sms_mobile_api/objects/<model("sms_mobile_api.sms_mobile_api"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('sms_mobile_api.object', {
#             'object': obj
#         })

