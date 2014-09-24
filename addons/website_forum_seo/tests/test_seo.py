# -*- coding: utf-8 -*-

from openerp.addons.website_forum_seo.tests.common import TestForumSEOCommon
from openerp.exceptions import AccessError
from openerp.tools import mute_logger

class TestSeoCommon(TestForumSEOCommon):
    def test_seo_word_and_url(self):
        seo_1 = self.env['forum.seo'].sudo(self.user_marketing_manager).create({
            'keyword': 'margoulin',
            'replacement_word': 'super margoulin',
            'url': 'http://www.dummy-margoulin.fr',
            'case_sensitive': False,
        })

        content = "<p>Je suis un margoulin qui mange du sopalin.</p>"
        expected_content = "<p>Je suis un <a href='http://www.dummy-margoulin.fr'><span>super margoulin</span></a> qui mange du sopalin.</p>"
        
        # Case 1
        new_content_check = self.env['forum.seo'].update_seo_word(content)
        self.assertEqual(expected_content, new_content_check, 'website_forum_seo: Case 1: After replaced content and expected result not same.')

        # Case 2
        edit_content_check = self.env['forum.seo'].update_seo_word(new_content_check)
        self.assertIn(expected_content, edit_content_check, 'website_forum_seo: Case 2: Already replaced word again replace.')

        addmore_new_content = "<p>Je suis un margoulin qui mange du sopalin. Je suis un margoulin qui mange du sopalin.</p>"
        updated_expected_content = "<p>Je suis un <a href='http://www.dummy-margoulin.fr'><span>super margoulin</span></a> qui mange du sopalin. Je suis un <a href='http://www.dummy-margoulin.fr'><span>super margoulin</span></a> qui mange du sopalin.</p>"

        # Case 3
        addmore_new_content_check = self.env['forum.seo'].update_seo_word(addmore_new_content)
        self.assertIn(updated_expected_content, addmore_new_content_check, 'website_forum_seo: Case 3: content edit after replaced content not match with a expected result.')

        # Case 4
        edit_addmore_new_content_check = self.env['forum.seo'].update_seo_word(addmore_new_content_check)
        self.assertIn(updated_expected_content, edit_addmore_new_content_check, 'website_forum_seo: Case 4: Again content edit, after replaced content not match with a expected result.')

    def test_seo_word(self):
        seo_2 = self.env['forum.seo'].sudo(self.user_erp_manager).create({
            'keyword': 'openerp',
            'replacement_word': 'OpenERP',
            'case_sensitive': False,
        })

        content = "<p>openerp is moving into new territories, beyond ERP.</p>"
        expected_content = "<p><span>OpenERP</span> is moving into new territories, beyond ERP.</p>"

        # Case 5
        new_content_check = self.env['forum.seo'].update_seo_word(content)
        self.assertEqual(expected_content, new_content_check, 'website_forum_seo: Case 5: After replaced content and expected result not same.')

        # Case 6
        edit_content_check = self.env['forum.seo'].update_seo_word(content)
        self.assertEqual(expected_content, edit_content_check, 'website_forum_seo: Case 6: Already replaced word again replace.')

    def test_url(self):
        seo_3 = self.env['forum.seo'].sudo(self.user_erp_manager).create({
            'keyword': 'Odoo',
            'url': 'http://www.odoo.com',
            'case_sensitive': False,
        })

        content = "<p>Two million people use odoo to run their business.</p>"
        expected_content = "<p>Two million people use <a href='http://www.odoo.com'><span>Odoo</span></a> to run their business.</p>"

        # Case 7
        new_content_check = self.env['forum.seo'].update_seo_word(content)
        self.assertEqual(expected_content, new_content_check, 'website_forum_seo: Case 7: Test URL replace become fails.')

        # Case 8
        edit_content_check = self.env['forum.seo'].update_seo_word(content)
        self.assertEqual(expected_content, edit_content_check, 'website_forum_seo: Case 8: Already replaced URL word sentence can not match.')
