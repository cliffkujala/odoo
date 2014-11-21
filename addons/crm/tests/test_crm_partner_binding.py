from openerp.tests.common import TransactionCase

class testPartnerBinding(TransactionCase):
	""" Tests for merge Opportunities """

	def setUp(self):
		super(testPartnerBinding, self).setUp()

		self.partner_bind = self.env['crm.partner.binding']
		self.active_id = self.env['ir.model.data'].xmlid_to_res_id('crm.crm_case_12')		

	def test_partner_binding(self):
		partner_id = self.partner_bind.with_context(active_model='crm.lead',active_id=self.active_id)._find_matching_partner()
		assert partner_id, "There are some problem with _find_matching_partner method"