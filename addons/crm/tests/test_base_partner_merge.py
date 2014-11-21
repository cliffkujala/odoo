from openerp.tests.common import TransactionCase

class testBasePartnerMerge(TransactionCase):
	""" Tests for Merge Partner """
		
	def setUp(self):
		super(testBasePartnerMerge, self).setUp()
		self.base_partner_merge = self.env['base.partner.merge.automatic.wizard']
		self.res_partner = self.env['res.partner']

		self.partner1 = self.res_partner.create(
			dict(
				name = "Jusab Sida",
				city = "Junagadh",
				email = "jsi@openerp.com",
				phone = "+01 23 456 789",
				))

		self.partner2 = self.res_partner.create(
			dict(
				name = "Mitesh P.",
				city = "Gandhinagar",
				email = "mpr@openerp.com",
				phone = "+10 23 456 789",
				))

	def test_partner_merge(self):
		self.base_partner_merge._merge(set([self.partner1.id, self.partner2.id]))
		# After merge, only one partner exist.
		result = self.res_partner.search([('name','ilike','Jusab Sida'),('name','ilike','Mitesh P.')])
		self.assertEqual(str(result),'res.partner()','There are sume problem with _merge mwthod')