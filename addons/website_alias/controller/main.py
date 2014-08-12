# -*- coding: utf-8 -*-
import werkzeug

from openerp.addons.web import http
from openerp.http import request


class Website_Url(http.Controller):
    @http.route('/website_alias/new', type='json', auth='user', methods=['POST'])
    def create_shorten_url(self, **post):
        if 'url' not in post or post['url'] == '':
            return {'error': 'empty_url'}
        return request.env['website.alias'].create(post).read()

    @http.route('/r', type='http', auth='user', website=True)
    def shorten_url(self, **post):
        return request.website.render("website_alias.page_shorten_url", post)

    @http.route('/website_alias/add_code', type='json', auth='user')
    def add_code(self, **post):
        alias_id = request.env['website.alias.code'].search([('code', '=', post['init_code'])], limit=1).alias_id.id
        new_code = request.env['website.alias.code'].search_count([('code', '=', post['new_code']), ('alias_id', '=', alias_id)])
        if new_code > 0:
            return new_code.read()
        else:
            return request.env['website.alias.code'].create({'code': post['new_code'], 'alias_id': alias_id})[0].read()

    @http.route('/website_alias/recent_links', type='json', auth='user')
    def recent_links(self, **post):
        return request.env['website.alias'].recent_links(post['filter'], post['limit'])

    @http.route('/r/<string:code>+', type='http', auth="user", website=True)
    def statistics_shorten_url(self, code, **post):
        code = request.env['website.alias.code'].search([('code', '=', code)], limit=1)

        if code:
            return request.website.render("website_alias.graphs", code.alias_id.read()[0])
        else:
            return werkzeug.utils.redirect('', 301)

    @http.route('/r/<string:code>', type='http', auth='none', website=True)
    def full_url_redirect(self, code, **post):
        request.env['website.alias.click'].add_click(code, request.httprequest.remote_addr, request.session['geoip'].get('country_code'), stat_id=False)
        redirect_url = request.env['website.alias'].get_url_from_code(code)
        return werkzeug.utils.redirect(redirect_url or '', 301)
