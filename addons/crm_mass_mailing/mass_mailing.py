# -*- coding: utf-8 -*-
from openerp import models, fields, api, _, SUPERUSER_ID


class MassMailingCampaign(models.Model):
    _name = 'mail.mass_mailing.campaign'
    _inherit = ['mail.mass_mailing.campaign', 'crm.tracking.mixin']

    _inherits = {'crm.tracking.campaign': 'campaign_id'}
    campaign_id = fields.Many2one('crm.tracking.campaign', required=True, ondelete='cascade')

    def _get_source_id(self):
        return self.env.ref('crm.crm_source_newsletter')

    def _get_medium_id(self):
        return self.env.ref('crm.crm_medium_email')

    source_id = fields.Many2one(default=_get_source_id)
    medium_id = fields.Many2one(default=_get_medium_id)

    @api.one
    @api.onchange('name')
    def _onchange_name(self):
        self.campaign_id.write({'name': self.name})

    # Rewrite the _auto_init method to avoid SQL constraint error
    # because of the migration of the required campaign_id field.
    def _auto_init(self, cr, context=None):
        self = self.browse(cr, SUPERUSER_ID, [], context)

        self._columns['campaign_id'].required = False
        super(MassMailingCampaign, self)._auto_init()

        for campaign in self.search([('campaign_id', '=', False)]):
            campaign.campaign_id = self.env['crm.tracking.campaign'].create({'name': campaign.name}).id

        self.env.cr.execute('ALTER TABLE %s ALTER COLUMN campaign_id SET NOT NULL' % self._table)
        self._columns['campaign_id'].required = True


class MassMailing(models.Model):
    _name = 'mail.mass_mailing'
    _inherit = ['mail.mass_mailing', 'crm.tracking.mixin']

    @api.onchange('mass_mailing_campaign_id')
    def _onchange_mass_mailing_campaign_id(self):
        if self.mass_mailing_campaign_id:
            self.campaign_id = self.mass_mailing_campaign_id.campaign_id
            self.source_id = self.mass_mailing_campaign_id.source_id
            self.medium_id = self.mass_mailing_campaign_id.medium_id
