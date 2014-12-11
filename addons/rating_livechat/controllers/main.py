# -*- coding: utf-8 -*-
import openerp

from openerp.addons.web import http
from openerp.http import request


class Rating(openerp.addons.rating.controllers.main.Rating):

    @http.route('/rating/livechat/feedback', type='json', auth='none')
    def rating_livechat_feedback(self, uuid, rate, reason=None, **kwargs):
        Session = request.env['im_chat.session']
        Rating = request.env['rating.rating']
        session_ids = Session.sudo().search([('uuid','=', uuid)])
        if session_ids:
            session = session_ids[0]
            # limit the creation : only ONE rating per session
            if len(session.rating_ids) <= 0:
                values = {
                    'res_id' : session.id,
                    'res_model' : 'im_chat.session',
                    'rating' : rate,
                }
                # find the partner related to the user of the conversation
                rated_partner_id = False
                if session.user_ids:
                    if session.user_ids[0]:
                        rated_partner_id = session.user_ids[0] and session.user_ids[0].partner_id.id or False
                values.update({'rated_partner_id' : rated_partner_id})
                if reason:
                    values.update({'feedback' : reason})
                # create the rating
                rating = Rating.sudo().create(values)
                return rating.id
        return False
