# -*- coding: utf-8 -*-
import datetime
import io
import json
import re
import urllib2
from PIL import Image
from urlparse import urlparse

from openerp import api, fields, models, _
from openerp.tools import mail, image
from openerp.exceptions import Warning
from openerp.http import request
from openerp.addons.website.models.website import slug


class Channel(models.Model):
    """ Channel contain slides. channel has group based access configuration for it's
        slides like which group can upload slide in channel or access channel it self.
        can promote specific slide in channel.
    """
    _name = 'slide.channel'
    _inherit = ['mail.thread', 'website.seo.metadata']
    _order = 'sequence, id'
    _description = 'Define public or private access for presentations in channels'

    name = fields.Char("Channel Name", translate=True, required=True)

    website_published = fields.Boolean('Published', help="Published on the website", copy=False)
    description = fields.Text(translate=True)
    slide_ids = fields.One2many('slide.slide', 'channel_id', string="Slides")
    category_ids = fields.One2many('slide.category', 'channel_id', string="Categories")

    promote_strategy = fields.Selection([
        ('none', 'No Featured Presentation'),
        ('latest', 'Newest'), ('popular', 'Most Upvoted'),
        ('mostview', 'Most Viewed'), ('custom', 'Select Manually')],
        string="Featured Presentation", default='none', required=True)

    nbr_presentations = fields.Integer('Number of Presentations', compute='_count_presentations', store=True)
    nbr_documents = fields.Integer('Number of Documents', compute='_count_presentations', store=True)
    nbr_videos = fields.Integer('Number of Videos', compute='_count_presentations', store=True)
    nbr_infographics = fields.Integer('Number of Infographics', compute='_count_presentations', store=True)
    total = fields.Integer(compute='_count_presentations', store=True)

    sequence = fields.Integer()
    access_error_msg = fields.Html(
        'Error Message', help="Display message (html) when channel's content"
        "is not accessible for a user due to access rights")
    template_id = fields.Many2one(
        'email.template', 'Email Template',
        html="Email template use to send new presentation upload notification through email")
    visibility = fields.Selection([
        ('public', 'Public'), ('private', 'Hide Channel'),
        ('partial', 'Show channel but presentations based on groups')], default='public')
    group_ids = fields.Many2many(
        'res.groups', 'rel_channel_groups', 'channel_id', 'group_id',
        string='Channel Groups', help="Groups allowed to access this channel.")
    upload_group_ids = fields.Many2many(
        'res.groups', 'rel_upload_groups', 'channel_id', 'group_id',
        string='Upload Groups', help="Groups allowed to upload presentations.")

    @api.multi
    @api.depends('slide_ids.slide_type', 'slide_ids.website_published')
    def _count_presentations(self):
        Slide = self.env['slide.slide']
        for record in self:
            domain = [('website_published', '=', True), ('channel_id', '=', record.id)]
            groups = Slide.read_group(domain, ['slide_type'], groupby=['slide_type'], lazy=False)
            countvals = {group.get('slide_type'): group.get('__count', 0) for group in groups}
            record.nbr_presentations = countvals.get('presentation', 0)
            record.nbr_documents = countvals.get('document', 0)
            record.nbr_videos = countvals.get('video', 0)
            record.nbr_infographics = countvals.get('infographic', 0)
            record.total = countvals.get('presentation', 0) + countvals.get('document', 0) + countvals.get('video', 0) + countvals.get('infographic', 0)

    def get_promoted_slide(self):
        '''Return promoted slide based on the promote type'''

        Slide = self.env['slide.slide']
        domain = [('website_published', '=', True), ('channel_id', '=', self.id)]

        strategy = {
            'custom': False,
            'none': None,
            'mostview': 'total_views desc',
            'popular': 'likes desc',
            'latest': 'date_publish desc',
        }
        order_by = strategy.get(self.promote_strategy)
        if order_by is None:
            return False
        if order_by:
            return Slide.search(domain, limit=1, offset=0, order=order_by)
        return self.promoted_slide_id or False

    @api.onchange('visibility')
    def change_visibility(self):
        if self.visibility == 'public':
            self.group_ids = False


class Category(models.Model):
    """ Channel contain various categories to manage it's slides by category """

    _name = 'slide.category'
    _description = "Category of slides"
    _order = "sequence, id"

    channel_id = fields.Many2one('slide.channel', string="Channel", required=True)
    name = fields.Char("Category", translate=True, required=True)
    sequence = fields.Integer(default=10)
    slide_ids = fields.One2many('slide.slide', 'category_id', string="Slides")

    nbr_presentations = fields.Integer("Number of Presentations", compute='_count_presentations', store=True)
    nbr_documents = fields.Integer("Number of Documents", compute='_count_presentations', store=True)
    nbr_videos = fields.Integer("Number of Videos", compute='_count_presentations', store=True)
    nbr_infographics = fields.Integer("Number of Infographics", compute='_count_presentations', store=True)
    total = fields.Integer(compute='_count_presentations', store=True)

    @api.multi
    @api.depends('slide_ids.slide_type', 'slide_ids.website_published')
    def _count_presentations(self):
        Slide = self.env['slide.slide']
        for record in self:
            Slide = record.env['slide.slide']
            domain = [('website_published', '=', True), ('category_id', '=', record.id)]
            groups = Slide.read_group(domain, ['slide_type'], groupby=['slide_type'], lazy=False)
            countvals = {group.get('slide_type'): group.get('__count', 0) for group in groups}

            record.nbr_presentations = countvals.get('presentation', 0)
            record.nbr_documents = countvals.get('document', 0)
            record.nbr_videos = countvals.get('video', 0)
            record.nbr_infographics = countvals.get('infographic', 0)
            record.total = countvals.get('presentation', 0) + countvals.get('document', 0) + countvals.get('video', 0) + countvals.get('infographic', 0)


class EmbededView(models.Model):
    _name = 'slide.embed'
    """ Slide can embed with third party website
        This model use for track view count in website. generate statistics by website
    """

    slide_id = fields.Many2one('slide.slide', string="Presentation")
    url = fields.Char(help="Embed website url.")
    count_views = fields.Integer('# Views on Embed')

    def add_embed_url(self, slide_id, url):
        schema = urlparse(url)
        baseurl = schema.netloc

        domain = [('url', '=', baseurl), ('slide_id', '=', int(slide_id))]
        count = self.search(domain, limit=1)
        if count:
            count.count_views += 1
        else:
            vals = {
                'slide_id': slide_id,
                'url': baseurl,
                'count_views': 1
            }
            self.create(vals)


class SlideTag(models.Model):
    """ Tag use for search slides by tag in various channel """

    _name = 'slide.tag'

    name = fields.Char()


class Slide(models.Model):
    """ This model represent actual presentation
        Slide must have one of four type depend on it's content.
            Presentation (pdf presentations)
            Document (pdf books or documents)
            Infographic (images)
            Video (youtube or google drive videos)

        Slide has various statistics like view count, embed count, like, dislikes
    """

    _name = 'slide.slide'
    _inherit = ['mail.thread', 'website.seo.metadata']
    _description = 'Slides'
    _slides_per_list = 20
    _PROMOTIONAL_FIELDS = ['__last_update', 'name', 'image_thumb', 'slide_type', 'total_views', 'category_id',
       'channel_id', 'description', 'website_published', 'tag_ids', 'write_date', 'create_date']

    name = fields.Char('Title', required=True)
    description = fields.Text(translate=True)
    index_content = fields.Text('Transcript')

    datas = fields.Binary('Content')
    url = fields.Char('Document URL', help="Youtube or Google Document URL")

    date_publish = fields.Datetime('Publish Date')
    downloadable = fields.Selection([
        ('not_downloadable', 'No One'), ('with_login', 'Authentified User Only'),
        ('without_login', 'Everyone')], string='Can Download')

    channel_id = fields.Many2one('slide.channel', string="Channel", required=True)
    category_id = fields.Many2one('slide.category', string="Category")
    tag_ids = fields.Many2many('slide.tag', 'rel_slide_tag', 'slide_id', 'tag_id', string='Tags')
    embedcount_ids = fields.One2many('slide.embed', 'slide_id', string="Embed Count")

    slide_type = fields.Selection([
        ('infographic', 'Infographic'), ('presentation', 'Presentation'),
        ('document', 'Document'), ('video', 'Video')],
        string='Type', help="Document type will be set automatically depending on"
        "the height and width, however you can change it manually.")

    image = fields.Binary()
    image_medium = fields.Binary('Medium', compute="_get_image", store=True)
    image_thumb = fields.Binary('Thumbnail', compute="_get_image", store=True)

    document_id = fields.Char('Document Id', help="youtube or google drive document id")
    mime_type = fields.Char('Mime-type')

    website_published = fields.Boolean('Published', help="Published on the website", copy=False)
    website_message_ids = fields.One2many(
        'mail.message', 'res_id',
        domain=lambda self: [('model', '=', self._name), ('type', '=', 'comment')],
        string='Website Messages', help="Website communication history")

    likes = fields.Integer()
    dislikes = fields.Integer()

    slide_views = fields.Integer('Number of Views')
    embed_views = fields.Integer('Number of Views on Embed')
    youtube_views = fields.Integer('Number of Views on Youtube')
    total_views = fields.Integer("Total", compute='_compute_total', store=True)
    share_url = fields.Char('Share URL', compute='_get_share_url')

    @api.multi
    @api.depends('slide_views', 'embed_views', 'youtube_views')
    def _compute_total(self):
        for record in self:
            record.total_views = record.slide_views + record.embed_views + record.youtube_views

    @api.multi
    @api.depends('image')
    def _get_image(self):
        for record in self:
            if record.image:
                record.image_medium = image.crop_image(record.image, thumbnail_ratio=3)
                record.image_thumb = image.crop_image(record.image, thumbnail_ratio=4)

    @api.multi
    def _get_share_url(self):
        base_url = self.env['ir.config_parameter'].get_param('web.base.url')
        for record in self:
            record.share_url = "%s/slides/detail_view/%s" % (base_url, slug(record))

    def get_related_slides(self, limit=20):
        domain = [('website_published', '=', True), ('channel_id.visibility', '!=', 'private'),
        ('id', '!=', self.id), ('category_id', '=', self.category_id.id)]
        return self.search(domain, limit=limit)

    def get_most_viewed_slides(self, limit=20):
        domain = [('id', '!=', self.id), ('channel_id.visibility', '!=', 'private'),('website_published', '=', True)]
        return self.search(domain, limit=limit, offset=0, order='total_views desc')

    @api.model
    def check_unique_slide(self, channel_id, file_name=False, document=False):
        """ Check video/doc already available or not
            :param values: dic with document_id or file name
            :returns: url link if document is google doc or youtube else boolean based on file name
        """
        domain = [('channel_id', '=', channel_id)]
        if document:
            domain += [('document_id', '=', document)]
            slide = self.search(domain, limit=1)
            if slide:
                return "/slides/detail_view/%s" % (slide.id)
        if file_name:
            domain += [('name', '=', file_name)]
            if self.search(domain, limit=1):
                return True
        return False

    @api.multi
    def get_slide_detail(self):
        most_viewed_slides = self.get_most_viewed_slides(self._slides_per_list)
        related_slides = self.get_related_slides(self._slides_per_list)
        user = request.env.user
        values = {
            'most_viewed_slides': most_viewed_slides,
            'related_slides': related_slides,
        }
        if self.channel_id.visibility == 'partial' and not self.channel_id.group_ids & user.groups_id:
            values.update({
                'private': True,
                'private_slide': self,
            })
            return values
        values.update({
            'channel': self.channel_id,
            'user': user,
            'is_public_user': user == request.website.user_id,
            'slide': self,
            'comments': self.website_message_ids,
        })
        return values

    def get_embed_code(self):
        base_url = self.env['ir.config_parameter'].get_param('web.base.url')
        embedcode = ""
        if self.datas and not self.document_id:
            embedcode = '<iframe  src="%s/slides/embed/%s?page=1" allowFullScreen="true" height="%s" width="%s" frameborder="0"></iframe>' % (base_url, self.id, 315, 420)
        if self.slide_type == 'video' and self.document_id:
            if not self.mime_type:
                # embed youtube video
                embedcode = '<iframe src="//www.youtube.com/embed/%s?theme=light" frameborder="0"></iframe>' % (self.document_id)
            else:
                # embed google doc video
                embedcode = '<embed src="https://video.google.com/get_player?ps=docs&partnerid=30&docid=%s" type="application/x-shockwave-flash"></embed>' % (self.document_id)
        return embedcode

    def get_mail_body(self, message=False):
        base_url = self.env['ir.config_parameter'].get_param('web.base.url')
        template = self.env['email.template']
        image_url = "%s/website/image/slide.slide/%s/image" % (base_url, self.id)

        msg_context = {
            'message': message or _('%s has shared a %s with you !') % (self.env.user.name, self.slide_type),
            'image_url': image_url,
            'base_url': base_url
        }
        msg_context.update(self._context)
        message_body = template.with_context(msg_context).render_template(self.channel_id.template_id.body_html, 'slide.slide', self.id)
        return message_body

    def send_share_email(self, email):
        result = False
        body = self.get_mail_body()
        subject = _('%s has shared a %s with you !') % (self.env.user.name, self.slide_type)

        if self.env.user.email:
            result = mail.email_send(email_from=self.env.user.email, email_to=[email], subject=subject, body=body, reply_to=self.env.user.email, subtype="html")

        return result

    def notify_published(self):
        if not self.website_published:
            return False

        if self.channel_id:
            base_url = self.pool['ir.config_parameter'].get_param(self._cr, self._uid, 'web.base.url')
            body = _(
                '<p>A new presentation <i>%s</i> has been published under %s channel. <a href="%s/slides/detail_view/%s">Click here to access the presentation.</a></p>' %
                (self.name, self.channel_id.name, base_url, slug(self))
            )
            self.channel_id.message_post(subject=self.name, body=body, subtype='website_slides.new_slides')

    # As per channel access configuration (visibility)
    #   public  ==> no restriction on slides access
    #   private ==> restrict all slides of channel base on access group define on channel group_ids field
    #   partial ==> Show channel, but presentations based on groups means any user can see channel but not slide's content.
    #
    #   for private : implement using record rule
    #
    #   for partial: user can see channel, but channel gridview have slide detail so we have to implement
    #   partial field access mechanism for public user so he can have access
    #   of promotional field (name, view_count) of slides, but not all fields like data (actual pdf content)
    #   all fields should be accessible only for user group define on channel group_ids
    #
    @api.model
    def check_field_access_rights(self, operation, fields):
        fields = super(Slide, self).check_field_access_rights(operation, fields)
        if self.ids:
            # still read not perform so we can not access self.channel_id
            self.env.cr.execute('SELECT DISTINCT channel_id FROM ' + self._table + ' WHERE id IN %s', (tuple(self.ids),))
            channel_ids = [x[0] for x in self.env.cr.fetchall()]
            channels = self.env['slide.channel'].sudo().browse(channel_ids)
            promotional_field_only = False
            for channel in channels:
                if channel.visibility == 'partial' and not(channel.group_ids & self.env.user.groups_id):
                    promotional_field_only = True

            if promotional_field_only:
                fields = filter(lambda field: field in self._PROMOTIONAL_FIELDS, fields)
        return fields

    def notify_request_to_approve(self):
        if self.website_published:
            return False

        if self.channel_id:
            message = _("A new %s has been uploaded and waiting for publish on %s channel.") % (self.slide_type, self.channel_id.name)

            base_url = self.pool['ir.config_parameter'].get_param(self._cr, self._uid, 'web.base.url')

            body = _(
                '<p>A new presentation <i>%s</i> has been uploaded under %s channel andwaiting for your review. <a href="%s/slides/detail_view/%s">Click here to review the presentation.</a></p>' %
                (self.name, self.channel_id.name, base_url, slug(self))
            )

            self.channel_id.message_post(subject=message, body=body, subtype='website_slides.new_slides_validation')

    @api.multi
    def write(self, values):
        if values.get('website_published'):
            values['date_publish'] = datetime.datetime.now()

        success = super(Slide, self).write(values)

        if values.get('website_published'):
            self.notify_published()

        return success

    def _parse_url(self, url):
        expr = re.compile(r'^.*((youtu.be/)|(v/)|(\/u\/\w\/)|(embed\/)|(watch\?))\??v?=?([^#\&\?]*).*')
        arg = expr.match(url)
        document_id = arg and arg.group(7) or False
        if document_id:
            return ('youtube', document_id)

        expr = re.compile(r'((^https://docs.google.com)|(^https://drive.google.com))(.*\/d\/)(.*)(.*\/)')
        arg = expr.match(url)
        document_id = arg and arg.group(5) or False
        if document_id:
            return ('google_doc', document_id)

        return (document_id, False)

    @api.one
    @api.onchange('url')
    def on_change_url(self):
        url = self.url
        if url:
            document, id = self._parse_url(url)
            if not document:
                raise Warning(_('Please enter valid youtube or google doc url'))

            vals = self.get_resource_detail({document: id})
            if not vals:
                raise Warning(_('Could not fetch data from url. Document or access right not available'))

            self.name = vals['name']
            self.image = vals['image']
            self.slide_type = vals['slide_type']
            self.document_id = id
            self.mime_type = vals.get('mime_type') or False
            self.index_content = vals.get('index_content') or ''
            self.datas = vals.get('datas') or ''
            self.description = vals.get('description') or ''

            self.youtube_views = vals.get('youtube_views') or 0
            self.likes = vals.get('likes') or 0
            self.dislikes = vals.get('dislikes') or 0

    @api.model
    def create(self, values):
        if not values.get('index_content'):
            values['index_content'] = values.get('description')

        if values.get('slide_type') == 'infographic':
            values['image'] = values['datas']

        if values.get('website_published'):
            values['date_publish'] = datetime.datetime.now()

        slide_id = super(Slide, self).create(values)

        # notify channel manager to approve uploaded slide
        slide_id.notify_request_to_approve()

        # notify all users who subscribed to channel
        slide_id.notify_published()
        return slide_id

    def prepare_create_values(self, post):
        """ prepare create values from post of the client """

        channel_id = post['channel_id']
        category = post['category_id']
        values = {}

        # Create category
        if category and category.get('create'):
            Category = request.env['slide.category']
            post['category_id'] = Category.create({
                'name': category['text'],
                'channel_id': channel_id
            }).id
        else:
            post['category_id'] = category and category['id'] or False

        document, id = self._parse_url(post['url'])
        if document:
            values = self.get_resource_detail({document: id})
            values['document_id'] = id
        values.update(post)

        # Do not publish slide if user has not publisher rights
        if not self.user_has_groups('base.group_website_publisher'):
            values['website_published'] = False

        return values

    def get_resource_detail(self, document, only_preview_fields=False, part='snippet,statistics', fields='id,snippet,statistics'):
        vals = False
        key = 'AIzaSyBKDzf7KjjZqwPWAME6JOeHzzBlq9nrpjk'
        if document.get('google_doc'):
            request_url = "https://www.googleapis.com/drive/v2/files/%s?projection=BASIC&key=%s" % (document['google_doc'], key)
            values = self._get_external_data(request_url, type="json")
            if values:
                vals = self.parse_google_document(values, only_preview_fields)
            return vals

        if document.get('youtube'):
            apiurl = 'https://www.googleapis.com/youtube/v3/videos'
            request_url = "%s?id=%s&key=%s&part=%s&fields=items(%s)" % (apiurl, document['youtube'], key, part, fields)
            values = self._get_external_data(request_url, type="json")
            if values:
                vals = self.parse_youtube_statistics(values, only_preview_fields)
            return vals

    def _get_external_data(self, resource_url, type=False):
        values = False
        try:
            req = urllib2.Request(resource_url)
            content = urllib2.urlopen(req).read()
            if type == 'json':
                values = json.loads(content)
            elif type in ('image', 'pdf'):
                values = content.encode('base64')
            else:
                values = content
        except urllib2.HTTPError:
            pass
        return values

    def parse_google_document(self, values, only_preview_fields):
        def get_slide_type(vals):
            image = Image.open(io.BytesIO(vals['image'].decode('base64')))
            width, height = image.size
            if height > width:
                return 'document'
            else:
                return 'presentation'

        vals = {}
        if values:
            if only_preview_fields:
                vals.update({
                    'url_src': values['thumbnailLink'],
                    'title': values['title'],
                })
                return vals
            image_url = values['thumbnailLink'].replace('=s220', '')
            vals.update({
                'name': values['title'],
                'mime_type': values['mimeType'],
                'image': self._get_external_data(image_url, type='image')
            })

            if values['mimeType'].startswith('video/'):
                vals['slide_type'] = 'video'

            if values['mimeType'].startswith('image/'):
                vals['datas'] = vals['image']
                vals['slide_type'] = 'infographic'

            if values['mimeType'].startswith('application/vnd.google-apps'):
                vals['datas'] = self._get_external_data(values['exportLinks']['application/pdf'], type='pdf')

                vals['slide_type'] = get_slide_type(vals)

                if values.get('exportLinks').get('text/plain'):
                    vals['index_content'] = self._get_external_data(values['exportLinks']['text/plain'])
                if values.get('exportLinks').get('text/csv'):
                    vals['index_content'] = self._get_external_data(values['exportLinks']['text/csv'])

            if values['mimeType'] == 'application/pdf':
                # TODO: Google drive pdf docuement don't provide plain text (transcript).
                vals['datas'] = self._get_external_data(values['webContentLink'], type='pdf')
                vals['slide_type'] = get_slide_type(vals)

        return vals

    def parse_youtube_statistics(self, values, only_preview_fields):
        vals = {}
        if values:
            item = values['items'][0]

            if item.get('snippet'):
                if only_preview_fields:
                    vals.update({
                        'url_src': item['snippet']['thumbnails']['high']['url'],
                        'title': values['items'][0]['snippet']['title'],
                        'description': values['items'][0]['snippet']['description']
                    })
                    return vals

                vals.update({
                    'name': values['items'][0]['snippet']['title'],
                    'image': self._get_external_data(item['snippet']['thumbnails']['high']['url'], type='image'),
                    'slide_type': 'video',
                    'description': values['items'][0]['snippet']['description'],
                })

            if item.get('statistics'):
                vals.update({
                    'youtube_views': int(item['statistics']['viewCount']),
                    'likes': int(item['statistics']['likeCount']),
                    'dislikes': int(item['statistics']['dislikeCount'])
                })

        return vals


class Channel(models.Model):
    _inherit = 'slide.channel'

    promoted_slide_id = fields.Many2one('slide.slide', string='Promoted Slide')
