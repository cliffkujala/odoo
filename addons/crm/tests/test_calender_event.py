from openerp.tests.common import TransactionCase

class testCalendarEvent(TransactionCase):
	""" Tests for copy lead """
		
	def setUp(self):
		super(testCalendarEvent, self).setUp()

		self.calendar = self.env['calendar.event']
		self.phonecall_id = self.env['ir.model.data'].xmlid_to_res_id('crm.crm_phonecall_1')  
		self.opportunity_id = self.env['ir.model.data'].xmlid_to_res_id('crm.crm_case_27')

	def test_calendar_event(self):
		res = self.calendar.with_context(active_id=self.opportunity_id).create(
			{'duration': 0, 
			 'start': '2014-11-11 00:00:00', 
			 'allday': True, 
			 'stop': '2014-11-11 00:00:00', 
			 'name': 'Demo Meeting'
			 })
		assert res, "There are some problem with create method"