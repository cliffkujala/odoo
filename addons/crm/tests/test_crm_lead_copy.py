from openerp.tests.common import TransactionCase

class testLeadCopy(TransactionCase):
	""" Tests for copy lead """
		
	def setUp(self):
		super(testLeadCopy, self).setUp()
		self.lead_obj = self.env['crm.lead']
		self.id = self.env["ir.model.data"].xmlid_to_res_id('crm.crm_case_4')
		self.lead_rec = self.lead_obj.browse(self.id)

	def test_lead_copy(self):
		new_lead = self.lead_rec.copy()
		self.assertTrue(new_lead, "There are some problem with copy method")