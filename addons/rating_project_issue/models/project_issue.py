# -*- coding: utf-8 -*-
from openerp import api, fields, models


class ProjectIssue(models.Model):

    _name = "project.issue"
    _inherit = ['project.issue', 'rating.mixin']

    @api.multi
    def write(self, values):
        if 'stage_id' in values and values.get('stage_id', False):
            template = self.env['project.task.type'].browse(values.get('stage_id')).rating_template_id
            if template:
                rated_partner_id = self.user_id.partner_id
                partner_id = self.partner_id
                if partner_id and rated_partner_id:
                    self.rating_send_request(template, partner_id, rated_partner_id)
        return super(ProjectIssue, self).write(values)


class Project(models.Model):

    _inherit = "project.project"

    @api.multi
    @api.depends('percentage_satisfaction_task', 'percentage_satisfaction_issue')
    def _compute_percentage_satisfaction_project(self):
        super(Project, self)._compute_percentage_satisfaction_project()
        Rating = self.env['rating.rating']
        for record in self:
            # get the number of rated tasks and issues with a read_group (more perfomant !)
            domain = [('rating', '>=', 0), '|',
                '&', ('res_model', '=', 'project.task'), ('res_id', 'in', record.tasks.ids),
                '&', ('res_model', '=', 'project.issue'), ('res_id', 'in', record.issue_ids.ids)]
            data = Rating.read_group(domain, ['res_model'], ['res_model'])
            # compute the number of each model and total number
            res = dict.fromkeys(['project.task', 'project.issue'], 0)
            for d in data:
                res[d['res_model']] += d['res_model_count']
            nbr_rated_task = res['project.task']
            nbr_rated_issue = res['project.issue']
            nbr_project_rating = nbr_rated_issue + nbr_rated_task
            # compute the weighted arithmetic average
            ratio_task = float(nbr_rated_task) / float(nbr_project_rating) if nbr_project_rating else 0
            ratio_issue = float(nbr_rated_issue) / float(nbr_project_rating) if nbr_project_rating else 0
            record.percentage_satisfaction_project = round((ratio_task*record.percentage_satisfaction_task)+(ratio_issue*record.percentage_satisfaction_issue)) if nbr_project_rating else -1


    @api.one
    def _compute_percentage_satisfaction_issue(self):
        project_issue = self.env['project.issue'].search([('project_id', '=', self.id)])
        activity = project_issue.rating_get_grades()
        self.percentage_satisfaction_issue = activity['great'] * 100 / sum(activity.values()) if sum(activity.values()) else 0

    @api.one
    @api.depends('use_tasks', 'use_issues')
    def _display_happy_customer(self):
        self.is_visible_happy_customer = self.use_tasks if self.use_tasks else self.use_issues


    percentage_satisfaction_issue = fields.Integer(
        compute='_compute_percentage_satisfaction_issue', string='% Happy')


    @api.multi
    def action_view_issue_rating(self):
        """ return the action to see all the rating about the issues of the project """
        action = self.env['ir.actions.act_window'].for_xml_id('rating', 'action_view_rating')
        issues = self.env['project.issue'].search([('project_id', 'in', self.ids)])
        return dict(action, domain=[('res_id', 'in', issues.ids), ('res_model', '=', 'project.issue')])

    @api.multi
    def action_view_all_rating(self):
        action = super(Project, self).action_view_all_rating()
        domain = action['domain']
        if not self.use_tasks: # remove task domain, if neeed
            domain = []
        if self.use_issues: # add issue domain if needed
            issues = self.env['project.issue'].search([('project_id', 'in', self.ids)])
            domain = ['|'] + domain + ['&', ('res_id', 'in', issues.ids), ('res_model', '=', 'project.issue')]
        return dict(action, domain=domain)

