from openerp import models, fields, api, _
from openerp.exceptions import Warning,except_orm
import re

class crm_lead2opportunity_partner(models.TransientModel):
    _name = 'crm.lead2opportunity.partner'
    _description = 'Lead To Opportunity Partner'
    _inherit = 'crm.partner.binding'

    name = fields.Selection([
            ('convert', 'Convert to opportunity'),
            ('merge', 'Merge with existing opportunities')
        ], 'Conversion Action', required=True)
    opportunity_ids = fields.Many2many('crm.lead', string='Opportunities')
    user_id = fields.Many2one('res.users', 'Salesperson', select=True)
    team_id = fields.Many2one('crm.team', 'Sales Team', oldname='section_id', select=True)

    @api.onchange('action')
    def onchange_action(self):
        self.partner_id = False if self.action != 'exist' else self._find_matching_partner()

    @api.model
    def _get_duplicated_leads(self, partner_id, email, include_lost=False):
        """
        Search for opportunities that have the same partner and that arent done or cancelled
        """
        return self.env['crm.lead']._get_duplicated_leads_by_emails(partner_id, email, include_lost=include_lost)
        # return [rec.id for rec in data]

    @api.model
    def default_get(self, fields):
        """
        Default get for name, opportunity_ids.
        If there is an exisitng partner link to the lead, find all existing
        opportunities links with this partner to merge all information together
        """
        lead_obj = self.env['crm.lead']
        res = super(crm_lead2opportunity_partner, self).default_get(fields)

        if self._context.get('active_id'):
            tomerge = [int(self._context['active_id'])]
            partner_id = res.get('partner_id')
            lead = lead_obj.browse(self._context['active_id'])
            email = lead.partner_id and lead.partner_id.email or lead.email_from

            tomerge.extend([rec.id for rec in self._get_duplicated_leads(partner_id, email, include_lost=True)])
            tomerge = list(set(tomerge))

            if 'action' in fields:
                res['action']= partner_id and 'exist' or 'create'
            if 'partner_id' in fields:
                res['partner_id'] = partner_id
            if 'name' in fields:
                res['name'] = len(tomerge) >= 2 and 'merge' or 'convert'
            if 'opportunity_ids' in fields and len(tomerge) >= 2:
                res['opportunity_ids'] = tomerge
            if lead.user_id:
                res['user_id'] = lead.user_id.id
            if lead.team_id:
                res['team_id'] = lead.team_id.id

        return res

    @api.onchange('user_id')
    def on_change_user(self):
        """ When changing the user, also set a team_id or restrict team id
            to the ones user_id is member of. """
        team_id = self.team_id.id or False
        if self.user_id:
            if self.team_id:
                user_in_team = self.env['crm.team'].search([('id', '=', self.team_id.id), '|', ('user_id', '=', self.user_id.id), ('member_ids', '=', self.user_id.id)], count=True)
            else:
                user_in_team = False
            if not user_in_team:
                result = self.env['crm.lead'].on_change_user()
                team_id = result.get('value') and result['value'].get('team_id') and result['value']['team_id'] or False
        self.team_id = team_id

    @api.model
    def view_init(self, fields):
        """
        Check some preconditions before the wizard executes.
        """
        lead_obj = self.env['crm.lead']
        for lead in lead_obj.browse(self._context.get('active_ids', [])):
            if lead.probability == 100:
                raise except_orm(_('Warning!'),_("Closed/Dead leads cannot be converted into opportunities."))
        return False


    @api.multi
    def _convert_opportunity(self, vals):
        res = False
        lead_rec = vals.get('lead_ids', [])
        team_id = vals.get('team_id', False)
        
        for lead in lead_rec:
            partner_id = self._create_partner(lead)
            res = lead.convert_opportunity(partner_id, [], False)
        user_ids = vals.get('user_ids', False)
        
        if self._context.get('no_force_assignation'):
            leads_to_allocate = [lead.id for lead in lead_rec if not lead.user_id]
        
        else:
            leads_to_allocate = [lead.id for lead in lead_rec]
        
        if user_ids:
            lead_re = self.env['crm.lead'].browse(leads_to_allocate)
            lead_re.allocate_salesman(user_ids, team_id=team_id)
        
        return res

    @api.multi
    def action_apply(self):
        """
        Convert lead to opportunity or merge lead and opportunity and open
        the freshly created opportunity view.
        """
        if self.name == 'merge':
            lead = self.opportunity_ids.merge_opportunity()
            lead_rec = [lead]
            #TODO: merge_opportunity already return browsed record so no need to read
            # lead = lead_obj.browse(self._cr, self._uid, lead_id, ['type', 'user_id'], context=self._context)

            if lead.type == "lead":
                self = self.with_context(active_ids=[lead.id])
                self._convert_opportunity({'lead_ids': lead_rec, 'user_ids': [self.user_id.id], 'team_id': self.team_id.id})

            elif not self._context.get('no_force_assignation') or not lead.user_id:
                lead.write({'user_id': self.user_id.id, 'team_id': self.team_id.id})
        
        else:
            lead_ids = self._context.get('active_ids', [])
            lead_rec = self.env['crm.lead'].browse(lead_ids)
            self._convert_opportunity({'lead_ids': lead_rec, 
                'user_ids': [self.user_id.id], 'team_id': self.team_id.id})
        return lead_rec[0].redirect_opportunity_view()


    @api.multi
    def _create_partner(self, lead):
        """
        Create partner based on action.
        :return dict: dictionary organized as followed: {lead_id: partner_assigned_id}
        """
        #TODO this method in only called by crm_lead2opportunity_partner
        #wizard and would probably diserve to be refactored or at least
        #moved to a better place
        partner_id = lead.partner_id.id
        action=self.action
        if self.action == 'each_exist_or_create':
            self = self.with_context(active_id = lead.id)
            partner_id = self._find_matching_partner()
            action = 'create'

        res = lead.handle_partner_assignation(action, partner_id)
        return res.get(lead.id)


class crm_lead2opportunity_mass_convert(models.TransientModel):
    _name = 'crm.lead2opportunity.partner.mass'
    _description = 'Mass Lead To Opportunity Partner'
    _inherit = 'crm.lead2opportunity.partner'

    user_ids =  fields.Many2many('res.users', string='Salesmen', oldname='section_id')
    team_id = fields.Many2one('crm.team', 'Sales Team')
    deduplicate = fields.Boolean('Apply deduplication', help='Merge with existing leads/opportunities of each partner', default = True)
    action = fields.Selection([
            ('each_exist_or_create', 'Use existing partner or create'),
            ('nothing', 'Do not link to a customer')
        ], 'Related Customer', required=True)
    force_assignation = fields.Boolean('Force assignation', help='If unchecked, this will leave the salesman of duplicated opportunities')


    @api.model
    def default_get(self, fields):
        res = super(crm_lead2opportunity_mass_convert, self).default_get(fields)
        if 'partner_id' in fields:
            # avoid forcing the partner of the first lead as default
            res['partner_id'] = False
        if 'action' in fields:
            res['action'] = 'each_exist_or_create'
        if 'name' in fields:
            res['name'] = 'convert'
        if 'opportunity_ids' in fields:
            res['opportunity_ids'] = False
        return res

    @api.onchange('action')
    def on_change_action(self):
        vals = {}
        if self.action != 'exist':
            self.partner_id = False

    @api.onchange('deduplicate')
    def on_change_deduplicate(self):
        active_leads = self.env['crm.lead'].browse(self._context['active_ids'])
        partner_ids = [(lead.partner_id.id, lead.partner_id and lead.partner_id.email or lead.email_from) for lead in active_leads]
        partners_duplicated_leads = {}
        for partner_id, email in partner_ids:
            duplicated_leads = self._get_duplicated_leads(partner_id, email)
            # duplicated_leads = [rs.id for rs in record_set]
            if len(duplicated_leads) > 1:
                partners_duplicated_leads.setdefault((partner_id, email), []).extend(duplicated_leads)
        leads_with_duplicates = []
        for lead in active_leads:
            lead_tuple = (lead.partner_id.id, lead.partner_id.email if lead.partner_id else lead.email_from)
            if len(partners_duplicated_leads.get(lead_tuple, [])) > 1:
                leads_with_duplicates.append(lead.id)
        self.opportunity_ids = leads_with_duplicates

    @api.multi
    def _convert_opportunity(self, vals):
        """
        When "massively" (more than one at a time) converting leads to
        opportunities, check the salesteam_id and salesmen_ids and update
        the values before calling super.
        """
        salesteam_id = self.team_id and self.team_id.id or False
        salesmen_ids = []
        if self.user_ids:
            salesmen_ids = [x.id for x in self.user_ids]
        vals.update({'user_ids': salesmen_ids, 'team_id': salesteam_id})
        return super(crm_lead2opportunity_mass_convert, self)._convert_opportunity(vals)

    @api.multi
    def mass_convert(self):
        if self.name == 'convert' and self.deduplicate:
            merged_lead_ids = []
            remaining_lead_ids = []
            lead_selected = self._context.get('active_ids', [])
            for lead_id in lead_selected:
                if lead_id not in merged_lead_ids:
                    lead = self.env['crm.lead'].browse(lead_id)
                    duplicated_lead_rec = self._get_duplicated_leads(lead.partner_id.id, lead.partner_id and lead.partner_id.email or lead.email_from)
                    if len(duplicated_lead_rec) > 1:
                        # lead_data = self.pool['crm.lead'].browse(self._cr, self._uid, duplicated_lead_ids)
                        lead = duplicated_lead_rec.merge_opportunity()
                        merged_lead_ids.extend([rec.id for rec in duplicated_lead_rec])
                        remaining_lead_ids.append(lead.id)

            active_ids = set(self._context.get('active_ids', []))
            active_ids = active_ids.difference(merged_lead_ids)
            active_ids = active_ids.union(remaining_lead_ids)
            self = self.with_context(active_ids = list(active_ids))
        self = self.with_context(no_force_assignation = self._context.get('no_force_assignation', not self.force_assignation))
        return self.action_apply()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
