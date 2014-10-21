# -*- coding: utf-8 -*-

from datetime import datetime
from urllib import urlencode

import hashlib

from openerp import SUPERUSER_ID
from openerp.osv import osv, fields


class Users(osv.Model):
    _inherit = 'res.users'

    def __init__(self, pool, cr):
        init_res = super(Users, self).__init__(pool, cr)
        self.SELF_WRITEABLE_FIELDS = list(
            set(
                self.SELF_WRITEABLE_FIELDS +
                ['country_id', 'city', 'website', 'website_description', 'website_published']))
        return init_res

    def _get_user_badge_level(self, cr, uid, ids, name, args, context=None):
        """Return total badge per level of users"""
        result = dict.fromkeys(ids, False)
        badge_user_obj = self.pool['gamification.badge.user']
        for id in ids:
            result[id] = {
                'gold_badge': badge_user_obj.search(cr, uid, [('badge_id.level', '=', 'gold'), ('user_id', '=', id)], context=context, count=True),
                'silver_badge': badge_user_obj.search(cr, uid, [('badge_id.level', '=', 'silver'), ('user_id', '=', id)], context=context, count=True),
                'bronze_badge': badge_user_obj.search(cr, uid, [('badge_id.level', '=', 'bronze'), ('user_id', '=', id)], context=context, count=True),
            }
        return result

    _columns = {
        'create_date': fields.datetime('Create Date', select=True, readonly=True),
        'karma': fields.integer('Karma'),
        'badge_ids': fields.one2many('gamification.badge.user', 'user_id', 'Badges'),
        'gold_badge': fields.function(_get_user_badge_level, string="Number of gold badges", type='integer', multi='badge_level'),
        'silver_badge': fields.function(_get_user_badge_level, string="Number of silver badges", type='integer', multi='badge_level'),
        'bronze_badge': fields.function(_get_user_badge_level, string="Number of bronze badges", type='integer', multi='badge_level'),
    }

    _defaults = {
        'karma': 0,
    }

    def _generate_forum_token(self, cr, uid, user_id, email):
        """Return a token for email validation. This token is valid for the day
        and is a hash based on a (secret) uuid generated by the forum module,
        the user_id, the email and currently the day (to be updated if necessary). """
        forum_uuid = self.pool.get('ir.config_parameter').get_param(cr, SUPERUSER_ID, 'website_forum.uuid')
        return hashlib.sha256('%s-%s-%s-%s' % (
            datetime.now().replace(hour=0, minute=0, second=0, microsecond=0),
            forum_uuid,
            user_id,
            email)).hexdigest()

    def send_forum_validation_email(self, cr, uid, user_id, forum_id=None, context=None):
        user = self.pool['res.users'].browse(cr, uid, user_id, context=context)
        token = self._generate_forum_token(cr, uid, user_id, user.email)
        activation_template_id = self.pool['ir.model.data'].xmlid_to_res_id(cr, uid, 'website_forum.validation_email')
        if activation_template_id:
            params = {
                'token': token,
                'id': user_id,
                'email': user.email}
            if forum_id:
                params['forum_id'] = forum_id
            base_url = self.pool['ir.config_parameter'].get_param(cr, uid, 'web.base.url')
            token_url = base_url + '/forum/validate_email?%s' % urlencode(params)
            tpl_ctx = dict(context, token_url=token_url)
            self.pool['email.template'].send_mail(cr, SUPERUSER_ID, activation_template_id, user_id, force_send=True, context=tpl_ctx)
        return True

    def process_forum_validation_token(self, cr, uid, token, user_id, email, forum_id=None, context=None):
        validation_token = self.pool['res.users']._generate_forum_token(cr, uid, user_id, email)
        user = self.pool['res.users'].browse(cr, SUPERUSER_ID, user_id, context=context)
        if token == validation_token and user.karma == 0:
            karma = 3
            if not forum_id:
                forum_ids = self.pool['forum.forum'].search(cr, uid, [], limit=1, context=context)
                if forum_ids:
                    forum_id = forum_ids[0]
            if forum_id:
                forum = self.pool['forum.forum'].browse(cr, uid, forum_id, context=context)
                # karma gained: karma to ask a question and have 2 downvotes
                karma = forum.karma_ask + (-2 * forum.karma_gen_question_downvote)
            return user.write({'karma': karma})
        return False

    def add_karma(self, cr, uid, ids, karma, context=None):
        for user in self.browse(cr, uid, ids, context=context):
            self.write(cr, uid, [user.id], {'karma': user.karma + karma}, context=context)
        return True

    def get_serialised_gamification_summary(self, cr, uid, excluded_categories=None, context=None):
        if isinstance(excluded_categories, list):
            if 'forum' not in excluded_categories:
                excluded_categories.append('forum')
        else:
            excluded_categories = ['forum']
        return super(Users, self).get_serialised_gamification_summary(cr, uid, excluded_categories=excluded_categories, context=context)

    # Wrapper for call_kw with inherits
    def open_website_url(self, cr, uid, id, context=None):
        return self.browse(cr, uid, id, context=context).partner_id.open_website_url()[0]
