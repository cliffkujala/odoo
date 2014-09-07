# -*- coding: utf-8 -*-

import base64
from openerp import SUPERUSER_ID as SU
from openerp.addons.web import http
from openerp.addons.web.http import request
from openerp.addons.website_sale.controllers.main import website_sale
from itertools import groupby
from werkzeug.exceptions import NotFound
from werkzeug.utils import redirect


class website_sale_digital(website_sale):

    downloads_page = '/shop/downloads'

    @http.route([
        '/shop/confirmation',
    ], type='http', auth="public", website=True)
    def display_attachments(self, **post):
        r = super(website_sale_digital, self).payment_confirmation(**post)
        return r

    @http.route([
        '/shop/attachment',
    ], auth='public')
    def download_attachment(self, attachment_id):
        from pprint import pprint; pprint(request.session)
        # Check if this is a valid attachment id
        attachment = request.env(user=SU)['ir.attachment'].search_read([('id', '=', int(attachment_id))], ["name", "datas", "file_type", "res_model", "res_id"])
        if attachment:
            attachment = attachment[0]
        else:
            redirect(self.downloads_page)

        # Check if the user has bought the associated product
        res_model = attachment['res_model']
        res_id = attachment['res_id']
        purchased_products = self._get_purchased_digital_products(request.uid)
        product_ids = map(lambda x: x['product_id'][0], purchased_products)

        if res_model == 'product.template':
            P = request.env['product.product']
            template_ids = map(lambda x: P.browse(x).product_tmpl_id.id, product_ids)
            if res_id not in template_ids:
                return redirect(self.downloads_page)

        elif res_model == 'product.product':
            if res_id not in product_ids:
                return redirect(self.downloads_page)

        else:
            return redirect(self.downloads_page)

        # The client has bought the product, otherwise it would have been blocked by now
        data = base64.standard_b64decode(attachment["datas"])
        headers = [
            ('Content-Type', attachment['file_type']),
            ('Content-Length', len(data)),
            ('Content-Disposition', 'attachment; filename="' + attachment['name'] + '"')
        ]
        return request.make_response(data, headers)

    @http.route([
        downloads_page,
    ], type='http', auth='public', website=True)
    def get_downloads(self):
        purchased_products = self._get_purchased_digital_products(request.uid)

        products_ids = []
        names = {}
        attachments = {}
        A = request.env['ir.attachment']
        P = request.env['product.product']
        for product in purchased_products:
            # Ignore duplicate products
            p_id = product['product_id'][0]
            if p_id in products_ids:
                continue

            # Search for product attachments
            p_name = product['product_id'][1]
            p_obj = P.browse(p_id)
            template = p_obj.product_tmpl_id
            att = A.search_read(
                domain = ['|', '&', ('res_model', '=', 'product.product'), ('res_id', '=', p_id), '&', ('res_model', '=', 'product.template'), ('res_id', '=', template.id)],
                fields = ['name'],
            )

            # Ignore products with no attachments
            if not att:
                continue

            # Store values for QWeb
            products_ids.append(p_id)
            attributes = p_obj.attribute_value_ids
            if attributes:
                names[p_id] = template.name + ' (' + ', '.join([a.name for a in attributes]) + ')'
            else:
                names[p_id] = template.name
            attachments[p_id] = att

        return request.website.render('website_sale_digital.downloads', {
            'products': products_ids,
            'names': names,
            'attachments': attachments,
        })

    def _get_purchased_digital_products(self, uid):
        user = request.env['res.users'].browse(uid)
        partner = user.partner_id
        sale_orders = request.env(user=SU)['sale.order.line']
        fields = ['product_id']

        purchases = sale_orders.search_read(
            domain = [('order_id.partner_id', '=', partner.id), ('state', '=', 'confirmed'), ('product_id.product_tmpl_id.digital_content','=', True)],
            fields = fields,
        )

        # Hack for public user last session
        last_purchase = sale_orders.search_read(
            domain = [('order_id', '=', request.session['sale_last_order_id'])],
            fields = fields,
        )

        return purchases + last_purchase