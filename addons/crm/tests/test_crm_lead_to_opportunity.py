from openerp.tests.common import TransactionCase

class testLead2Opportunity(TransactionCase):

	def setUp(self):
		super(testLead2Opportunity, self).setUp()

		self.lead2opp_partner_obj = self.env['crm.lead2opportunity.partner']

		self.user_id = self.env["ir.model.data"].xmlid_to_res_id('base.user_root')
		self.team_id = self.env["ir.model.data"].xmlid_to_res_id('sales_team.crm_team_1')
		self.data1 = self.env["ir.model.data"].xmlid_to_res_id('crm.crm_case_4')
		self.data2 = self.env["ir.model.data"].xmlid_to_res_id('crm.crm_case_1')
		self.opportunity_ids = [self.data1, self.data2]
		
		self.lead_ids1 = self.lead2opp_partner_obj.create( 
			{'name':'merge',
			 'user_id':self.user_id,
			 'team_id':self.team_id,
			 'opportunity_ids':[(6, 0, self.opportunity_ids)]
			})
		assert self.lead_ids1, "Record1 will not created from wizard."

		self.lead_ids2 = self.lead2opp_partner_obj.create( 
			{'name':'convert',
			 'user_id':self.user_id,
			 'team_id':self.team_id,
			 'opportunity_ids':[(6, 0, self.opportunity_ids)]
			})
		assert self.lead_ids2, "Record2 will not created from wizard."

	def test_lead_to_opportunity(self):
		res1 = self.lead_ids1.with_context(active_model='crm.lead').action_apply()
		self.assertEqual(res1.get('view_type',''),'form','There are some problem with action_apply method')

		res2 = self.lead2opp_partner_obj.with_context(active_model='crm.lead', active_ids=self.lead_ids2.id).action_apply()
		self.assertEqual(res2.get('view_type',''),'form','There are some problem with action_apply method')
