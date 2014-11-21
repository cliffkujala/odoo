from openerp.tests.common import TransactionCase

class testPhonecall2Phonecall(TransactionCase):
	""" Tests for merge Opportunities """

	def setUp(self):
		super(testPhonecall2Phonecall, self).setUp()

		self.phonecall_id = self.env['ir.model.data'].xmlid_to_res_id('crm.crm_phonecall_1')
		self.phonecall_rec = self.env['crm.phonecall'].browse(self.phonecall_id)
		self.phonecall2phonecall = self.env['crm.phonecall2phonecall']
		
	def test_phonecall_to_phonecall(self):
		new_rec = self.phonecall2phonecall.with_context({'active_ids' : [self.phonecall_id]}).create(
			 dict(name = self.phonecall_rec.name, 
				  user_id = self.phonecall_rec.user_id.id, 
				  partner_id = self.phonecall_rec.partner_id.id, 
				  categ_id = self.phonecall_rec.categ_id.id, 
				  team_id = self.phonecall_rec.team_id.id, 
				  action = "schedule",
				  )
			 )
		res = new_rec.action_schedule()
		self.assertEqual(res.get('view_type',''),'form', "There are some problem with action_schedule method")		