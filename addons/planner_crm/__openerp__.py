# -*- coding: utf-8 -*-

{
    'name': 'CRM Planner',
    'summary': 'Help to configure application',
    'version': '1.0',
    'description': """CRM Planner""",
    'author': 'Odoo SA',
    'depends': ['planner', 'crm'],
    'data': [
        'data/planner_data.xml',
        'views/planner_crm.xml'
    ],
    'installable': True,
}
