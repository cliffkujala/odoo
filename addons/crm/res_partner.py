from openerp import models, api, fields, _

class res_partner(models.Model):
    """ Inherits partner and adds CRM information in the partner form """
    _inherit = 'res.partner'

    @api.multi
    @api.depends('opportunity_ids', 'meeting_ids', 'phonecall_ids')
    def _opportunity_meeting_phonecall_count(self):
        # the user may not have access rights for opportunities or meetings
        try:
            for partner in self:
                partner.opportunity_count = len(partner.opportunity_ids)
                partner.meeting_count = len(partner.meeting_ids)
        except:
            pass
        for partner in self:
            print"**in last for : ",len(partner.phonecall_ids)
            partner.phonecall_count = len(partner.phonecall_ids)

    team_id = fields.Many2one('crm.team', 'Sales Team', oldname='section_id')
    opportunity_ids = fields.One2many('crm.lead', 'partner_id', 'Opportunities', domain=[('type', '=', 'opportunity')])
    meeting_ids = fields.Many2many('calendar.event', 'calendar_event_res_partner_rel','res_partner_id', 'calendar_event_id', 'Meetings', store=True)
    phonecall_ids = fields.One2many('crm.phonecall', 'partner_id', string='Phonecalls', store=True)
    opportunity_count = fields.Integer(compute='_opportunity_meeting_phonecall_count', string="Opportunity")
    meeting_count = fields.Integer(compute='_opportunity_meeting_phonecall_count', string="# Meetings")
    phonecall_count = fields.Integer(compute='_opportunity_meeting_phonecall_count', string="Phonecalls")

    @api.model
    def redirect_partner_form(self, partner_id):
        search_view = self.env['ir.model.data'].get_object_reference('base', 'view_res_partner_filter')
        value = {
            'domain': "[]",
            'view_type': 'form',
            'view_mode': 'form,tree',
            'res_model': 'res.partner',
            'res_id': int(partner_id),
            'view_id': False,
            'context': self._context,
            'type': 'ir.actions.act_window',
            'search_view_id': search_view and search_view[1] or False
        }
        return value

    @api.multi
    def make_opportunity(self, opportunity_summary, planned_revenue=0.0, probability=0.0, partner_id=None):
        tag_ids = self.env['crm.lead.tag'].search([])
        opportunity_ids = {}
        for partner in self:
            if not partner_id:
                partner_id = partner.id
            opportunity_id = partner.opportunity_ids.create({
                'name' : opportunity_summary,
                'planned_revenue' : planned_revenue,
                'probability' : probability,
                'partner_id' : partner_id,
                'tag_ids' : tag_ids and tag_ids[0].id or [],
                'type': 'opportunity'
            })
            opportunity_ids[partner_id] = opportunity_id.id
        return opportunity_ids


    @api.multi
    def schedule_meeting(self):
        partner_ids = self.ids
        partner_ids.append(self.env['res.users'].browse(self._uid).partner_id.id)
        res = self.env['ir.actions.act_window'].for_xml_id('calendar', 'action_calendar_event')
        res['context'] = {
            'search_default_partner_ids': self.ids,
            'default_partner_ids': partner_ids,
        }
        return res