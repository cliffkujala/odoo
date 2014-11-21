from openerp import models, api, fields, _
import time

class crm_phonecall2phonecall(models.TransientModel):
    _name = 'crm.phonecall2phonecall'
    _description = 'Phonecall To Phonecall'

    name = fields.Char('Call summary', required=True, select=1)
    user_id = fields.Many2one('res.users',"Assign To")
    contact_name = fields.Char('Contact')
    phone = fields.Char('Phone')
    categ_id = fields.Many2one('crm.phonecall.category', 'Category')
    date = fields.Datetime('Date')
    team_id = fields.Many2one('crm.team','Sales Team')
    action = fields.Selection([('schedule','Schedule a call'), ('log','Log a call')], 'Action', required=True)
    partner_id = fields.Many2one('res.partner', "Partner")
    note = fields.Text('Note')

    @api.model
    def action_cancel(self):
        """
        Closes Phonecall to Phonecall form
        """
        return {'type':'ir.actions.act_window_close'}

    @api.multi
    def action_schedule(self):
        phonecall = self.env['crm.phonecall'].browse(self._context.get('active_ids',[]))
        for this in self:
            phonecall_ids = phonecall.schedule_another_phonecall(
                                this.date, this.name,
                                this.user_id and this.user_id.id or False,
                                this.team_id and this.team_id.id or False,
                                this.categ_id and this.categ_id.id or False, 
                                action=this.action)
        return phonecall.redirect_phonecall_view(phonecall_ids[phonecall[0].id])
    
    @api.model
    def default_get(self, fields):
        """
        This function gets default values
        """
        res = super(crm_phonecall2phonecall, self).default_get(fields)
        record_id = self._context.get('active_id', False)
        res.update({'action': 'schedule', 'date': time.strftime('%Y-%m-%d %H:%M:%S')})
        if record_id:
            phonecall = self.env['crm.phonecall'].browse(record_id)
            categ_id = False
            data_obj = self.env['ir.model.data']
            try:
                res_id = data_obj._get_id('crm', 'categ_phone2')
                categ_id = data_obj.browse(res_id).res_id
            except ValueError:
                pass

            if 'name' in fields:
                res['name'] = phonecall.name
            if 'user_id' in fields:
                res['user_id'] = phonecall.user_id and phonecall.user_id.id or False
            if 'date' in fields:
                res['date'] = False
            if 'team_id' in fields:
                res['team_id'] = phonecall.team_id and phonecall.team_id.id or False
            if 'categ_id' in fields:
                res['categ_id'] = categ_id
            if 'partner_id' in fields:
                res['partner_id'] = phonecall.partner_id and phonecall.partner_id.id or False
        return res
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: