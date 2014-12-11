# -*- coding: utf-8 -*-

from openerp import models, fields, api


class im_livechat_session(models.Model):

    _name = 'im_chat.session'
    _inherit = ['im_chat.session', 'rating.mixin']


class im_livechat_channel(models.Model):

    _inherit = 'im_livechat.channel'

    @api.multi
    def _compute_percentage_satisfaction(self):
        for record in self:
            repartition = record.session_ids.rating_get_grades()
            total = sum(repartition.values())
            happy = repartition['great']
            record.rating_percentage_satisfaction = ((happy*100) / total) if happy > 0 else 0

    rating_percentage_satisfaction = fields.Integer(compute='_compute_percentage_satisfaction', string='% Happy')

    @api.multi
    def action_view_rating(self):
        action = self.env['ir.actions.act_window'].for_xml_id('rating', 'action_view_rating')
        action['domain'] = [('res_id', 'in', self.session_ids.ids), ('res_model', '=', 'im_chat.session')]
        return action
