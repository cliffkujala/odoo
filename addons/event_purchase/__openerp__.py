# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Business Applications
#    Copyright (C) 2013-TODAY OpenERP S.A. (<http://openerp.com>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

{
    'name': 'Events Purchases',
    'version': '0.1',
    'category': 'Tools',
    'description': """
Manage purchases for your events
=================================

This module allows you to manager purchase for your events, book room & request
speakers/trainer participations.
""",
    'author': 'OpenERP SA',
    'depends': ['event', 'purchase'],
    'data': [
        'event_purchase_view.xml',
        'security/ir.model.access.csv',
        'security/event_purchase_rules.xml',
    ],
    'demo': [],
    'test': [],
    'installable': True,
    'auto_install': True
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
