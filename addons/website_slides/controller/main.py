# -*- coding: utf-8 -*-
import base64
import logging

import werkzeug

from openerp.http import request
from openerp.addons.web import http
from openerp.tools.translate import _

_logger = logging.getLogger(__name__)


class website_slides(http.Controller):

    _slides_per_page = 12

    def _is_viewed_slide(self, slide, key):
        slide_session = '%s_%s' % (key, request.session_id)
        request.session[slide_session] = request.session.get(slide_session, [])
        if slide.id not in request.session[slide_session]:
            return False
        return True

    @http.route('/slides', type='http', auth="public", website=True)
    def index(self, *args, **post):
        """ Returns a list of available channels: if only one is available,
            redirects directly to its slides
        """
        Channel = request.env['slide.channel']
        user = request.env.user
        channels = Channel.search([], order='sequence, id')

        if not channels:
            return request.website.render("website_slides.channel_not_found")

        if len(channels) == 1:
            return request.redirect("/slides/%s" % channels.id)

        vals = {
            'channels': channels,
            'user': user,
            'is_public_user': user == request.website.user_id
        }
        return request.website.render('website_slides.channels', vals)

    @http.route(['/slides/<model("slide.channel"):channel>',
                '/slides/<model("slide.channel"):channel>/page/<int:page>',

                '/slides/<model("slide.channel"):channel>/<slide_type>',
                '/slides/<model("slide.channel"):channel>/<slide_type>/page/<int:page>',

                '/slides/<model("slide.channel"):channel>/tag/<model("slide.tag"):tag>',
                '/slides/<model("slide.channel"):channel>/tag/<model("slide.tag"):tag>/page/<int:page>',

                '/slides/<model("slide.channel"):channel>/category/<model("slide.category"):category>',
                '/slides/<model("slide.channel"):channel>/category/<model("slide.category"):category>/page/<int:page>',

                '/slides/<model("slide.channel"):channel>/category/<model("slide.category"):category>/<slide_type>',
                '/slides/<model("slide.channel"):channel>/category/<model("slide.category"):category>/<slide_type>/page/<int:page>',
                ], type='http', auth="public", website=True)
    def slides(self, channel, category=None, page=1, slide_type='', tag='', sorting='creation', *args, **kw):
        user = request.env.user
        Slide = request.env['slide.slide']
        domain = [('channel_id', '=', channel.id)]

        url = "/slides/%s" % (channel.id)
        if category:
            domain += [('category_id', '=', category.id)]
            url = "/slides/%s/category/%s" % (channel.id, category.id)

        if slide_type:
            domain += [('slide_type', '=', slide_type)]
            url = "/slides/%s/%s" % (channel.id, slide_type)

        if tag:
            domain += [('tag_ids.id', '=', tag.id)]
            url = "/slides/%s/tag/%s" % (channel.id, tag.name)

        if category and slide_type:
            url = "/slides/%s/category/%s/%s" % (channel.id, category.id, slide_type)

        if sorting == 'date':
            order = 'date_publish desc'
        elif sorting == 'view':
            order = 'total_views desc'
        elif sorting == 'vote':
            order = 'likes desc'
        else:
            sorting = 'date'
            order = 'date_publish desc'

        access_group = channel.group_ids
        upload_group = channel.upload_group_ids
        user_group = user.groups_id

        channel_access = True
        if channel.visibility in ('private', 'partial'):
            channel_access = access_group & user_group and True or False

        # if no upload group define then anyone can upload who has channel access right
        upload_access = len(upload_group & user_group) if upload_group else True

        pager_count = Slide.search_count(domain)
        pager = request.website.pager(url=url, total=pager_count, page=page,
                                      step=self._slides_per_page, scope=self._slides_per_page,
                                      url_args={'sorting': sorting})

        slides = Slide.search(domain, limit=self._slides_per_page, offset=pager['offset'], order=order)
        famous = channel.get_promoted_slide()
        values = {
            'channel': channel,
            'slides': slides,
            'tag': tag,
            'user': user,
            'all_count': pager_count,
            'pager': pager,
            'slide_type': slide_type,
            'sorting': sorting,
            'category': category,
            'famous': famous,
            'is_public_user': user == request.website.user_id,
            'can_upload': channel_access and upload_access
        }

        # Display uncategorized slides
        if not slide_type and not category:
            category_datas = []
            for category in Slide.read_group(domain, ['category_id'], ['category_id']):
                category_id, name = category.get('category_id') or (False, _('Uncategorized'))
                category_datas.append({
                    'id': category_id,
                    'name': name,
                    'total': category['category_id_count'],
                    'slides': Slide.search(category['__domain'], limit=4, offset=0, order=order)
                })
            values.update({
                'category_datas': category_datas,
            })
        return request.website.render('website_slides.home', values)

    @http.route('/slides/detail_view/<model("slide.slide"):slide>', type='http', auth="public", website=True)
    def slide_detail_view(self, slide):
        values = slide.get_slide_detail()
        key = 'slide'
        if not self._is_viewed_slide(slide, key) and not values.get('private'):
            slide.slide_views += 1
            slide_session = '%s_%s' % (key, request.session_id)
            request.session[slide_session].append(slide.id)
        return request.website.render('website_slides.slide_detail_view', values)

    @http.route('/slides/pdf_content/<model("slide.slide"):slide>', type='http', auth="public", website=True)
    def slide_view_content(self, slide):
        response = werkzeug.wrappers.Response()
        response.data = slide.datas.decode('base64')
        response.mimetype = 'application/pdf'
        return response

    @http.route('/slides/comment/<model("slide.slide"):slide>', type='http', auth="public", methods=['POST'], website=True)
    def slides_comment(self, slide, **post):
        Partner = request.env['res.partner']
        partner_ids = False

        # TODO: make website_published False by default and write an method to send email with random back link,
        # which will post all comments posted with that email address
        website_published = False

        if post.get('comment'):
            if request.uid != request.website.user_id.id:
                partner_ids = [request.env.user.partner_id]
                website_published = True
            else:
                partner_ids = Partner.sudo().search([('email', '=', post.get('email'))])
                if not partner_ids or not partner_ids[0]:
                    partner_ids = [Partner.sudo().create({
                        'name': post.get('name'),
                        'email': post.get('email')
                    })]

            if partner_ids:
                slide.sudo().with_context(mail_create_nosubcribe=True).message_post(
                    body=post.get('comment'),
                    type='comment',
                    subtype='mt_comment',
                    author_id=partner_ids[0].id,
                    website_published=website_published
                )

        return werkzeug.utils.redirect(request.httprequest.referrer + "#discuss")

    @http.route('/slides/like/<model("slide.slide"):slide>', type='json', auth="public", website=True)
    def slide_like(self, slide, **post):
        slide.likes += 1
        return slide.likes

    @http.route('/slides/dislike/<model("slide.slide"):slide>', type='json', auth="public", website=True)
    def slide_dislike(self, slide, **post):
        slide.dislikes += 1
        return slide.dislikes

    @http.route(['/slides/send_share_email/<model("slide.slide"):slide>'], type='json', auth='user', methods=['POST'], website=True)
    def send_share_email(self, slide, email):
        result = slide.send_share_email(email)
        return result

    @http.route(['/slides/dialog_preview'], type='json', auth='user', methods=['POST'], website=True)
    def dialog_preview(self, **data):
        Slide = request.env['slide.slide']
        document, id = Slide._parse_url(data['url'])
        preview = {}
        if not document:
            preview['error'] = _('Please enter valid youtube or google doc url')
            return preview
        avalilable = Slide.check_unique_slide(data['channel_id'], False, id)
        if avalilable:
            preview['error'] = _('This video already exists in this channel <a target="_blank" href="%s">click here to view it </a>' % avalilable)
            return preview
        values = Slide.get_resource_detail({document: id}, only_preview_fields=True)
        if not values:
            preview['error'] = _('Could not fetch data from url. Document or access right not available')
            return preview
        return values

    @http.route(['/slides/add_slide'], type='json', auth='user', methods=['POST'], website=True)
    def create_slide(self, *args, **post):
        Slide = request.env['slide.slide']
        payload = request.httprequest.content_length
        # payload is total request content size so it's not exact size of file.
        # already add client validation this is for double check if client alter.
        if (payload / 1024 / 1024 > 17):
            return {'error': _('File is too big.')}

        if Slide.search([('name', '=', post['name']), ('channel_id', '=', post['channel_id'])]):
            return {
                'error': _('This title already exists in the channel, rename and try again.')
            }
        # handle exception during creation of slide and sent error notification to the client
        # otherwise client slide create dialog box continue processing even server fail to create a slide.
        try:
            values = Slide.prepare_create_values(post)
            slide_id = Slide.create(values)
        except Exception as e:
            _logger.error(e)
            return {'error': _('Internal server error, please try again later or contact administrator.')}
        return {'url': "/slides/detail_view/%s" % (slide_id.id)}

    @http.route('/slides/overlay/<model("slide.slide"):slide>', type='json', auth="public", website=True)
    def get_next_slides(self, slide):
        slides_to_suggest = 9
        suggested_slides = slide.get_related_slides(slides_to_suggest)
        if len(suggested_slides) < slides_to_suggest:
            slides_to_suggest = slides_to_suggest - len(suggested_slides)
            suggested_slides += slide.get_most_viewed_slides(slides_to_suggest)

        vals = []
        for suggest in suggested_slides:
            val = {
                'img_src': '/website/image/slide.slide/%s/image_thumb' % (suggest.id),
                'caption': suggest.name,
                'url': suggest.share_url
            }
            vals.append(val)

        return vals

    @http.route('/slides/download/<model("slide.slide"):slide>', type='http', auth="public", website=True)
    def download_slide(self, slide):
        if slide.downloadable == 'not_downloadable':
            return request.website.render("website.403")
        if not request.session.uid and slide.downloadable == 'with_login':
            login_redirect = '/web?redirect=/slides/detail_view/%s' % (slide.id)
            return werkzeug.utils.redirect(login_redirect)
        filecontent = base64.b64decode(slide.datas)
        # TODO not sure convert filename to utf-8 and quote, check with IE if it required
        disposition = 'attachment; filename=%s.pdf' % slide.name
        return request.make_response(filecontent,
                [('Content-Type', 'application/pdf'),
                 ('Content-Disposition', disposition)])

    @http.route(['/slides/<model("slide.channel"):channel>/search',
                '/slides/<model("slide.channel"):channel>/search/page/<int:page>'
                ], type='http', auth="public", website=True)
    def search(self, channel=0, query=False, page=1, order=False):
        Slide = request.env['slide.slide']

        domain = [('channel_id', '=', channel.id)]

        if request.env.user == request.website.user_id:
            domain += [('website_published', '=', True)]

        if query:
            domain += ['|', '|', ('name', 'ilike', query), ('description', 'ilike', query), ('index_content', 'ilike', query)]

        url = "/slides/%s/search" % (channel.id)
        url_args = {}
        if query:
            url_args['query'] = query

        pager_count = Slide.search_count(domain)
        pager = request.website.pager(url=url, total=pager_count, page=page,
                                      step=self._slides_per_page, scope=self._slides_per_page,
                                      url_args=url_args)

        slides = Slide.search(domain, limit=self._slides_per_page, offset=pager['offset'], order=order)

        values = {
            'channel': channel,
            'pager': pager,
            'slides': slides,
            'query': query,
            'order': order
        }
        return request.website.render('website_slides.search_result', values)

    @http.route('/slides/promote/<model("slide.slide"):slide>', type='http', auth='public', website=True)
    def set_promoted_slide(self, slide):
        slide.channel_id.promoted_slide_id = slide.id
        return request.redirect("/slides/%s" % slide.channel_id.id)
