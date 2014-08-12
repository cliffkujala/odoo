{
    'name': 'Link Tracker',
    'category': 'Hidden',
    'description': """
Create short and trackable URLs.
=====================================================

        """,
    'version': '1.0',
    'depends':['website','marketing', 'crm'],
    'data' : [
        'views/website_alias.xml',
        'views/website_alias_template.xml',
        'views/website_alias_graphs.xml',
        'security/ir.model.access.csv',
    ],
    'qweb': ['static/src/xml/*.xml'],
    'auto_install': True,
}
