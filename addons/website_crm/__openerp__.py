{
    'name': 'Contact Form',
    'category': 'Website',
    'summary': 'Create Leads From Contact Form',
    'version': '1.0',
    'description': """
OpenERP Contact Form
====================

        """,
    'author': 'OpenERP SA',
    'depends': ['website_form_builder','website_partner', 'crm'],
    'data': [
        'data/website_crm_data.xml',
        'views/website_crm.xml',
    ],
    'installable': True,
    'auto_install': True,
}
