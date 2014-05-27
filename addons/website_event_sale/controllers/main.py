# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2013-Today OpenERP SA (<http://www.openerp.com>).
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

from openerp import SUPERUSER_ID
from openerp.addons.web import http
from openerp.addons.web.http import request
from openerp.addons.website_event.controllers.main import website_event
from openerp.tools.translate import _
from collections import OrderedDict, defaultdict


class website_event(website_event):

    @http.route(['/event/register/attendee'], type='http', auth="public", methods=['POST'], website=True)
    def register_attendee(self, event_id, **post):
        cr, uid, context = request.cr, request.uid, request.context
        ticket_obj = request.registry.get('event.event.ticket')

        sale = False
        for key, value in post.items():
            quantity = int(value or "0")
            if not quantity:
                continue
            sale = True
            ticket_id = key.split("-")[0] == 'ticket' and int(key.split("-")[1]) or None
            ticket = ticket_obj.browse(cr, SUPERUSER_ID, ticket_id, context=context)
            request.website.sale_get_order(force_create=1)._cart_update(
                product_id=ticket.product_id.id, add_qty=quantity, context=dict(context, event_ticket_id=ticket.id))

        if not sale:
            return request.redirect("/event/%s" % event_id)

        return request.website.render("website_event_sale.event_attendee_registration", {'post': OrderedDict(sorted(post.items())), 'event_id': event_id})

    @http.route(['/event/cart/update'], type='http', auth="public", methods=['POST'], website=True)
    def cart_update(self, event_id, **post):
        cr, uid, context = request.cr, request.uid, request.context
        attendee_obj = request.registry.get('event.registration_attendee')

        dict_attendee = {}
        for key, value in post.items():
            if key.partition('-')[0] == "attendee":
                dict_attendee[key] = value

        # Attendee creation
        attendees = defaultdict(lambda: defaultdict(lambda: defaultdict(dict)))
        for key, value in dict_attendee.items():
            splitted_key = key.rsplit('-')
            attendees[splitted_key[2]][splitted_key[3]][splitted_key[1]] = value

        for key1, value1 in attendees.items():
            for key2, value2 in value1.items():
                value2['event_id'] = event_id
                attendee_id = attendee_obj.create(request.cr, SUPERUSER_ID, value2, context=request.context)

        return request.redirect("/shop/checkout")

    def _add_event(self, event_name="New Event", context={}, **kwargs):
        try:
            dummy, res_id = request.registry.get('ir.model.data').get_object_reference(request.cr, request.uid, 'event_sale', 'product_product_event')
            context['default_event_ticket_ids'] = [[0,0,{
                'name': _('Subscription'),
                'product_id': res_id,
                'deadline' : False,
                'seats_max': 1000,
                'price': 0,
            }]]
        except ValueError:
            pass
        return super(website_event, self)._add_event(event_name, context, **kwargs)
