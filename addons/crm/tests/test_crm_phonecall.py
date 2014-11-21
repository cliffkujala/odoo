from openerp.tests.common import TransactionCase

class testPhonecall(TransactionCase):
	""" Tests for merge Opportunities """

	def setUp(self):
		super(testPhonecall, self).setUp()

		self.phonecall_id = self.env['ir.model.data'].xmlid_to_res_id('crm.crm_phonecall_1')
		self.phonecall_rec = self.env['crm.phonecall'].browse(self.phonecall_id)

	def test_phonecall(self):
		res = self.phonecall_rec.action_button_convert2opportunity()
		assert res, "There are some problem with action_button_convert2opportunity method"

		res = self.phonecall_rec.action_make_meeting()
		assert res, "There are some problem with action_make_meeting method"		

