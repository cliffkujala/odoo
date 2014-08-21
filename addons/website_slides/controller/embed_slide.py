# -*- coding: utf-8 -*-
from openerp.http import request
from openerp.addons.web import http
from main import website_slides


class website_slide_embed(website_slides):
    @http.route('/slides/embed/count', type='http', methods=['POST'], auth='public', website=True)
    def slides_embed_count(self, slide, url):
        request.env['slide.embed'].sudo().add_embed_url(slide, url)

    @http.route('/slides/embed/<model("slide.slide"):slide>', type='http', auth='public', website=True)
    def slides_embed(self, slide, page="1"):
        values = slide.get_slide_detail()
        key = 'embed_slide'
        if not self._is_viewed_slide(slide, key) and not values.get('private'):
            slide.embed_views += 1
            slide_session = '%s_%s' % (key, request.session_id)
            request.session[slide_session].append(slide.id)
        values['page'] = page
        return request.website.render('website_slides.embed_slide', values)
