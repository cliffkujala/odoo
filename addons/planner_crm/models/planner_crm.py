# -*- coding: utf-8 -*-

from openerp import api, models


class PlannerCrm(models.Model):
    _inherit = 'planner.planner'

    @api.model
    def _get_planner_application(self):
        planner = super(PlannerCrm, self)._get_planner_application()
        planner.append(['planner_crm', 'CRM Planner'])
        return planner

    @api.model
    def _prepare_planner_crm_data(self):
        alias_domain = self.env.ref(
            'sales_team.team_sales_department').alias_domain
        company_data = self.env['res.users'].browse(self._uid).company_id
        values = {
            'prepare_backend_url': self.prepare_backend_url,
            'alias_domain': alias_domain,
            'company_data': company_data,
        }
        return values
