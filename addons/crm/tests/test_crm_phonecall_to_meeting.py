from openerp.tests.common import TransactionCase

class testPhonecall2Meeting(TransactionCase):
	""" Tests for merge Opportunities """

	def setUp(self):
		super(testPhonecall2Meeting, self).setUp()
		p2m = self.env['crm.phonecall2meeting']

	def test_phonecall_to_meeting(self):