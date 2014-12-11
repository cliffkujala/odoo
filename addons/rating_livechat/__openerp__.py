# -*- coding: utf-8 -*-
{
    'name': 'Livechat Rating',
    'version': '1.0',
    'category': 'Hidden',
    'summary' : "Livesupport customer feedback",
    'description': """
        This module allows to get feedback from the livechat sessions.
    """,
    'author': 'Odoo SA',
    'website': 'http://odoo.com',
    'depends': [
        'rating',
        'im_livechat'
    ],
    'data': [
        'views/rating_livechat.xml',
        'views/rating_livechat_view.xml',
    ],
    'qweb':[
        'static/src/xml/rating_livechat.xml',
    ],
    'installable': True,
    'auto_install': True,
}

