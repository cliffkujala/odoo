# -*- coding: utf-8 -*-

from openerp import models, fields, api, exceptions
import time
from datetime import datetime
from dateutil.relativedelta import relativedelta
# is this necessary? yes, if activity condition contains regular
# expression, i suppose
import re
import pdb
_intervalTypes = {
    'hours': lambda interval: relativedelta(hours=interval),
    'days': lambda interval: relativedelta(days=interval),
    'months': lambda interval: relativedelta(months=interval),
    'years': lambda interval: relativedelta(years=interval),
}

DT_FMT = '%Y-%m-%d %H:%M:%S'


class lead_automation_campaign(models.Model):
    _name = "lead.automation.campaign"

    name = fields.Char('Name', required=True)
    object_id = fields.Many2one('ir.model', 'Resource', required=True,
                                help="Choose the resource on which you want this campaign to be run")
    partner_field_id = fields.Many2one('ir.model.fields', 'Partner Field',
                                       domain="[('model_id', '=', object_id), ('ttype', '=', 'many2one'), ('relation', '=', 'res.partner')]",
                                       help="The generated workitems will be linked to the partner related to the record. "
                                       "If the record is the partner itself leave this field empty. "
                                       "This is useful for reporting purposes, via the Campaign Analysis or Campaign Follow-up views.")
    unique_field_id = fields.Many2one('ir.model.fields', 'Unique Field',
                                      domain="[('model_id', '=', object_id), ('ttype', 'in', ['char','int','many2one','text','selection'])]",
                                      help='If set, this field will help segments that work in "no duplicates" mode to avoid '
                                      'selecting similar records twice. Similar records are records that have the same value for '
                                      'this unique field. For example by choosing the "email_from" field for CRM Leads you would prevent '
                                      'sending the same campaign to the same email address again. If not set, the "no duplicates" segments '
                                      "will only avoid selecting the same record again if it entered the campaign previously. "
                                      "Only easily comparable fields like textfields, integers, selections or single relationships may be used.")
    mode = fields.Selection([('test', 'Test Directly'),
                             ('test_realtime', 'Test in Realtime'),
                             ('manual', 'With Manual Confirmation'),
                             ('active', 'Normal')], default='test',
                            string='Mode', required=True, help="""Test - It creates and process all the activities directly (without waiting for the delay on transitions) but does not send emails or produce reports.
																																	Test in Realtime - It creates and processes all the activities directly but does not send emails or produce reports.
																																	With Manual Confirmation - the campaigns runs normally, but the user has to validate all workitem manually.
																																	Normal - the campaign runs normally and automatically sends all emails and reports (be very careful with this mode, you're live!)""")
    state = fields.Selection([('draft', 'New'),
                              ('running', 'Running'),
                              ('cancelled', 'Cancelled'),
                              ('done', 'Done')],
                             'Status', copy=False, default='draft')
    activity_ids = fields.One2many(
        'lead.automation.activity', 'campaign_id', 'Activities')
    fixed_cost = fields.Float(
        'Fixed Cost', help="Fixed cost for running this campaign. You may also specify variable cost and revenue on each campaign activity. Cost and Revenue statistics are included in Campaign Reporting.")
    segment_ids = fields.One2many(
        'lead.automation.segment', 'campaign_id', 'Segments', readonly=False)
    segments_count = fields.Integer(
        compute='_count_segments', string='Segments')

    @api.one
    def _get_partner_for(self, record):
        partner_field = self.partner_field_id.name
        if partner_field:
            return self.partner_field_id
        elif self.object_id.model == 'res.partner':
            return record
        return None

    @api.one
    def _count_segments(self):
        self.segments_count = len(self.segment_ids)

    @api.one
    def action_draft(self):
        self.state = 'draft'

    @api.one
    def action_run(self):
        if not self.activity_ids:
            raise exceptions.ValidationError(
                "A Campaign without any Activity cannot be set to Run.")

        has_start = False
        has_signal_without_from = False
        for activity in self.activity_ids:
            if activity.start:
                has_start = True
            if activity.signal and len(activity.from_ids) == 0:
                has_signal_without_from = True

        if not has_start and not has_signal_without_from:
            raise exceptions.ValidationError(
                "The campaign cannot be started. It does not have any starting activity. Modify campaign's activities to mark one as the starting point.")

        self.state = 'running'

    @api.one
    def action_done(self):
        has_active_segment = False
        for segment in self.segment_ids:
            if segment.state == 'running':
                has_active_segment = True

        if has_active_segment:

            raise exceptions.ValidationError(
                'The campaign cannot be marked as done before all segments are closed.')
        self.state = 'done'

    @api.one
    def action_cancel(self):
        self.state = 'cancelled'

    # prevent duplication until the server properly duplicates several levels
    # of nested o2m
    @api.one
    def copy(self, default=None):
        raise exceptions.ValidationError(
            "You cannot duplicate a campaign, Not supported yet.")


class lead_automation_segment(models.Model):
    _name = "lead.automation.segment"

    name = fields.Char('Name', required=True)
    campaign_id = fields.Many2one(
        'lead.automation.campaign', 'Campaign', required=True, select=1, ondelete="cascade")
    object_id = fields.Many2one(
        related='campaign_id.object_id', string='Resource', store=True)
    ir_filter_id = fields.Many2one('ir.filters', 'Filter', ondelete="restrict",
                                   help="Filter to select the matching resource records that belong to this segment. "
                                   "New filters can be created and saved using the advanced search on the list view of the Resource. "
                                   "If no filter is set, all records are selected without filtering. "
                                   "The synchronization mode may also add a criterion to the filter.")
    sync_last_date = fields.Datetime(
        'Last Synchronization', help="Date on which this segment was synchronized last time (automatically or manually)"),
    sync_mode = fields.Selection([('create_date', 'Only records created after last sync'),
                                  ('write_date',
                                   'Only records modified after last sync (no duplicates)'),
                                  ('all', 'All records (no duplicates)')],
                                 string='Synchronization mode',
                                 default='create_date',
                                 help="Determines an additional criterion to add to the filter when selecting new records to inject in the campaign. "
                                 '"No duplicates" prevents selecting records which have already entered the campaign previously.'
                                 'If the campaign has a "unique field" set, "no duplicates" will also prevent selecting records which have '
                                 'the same value for the unique field as other records that already entered the campaign.')
    state = fields.Selection([('draft', 'New'),
                              ('cancelled', 'Cancelled'),
                              ('running', 'Running'),
                              ('done', 'Done')],
                             string='Status', default="draft", copy=False)
    date_run = fields.Datetime(
        'Launch Date', help="Initial start date of this segment.")
    date_done = fields.Datetime(
        'End Date', help="Date this segment was last closed or cancelled.")
    date_next_sync = fields.Datetime(
        compute='_get_next_sync', string='Next Synchronization')
    sync_last_date = fields.Datetime(
        'Last Synchronization', help="Date on which this segment was synchronized last time (automatically or manually)")

    def _get_next_sync(self):
        segment_cron = self.env['ir.cron'].search(
            [('model', '=', 'lead.automation.segment')])
        self.date_next_sync = fields.Datetime.from_string(
            segment_cron.nextcall)

    @api.constrains('ir_filter_id', 'campaign_id')
    @api.one
    def check_object_model(self):
        if self.ir_filter_id:
            if self.object_id.model != self.ir_filter_id.model_id:
                raise exceptions.ValidationError(
                    "Model of filter must be same as resource model of Campaign.")

    @api.one
    def action_draft(self):
        self.state = 'draft'

    @api.one
    def action_run(self):
        if not(self.date_run):
            self.date_run = time.strftime('%Y-%m-%d %H:%M:%S')
        self.state = 'running'

    @api.one
    def action_done(self):
        # TODO: cancel all workitems related to that segment
        self.state = 'done'

    @api.one
    def action_cancel(self):
        # TODO: cancel all workitems related to that segment
        self.state = 'cancelled'

    @api.one
    def synchronize(self):
        self.process_segment()
        return True

    # def process_segment(self):

    @api.one
    def process_segment(self):
        Workitems = self.env['lead.automation.workitem']
        Campaigns = self.env['lead.automation.campaign']
        if self.state != 'running' and self.campaign_id.state != 'running':
            return False

        action_date = time.strftime(DT_FMT)

        activities = self.env['lead.automation.activity'].search(
            [('start', '=', True), ('campaign_id', '=', self.campaign_id.id)])

        model_obj = self.object_id.model
        criteria = []
        if self.sync_last_date and self.sync_mode != 'all':
            criteria += [(self.sync_mode, '>', self.sync_last_date)]
        if self.ir_filter_id:
            criteria += eval(self.ir_filter_id.domain)
        objects = self.env[model_obj].search(criteria)
        # XXX TODO: rewrite this loop more efficiently without doing 1 search
        # per record!
        for record in objects:
            # avoid duplicate workitem for the same resource
            # if segment.sync_mode in ('write_date','all'):
            #	if Campaigns._find_duplicate_workitems(cr, uid, record, segment.campaign_id, context=context):
            #		continue

            wi_vals = {
                'segment_id': self.id,
                'date': action_date,
                'state': 'todo',
                'res_id': record.id
            }
        #	partner = self.env.pool.get('lead.automation.campaign')._get_partner_for(segment.campaign_id, record)
        #	if partner:
        #		wi_vals['partner_id'] = partner.id

            for act_id in activities:
                wi_vals['activity_id'] = act_id.id
                Workitems.create(wi_vals)

        self.sync_last_date = action_date
        workitems = self.env['lead.automation.workitem'].search([('segment_id','=',self.id)])
        workitems.process()
        return True


class lead_automation_activity(models.Model):
    _name = 'lead.automation.activity'
    _action_types = [
        ('email', 'Email'),
        ('report', 'Report'),
        ('action', 'Custom Action'),
        # TODO implement the subcampaigns.
        # TODO implement the subcampaign out. disallow out transitions from
        # subcampaign activities ?
        #('subcampaign', 'Sub-Campaign'),
    ]
    name = fields.Char('Name', required=True)
    campaign_id = fields.Many2one('lead.automation.campaign', 'Campaign',
                                  required=True, ondelete='cascade', select=1)
    object_id = fields.Many2one(
        related='campaign_id.object_id', string='Object', readonly=True)
    start = fields.Boolean(
        'Start', help="This activity is launched when the campaign starts.", select=True)
    condition = fields.Text('Condition', size=256, required=True, default="True",
                            help="Python expression to decide whether the activity can be executed, otherwise it will be deleted or cancelled."
                            "The expression may use the following [browsable] variables:\n"
                            "   - activity: the campaign activity\n"
                            "   - workitem: the campaign workitem\n"
                            "   - resource: the resource object this campaign item represents\n"
                            "   - transitions: list of campaign transitions outgoing from this activity\n"
                            "...- re: Python regular expression module")
    type = fields.Selection(_action_types, 'Type', required=True, default="email",
                            help="""The type of action to execute when an item enters this activity, such as:
   - Email: send an email using a predefined email template
   - Report: print an existing Report defined on the resource item and save it into a specific directory
   - Custom Action: execute a predefined action, e.g. to modify the fields of the resource record
  """)
    email_template_id = fields.Many2one(
        'email.template', "Email Template", help='The email to send when this activity is activated')
    report_id = fields.Many2one('ir.actions.report.xml', "Report",
                                help='The report to generate when this activity is activated', )
    report_directory_id = fields.Many2one('document.directory', 'Directory',
                                          help="This folder is used to store the generated reports")
    server_action_id = fields.Many2one('ir.actions.server', string='Action',
                                       help="The action to perform when this activity is activated")
    to_ids = fields.One2many('lead.automation.transition',
                             'activity_from_id',
                             'Next Activities')
    from_ids = fields.One2many('lead.automation.transition',
                               'activity_to_id',
                               'Previous Activities')
    # variable_cost: fields.float('Variable Cost', help="Set a variable cost if you consider that every campaign item that has reached this point has entailed a certain cost. You can get cost statistics in the Reporting section", digits_compute=dp.get_precision('Product Price'))
    # revenue: fields.float('Revenue', help="Set an expected revenue if you
    # consider that every campaign item that has reached this point has
    # generated a certain revenue. You can get revenue statistics in the
    # Reporting section", digits_compute=dp.get_precision('Account'))
    signal = fields.Char('Signal',
                         help='An activity with a signal can be called programmatically. Be careful, the workitem is always created when a signal is sent')
    keep_if_condition_not_met = fields.Boolean(
        "Don't Delete Workitems", help="By activating this option, workitems that aren't executed because the condition is not met are marked as cancelled instead of being deleted.")

    @api.one
    def process(self, workitem):
        #method = '_process_wi_%s' % (self.type)
        #action = getattr(self, method, None)
        # if not action:
        #	raise ValidationError('Method %r is not implemented on %r object.' % (method, self))

        #workitem = self.env['lead.automation.workitem'].browse(cr, uid, wi_id, context=context)
        # return action(cr, uid, activity, workitem, context=context)
        return True


class lead_automation_transition(models.Model):
    _name = 'lead.automation.transition'

    _interval_units = [
        ('hours', 'Hour(s)'),
        ('days', 'Day(s)'),
        ('months', 'Month(s)'),
        ('years', 'Year(s)'),
    ]

    name = fields.Char(compute='_get_name', string='Name', size=128)
    activity_from_id = fields.Many2one(
        'lead.automation.activity', 'Previous Activity', select=1, required=True, ondelete="cascade")
    activity_to_id = fields.Many2one(
        'lead.automation.activity', 'Next Activity', required=True, ondelete="cascade")
    interval_nbr = fields.Integer('Interval Value', required=True, default=1)
    interval_type = fields.Selection(
        _interval_units, 'Interval Unit', required=True, default="days")

    trigger = fields.Selection([('auto', 'Automatic'),
                                ('time', 'Time'),
                                # fake plastic transition
                                ('cosmetic', 'Cosmetic'),
                                ],
                               'Trigger', required=True, default='time',
                               help="How is the destination workitem triggered")

    @api.one
    def _get_name(self):
        # name formatters that depend on trigger
        formatters = {
            'auto': _('Automatic transition'),
            'time': _('After %(self.interval_nbr)d %(self.interval_type)s'),
            'cosmetic': _('Cosmetic'),
        }
        self.name = formatters[self.trigger]

    @api.one
    def _delta(self):
        if self.trigger != 'time':
            raise ValidationError(
                'Delta is only relevant for timed transition.')
        return relativedelta(**{str(self.interval_type): self.interval_nbr})


class lead_automation_workitem(models.Model):
    _name = "lead.automation.workitem"

    segment_id = fields.Many2one(
        'lead.automation.segment', 'Segment', readonly=False)
    activity_id = fields.Many2one(
        'lead.automation.activity', 'Activity', required=True, readonly=False)
    campaign_id = fields.Many2one(
        related='activity_id.campaign_id', string='Campaign', readonly=False, store=True)
    object_id = fields.Many2one(
        related='activity_id.campaign_id.object_id', string='Resource', select=1, readonly=False, store=True)
    res_id = fields.Integer('Resource ID', select=1, readonly=False)
    res_name = fields.Char(
        compute='_res_name_get', string='Resource Name', search='_resource_search', size=64)
    date = fields.Datetime('Execution Date', default=False,
                           help='If date is not set, this workitem has to be run manually', readonly=False)
    partner_id = fields.Many2one(
        'res.partner', 'Partner', select=1, readonly=True)
    state = fields.Selection([('todo', 'To Do'),
                              ('cancelled', 'Cancelled'),
                              ('exception', 'Exception'),
                              ('done', 'Done'),
                              ], 'Status', default='todo', readonly=True, copy=False)
    error_msg = fields.Text('Error Message', readonly=True)

    @api.one
    def _res_name_get(self):
        self.res_name = self.env[self.object_id.model].browse(self.res_id).name

    @api.one
    def _resource_search(self):
        self.res_name = self.res_id.model

    @api.one
    def action_draft(self):
        if self.state in ['exception', 'cancelled']:
            self.state = 'todo'

    @api.one
    def action_cancel(self):
        if self.state in ['exception', 'todo']:
            self.state = cancelled

    @api.one
    def process(self):
        if self.state != 'todo':
            return False

        activity = self.activity_id
        object_id = self.env[self.object_id.model].browse(self.res_id)

        eval_context = {
            'activity': activity,
            'workitem': self,
            'object': object_id,
            'resource': object_id,
            'transitions': activity.to_ids,
            're': re,
        }
        try:
            condition = activity.condition
            campaign_mode = self.campaign_id.mode
            if condition:
                if not eval(condition, eval_context):
                    if activity.keep_if_condition_not_met:
                        self.state = 'cancelled'
                    else:
                        self.unlink()
                    return
            result = True
            if campaign_mode in ('manual', 'active'):
                result = activity.process(self)

            values = dict(state='done')
            if not self.date:
                values['date'] = datetime.now().strftime(DT_FMT)
            self.write(values)

            if result:
                # process _chain
                self.refresh()       # reload
                date = datetime.strptime(self.date, DT_FMT)

                for transition in activity.to_ids:
                    if transition.trigger == 'cosmetic':
                        continue
                    launch_date = False
                    if transition.trigger == 'auto':
                        launch_date = date
                    elif transition.trigger == 'time':
                        temp = transition._delta()
                        launch_date = date + temp[0]

                    if launch_date:
                        launch_date = launch_date.strftime(DT_FMT)
                    values = {
                        'date': launch_date,
                        'segment_id': self.segment_id.id,
                        'activity_id': transition.activity_to_id.id,
                        'partner_id': self.partner_id.id,
                        'res_id': self.res_id,
                        'state': 'todo',
                    }
                    wi_id = self.create(values)

                    # Now, depending on the trigger and the campaign mode
                    # we know whether we must run the newly created workitem.
                    #
                    # rows = transition trigger \ colums = campaign mode
                    #
                    #           test    test_realtime     manual      normal (active)
                    # time       Y            N             N           N
                    # cosmetic   N            N             N           N
                    # auto       Y            Y             N           Y
                    #

                    run = (transition.trigger == 'auto' and campaign_mode != 'manual') \
                        or (transition.trigger == 'time' and campaign_mode == 'test')
                    if run:
                        wi_id.process()

        except Exception:
            self.state = 'exception'
            self.error_msg = Exception.message


class email_template(models.Model):
    _inherit = "email.template"
    _defaults = {
        'model_id': lambda obj, cr, uid, context: context.get('object_id', False),
    }
