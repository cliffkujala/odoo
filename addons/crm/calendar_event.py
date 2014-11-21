from openerp import models, api, fields, _
import logging
_logger = logging.getLogger(__name__)


class calendar_event(models.Model):
    """ Model for Calendar Event """
    _inherit = 'calendar.event'

    phonecall_id = fields.Many2one('crm.phonecall', 'Phonecall')
    opportunity_id = fields.Many2one('crm.lead', 'Opportunity', domain="[('type', '=', 'opportunity')]")

    @api.model
    def create(self, vals):
        res = super(calendar_event, self).create(vals)
        if res.opportunity_id:
            res.opportunity_id.log_meeting(res.name, res.start, res.duration)
        return res
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: