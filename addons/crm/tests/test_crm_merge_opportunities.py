from openerp.tests.common import TransactionCase

class testMergeOpportunities(TransactionCase):
	""" Tests for merge Opportunities """

	def setUp(self):
		super(testMergeOpportunities, self).setUp()

		self.merge_opp = self.env['crm.merge.opportunity']
		self.user_id = self.env["ir.model.data"].xmlid_to_res_id('base.user_root')
		self.team_id = self.env["ir.model.data"].xmlid_to_res_id('sales_team.crm_team_1')
		self.data1 = self.env["ir.model.data"].xmlid_to_res_id('crm.crm_case_4')
		self.data2 = self.env["ir.model.data"].xmlid_to_res_id('crm.crm_case_1')
		self.opportunity_ids = [self.data1, self.data2]
		
		self.ids = self.merge_opp.create( 
			{'user_id':self.user_id,'team_id':self.team_id,'opportunity_ids':[(6, 0, self.opportunity_ids)]})
		assert self.ids, "Record will not created from wizard."

	def test_merge_opportunities(self):
		res = self.ids.action_merge()
		self.assertEqual(res.get('view_type',''), 'form',"There are some problem with action_merge method")