# -*- coding: utf-8 -*-

from datetime import datetime
from dateutil import relativedelta
# import json
import random

from openerp import tools
from openerp.exceptions import Warning
from openerp.tools import ustr
from openerp.tools.misc import DEFAULT_SERVER_DATETIME_FORMAT
from openerp.tools.safe_eval import safe_eval as eval
from openerp.tools.translate import _
from openerp.osv import osv, fields


class MassMailingCategory(osv.Model):
    """Model of categories of mass mailing, i.e. marketing, newsletter, ... """
    _name = 'mail.mass_mailing.category'
    _description = 'Mass Mailing Category'
    _order = 'name'

    _columns = {
        'name': fields.char('Name', required=True),
    }


class MassMailingContact(osv.Model):
    """Model of a contact. This model is different from the partner model
    because it holds only some basic information: name, email. The purpose is to
    be able to deal with large contact list to email without bloating the partner
    base."""
    _name = 'mail.mass_mailing.contact'
    _inherit = 'mail.thread'
    _description = 'Mass Mailing Contact'
    _order = 'email'
    _rec_name = 'email'

    _columns = {
        'name': fields.char('Name'),
        'email': fields.char('Email', required=True),
        'create_date': fields.datetime('Create Date'),
        'list_id': fields.many2one(
            'mail.mass_mailing.list', string='Mailing List',
            ondelete='cascade', required=True,
        ),
        'opt_out': fields.boolean('Opt Out', help='The contact has chosen not to receive mails anymore from this list'),
        'unsubscription_date': fields.datetime('Unsubscription Date'),
        'message_bounce': fields.integer('Bounce', help='Counter of the number of bounced emails for this contact.'),
    }

    def _get_latest_list(self, cr, uid, context={}):
        lid = self.pool.get('mail.mass_mailing.list').search(cr, uid, [], limit=1, order='id desc', context=context)
        return lid and lid[0] or False

    _defaults = {
        'list_id': _get_latest_list
    }

    def on_change_opt_out(self, cr, uid, id, opt_out, context=None):
        return {'value': {
            'unsubscription_date': opt_out and fields.datetime.now() or False,
        }}

    def create(self, cr, uid, vals, context=None):
        if 'opt_out' in vals:
            vals['unsubscription_date'] = vals['opt_out'] and fields.datetime.now() or False
        return super(MassMailingContact, self).create(cr, uid, vals, context=context)

    def write(self, cr, uid, ids, vals, context=None):
        if 'opt_out' in vals:
            vals['unsubscription_date'] = vals['opt_out'] and fields.datetime.now() or False
        return super(MassMailingContact, self).write(cr, uid, ids, vals, context=context)

    def get_name_email(self, name, context):
        name, email = self.pool['res.partner']._parse_partner_name(name, context=context)
        if name and not email:
            email = name
        if email and not name:
            name = email
        return name, email

    def name_create(self, cr, uid, name, context=None):
        name, email = self.get_name_email(name, context=context)
        rec_id = self.create(cr, uid, {'name': name, 'email': email}, context=context)
        return self.name_get(cr, uid, [rec_id], context)[0]

    def add_to_list(self, cr, uid, name, list_id, context=None):
        name, email = self.get_name_email(name, context=context)
        rec_id = self.create(cr, uid, {'name': name, 'email': email, 'list_id': list_id}, context=context)
        return self.name_get(cr, uid, [rec_id], context)[0]

    def message_get_default_recipients(self, cr, uid, ids, context=None):
        res = {}
        for record in self.browse(cr, uid, ids, context=context):
            res[record.id] = {'partner_ids': [], 'email_to': record.email, 'email_cc': False}
        return res

    def message_receive_bounce(self, cr, uid, ids, mail_id=None, context=None):
        """Called by ``message_process`` when a bounce email (such as Undelivered
        Mail Returned to Sender) is received for an existing thread. As contacts
        do not inherit form mail.thread, we have to define this method to be able
        to track bounces (see mail.thread for more details). """
        for obj in self.browse(cr, uid, ids, context=context):
            self.write(cr, uid, [obj.id], {'message_bounce': obj.message_bounce + 1}, context=context)


class MassMailingList(osv.Model):
    """Model of a contact list. """
    _name = 'mail.mass_mailing.list'
    _order = 'name'
    _description = 'Mailing List'

    def _get_contact_nbr(self, cr, uid, ids, name, arg, context=None):
        result = dict.fromkeys(ids, 0)
        Contacts = self.pool.get('mail.mass_mailing.contact')
        for group in Contacts.read_group(cr, uid, [('list_id', 'in', ids), ('opt_out', '!=', True)], ['list_id'], ['list_id'], context=context):
            result[group['list_id'][0]] = group['list_id_count']
        return result

    _columns = {
        'name': fields.char('Mailing List', required=True),
        'create_date': fields.datetime('Creation Date'),
        'contact_nbr': fields.function(
            _get_contact_nbr, type='integer',
            string='Number of Contacts',
        ),
    }


class MassMailingStage(osv.Model):
    """Stage for mass mailing campaigns. """
    _name = 'mail.mass_mailing.stage'
    _description = 'Mass Mailing Campaign Stage'
    _order = 'sequence'

    _columns = {
        'name': fields.char('Name', required=True, translate=True),
        'sequence': fields.integer('Sequence'),
    }

    _defaults = {
        'sequence': 0,
    }


class MassMailingCampaign(osv.Model):
    """Model of mass mailing campaigns. """
    _name = "mail.mass_mailing.campaign"
    _description = 'Mass Mailing Campaign'

    def _get_statistics(self, cr, uid, ids, name, arg, context=None):
        """ Compute statistics of the mass mailing campaign """
        results = {}
        cr.execute("""
            SELECT
                c.id as campaign_id,
                COUNT(s.id) AS total,
                COUNT(CASE WHEN s.sent is not null THEN 1 ELSE null END) AS sent,
                COUNT(CASE WHEN s.scheduled is not null AND s.sent is null AND s.exception is null THEN 1 ELSE null END) AS scheduled,
                COUNT(CASE WHEN s.scheduled is not null AND s.sent is null AND s.exception is not null THEN 1 ELSE null END) AS failed,
                COUNT(CASE WHEN s.id is not null AND s.bounced is null THEN 1 ELSE null END) AS delivered,
                COUNT(CASE WHEN s.opened is not null THEN 1 ELSE null END) AS opened,
                COUNT(CASE WHEN s.replied is not null THEN 1 ELSE null END) AS replied ,
                COUNT(CASE WHEN s.bounced is not null THEN 1 ELSE null END) AS bounced
            FROM
                mail_mail_statistics s
            RIGHT JOIN
                mail_mass_mailing_campaign c
                ON (c.id = s.mass_mailing_campaign_id)
            WHERE
                c.id IN %s
            GROUP BY
                c.id
        """, (tuple(ids), ))
        for row in cr.dictfetchall():
            results[row.pop('campaign_id')] = row
            total = row['total'] or 1
            row['delivered'] = row['sent'] - row['bounced']
            row['received_ratio'] = 100.0 * row['delivered'] / total
            row['opened_ratio'] = 100.0 * row['opened'] / total
            row['replied_ratio'] = 100.0 * row['replied'] / total
        return results

    _columns = {
        'name': fields.char('Name', required=True),
        'stage_id': fields.many2one('mail.mass_mailing.stage', 'Stage', required=True),
        'user_id': fields.many2one(
            'res.users', 'Responsible',
            required=True,
        ),
        'category_ids': fields.many2many(
            'mail.mass_mailing.category', 'mail_mass_mailing_category_rel',
            'category_id', 'campaign_id', string='Categories'),
        'mass_mailing_ids': fields.one2many(
            'mail.mass_mailing', 'mass_mailing_campaign_id',
            'Mass Mailings',
        ),
        'unique_ab_testing': fields.boolean(
            'AB Testing',
            help='If checked, recipients will be mailed only once, allowing to send'
                 'various mailings in a single campaign to test the effectiveness'
                 'of the mailings.'),
        'color': fields.integer('Color Index'),
        # stat fields
        'total': fields.function(
            _get_statistics, string='Total',
            type='integer', multi='_get_statistics'
        ),
        'scheduled': fields.function(
            _get_statistics, string='Scheduled',
            type='integer', multi='_get_statistics'
        ),
        'failed': fields.function(
            _get_statistics, string='Failed',
            type='integer', multi='_get_statistics'
        ),
        'sent': fields.function(
            _get_statistics, string='Sent Emails',
            type='integer', multi='_get_statistics'
        ),
        'delivered': fields.function(
            _get_statistics, string='Delivered',
            type='integer', multi='_get_statistics',
        ),
        'opened': fields.function(
            _get_statistics, string='Opened',
            type='integer', multi='_get_statistics',
        ),
        'replied': fields.function(
            _get_statistics, string='Replied',
            type='integer', multi='_get_statistics'
        ),
        'bounced': fields.function(
            _get_statistics, string='Bounced',
            type='integer', multi='_get_statistics'
        ),
        'received_ratio': fields.function(
            _get_statistics, string='Received Ratio',
            type='integer', multi='_get_statistics',
        ),
        'opened_ratio': fields.function(
            _get_statistics, string='Opened Ratio',
            type='integer', multi='_get_statistics',
        ),
        'replied_ratio': fields.function(
            _get_statistics, string='Replied Ratio',
            type='integer', multi='_get_statistics',
        ),
    }

    def _get_default_stage_id(self, cr, uid, context=None):
        stage_ids = self.pool['mail.mass_mailing.stage'].search(cr, uid, [], limit=1, context=context)
        return stage_ids and stage_ids[0] or False

    _defaults = {
        'user_id': lambda self, cr, uid, ctx=None: uid,
        'stage_id': lambda self, *args: self._get_default_stage_id(*args),
    }

    def get_recipients(self, cr, uid, ids, model=None, context=None):
        """Return the recipients of a mailing campaign. This is based on the statistics
        build for each mailing. """
        Statistics = self.pool['mail.mail.statistics']
        res = dict.fromkeys(ids, False)
        for cid in ids:
            domain = [('mass_mailing_campaign_id', '=', cid)]
            if model:
                domain += [('model', '=', model)]
            stat_ids = Statistics.search(cr, uid, domain, context=context)
            res[cid] = set(stat.res_id for stat in Statistics.browse(cr, uid, stat_ids, context=context))
        return res


class MassMailing(osv.Model):
    """ MassMailing models a wave of emails for a mass mailign campaign.
    A mass mailing is an occurence of sending emails. """

    _name = 'mail.mass_mailing'
    _description = 'Mass Mailing'
    # number of periods for tracking mail_mail statistics
    _period_number = 6
    _order = 'sent_date DESC'
    # _send_trigger = 5  # Number under which mails are send directly

    def __get_bar_values(self, cr, uid, obj, domain, read_fields, value_field, groupby_field, date_begin, context=None):
        """ Generic method to generate data for bar chart values using SparklineBarWidget.
            This method performs obj.read_group(cr, uid, domain, read_fields, groupby_field).

            :param obj: the target model (i.e. crm_lead)
            :param domain: the domain applied to the read_group
            :param list read_fields: the list of fields to read in the read_group
            :param str value_field: the field used to compute the value of the bar slice
            :param str groupby_field: the fields used to group

            :return list section_result: a list of dicts: [
                                                {   'value': (int) bar_column_value,
                                                    'tootip': (str) bar_column_tooltip,
                                                }
                                            ]
        """
        date_begin = date_begin.date()
        section_result = [{'value': 0,
                           'tooltip': ustr((date_begin + relativedelta.relativedelta(days=i)).strftime('%d %B %Y')),
                           } for i in range(0, self._period_number)]
        group_obj = obj.read_group(cr, uid, domain, read_fields, groupby_field, context=context)
        field = obj._fields.get(groupby_field.split(':')[0])
        pattern = tools.DEFAULT_SERVER_DATE_FORMAT if field.type == 'date' else tools.DEFAULT_SERVER_DATETIME_FORMAT
        for group in group_obj:
            group_begin_date = datetime.strptime(group['__domain'][0][2], pattern).date()
            timedelta = relativedelta.relativedelta(group_begin_date, date_begin)
            section_result[timedelta.days] = {'value': group.get(value_field, 0), 'tooltip': group.get(groupby_field)}
        return section_result

    def _get_statistics(self, cr, uid, ids, name, arg, context=None):
        """ Compute statistics of the mass mailing """
        results = {}
        cr.execute("""
            SELECT
                m.id as mailing_id,
                COUNT(s.id) AS total,
                COUNT(CASE WHEN s.sent is not null THEN 1 ELSE null END) AS sent,
                COUNT(CASE WHEN s.scheduled is not null AND s.sent is null AND s.exception is null THEN 1 ELSE null END) AS scheduled,
                COUNT(CASE WHEN s.scheduled is not null AND s.sent is null AND s.exception is not null THEN 1 ELSE null END) AS failed,
                COUNT(CASE WHEN s.sent is not null AND s.bounced is null THEN 1 ELSE null END) AS delivered,
                COUNT(CASE WHEN s.opened is not null THEN 1 ELSE null END) AS opened,
                COUNT(CASE WHEN s.replied is not null THEN 1 ELSE null END) AS replied,
                COUNT(CASE WHEN s.bounced is not null THEN 1 ELSE null END) AS bounced,
                COUNT(CASE WHEN s.exception is not null THEN 1 ELSE null END) AS failed
            FROM
                mail_mail_statistics s
            RIGHT JOIN
                mail_mass_mailing m
                ON (m.id = s.mass_mailing_id)
            WHERE
                m.id IN %s
            GROUP BY
                m.id
        """, (tuple(ids), ))
        for row in cr.dictfetchall():
            results[row.pop('mailing_id')] = row
            total = row['total'] or 1
            row['received_ratio'] = 100.0 * row['delivered'] / total
            row['opened_ratio'] = 100.0 * row['opened'] / total
            row['replied_ratio'] = 100.0 * row['replied'] / total
            row['bounced_ratio'] = 100.0 * row['bounced'] / total
        return results

    def _get_mailing_model(self, cr, uid, context=None):
        res = []
        for model_name in self.pool:
            model = self.pool[model_name]
            if hasattr(model, '_mail_mass_mailing') and getattr(model, '_mail_mass_mailing'):
                res.append((model._name, getattr(model, '_mail_mass_mailing')))
        res.append(('mail.mass_mailing.contact', _('Mailing List')))
        return res

    def _get_next_departure(self, cr, uid, ids, name, arg, context=None):
        mass_mailings = self.browse(cr, uid, ids, context=context)
        cron_next_call = self.pool.get('ir.model.data').xmlid_to_object(cr, uid, 'mass_mailing.ir_cron_mass_mailing_queue', context=context).nextcall

        result = {}
        for mass_mailing in mass_mailings:
            schedule_date = mass_mailing.schedule_date
            if schedule_date:
                if datetime.now() > datetime.strptime(schedule_date, tools.DEFAULT_SERVER_DATETIME_FORMAT):
                    result[mass_mailing.id] = cron_next_call
                else:
                    result[mass_mailing.id] = schedule_date
            else:
                result[mass_mailing.id] = cron_next_call
        return result

    def _get_total(self, cr, uid, ids, name, arg, context=None):
        mass_mailings = self.browse(cr, uid, ids, context=context)

        result = {}
        for mass_mailing in mass_mailings:
            mailing = self.browse(cr, uid, mass_mailing.id, context=context)
            result[mass_mailing.id] = len(self.get_recipients(cr, uid, mailing, context=context))
        return result

    # indirections for inheritance
    _mailing_model = lambda self, *args, **kwargs: self._get_mailing_model(*args, **kwargs)

    _columns = {
        'name': fields.char('Subject', required=True),
        'email_from': fields.char('From', required=True),
        'create_date': fields.datetime('Creation Date'),
        'sent_date': fields.datetime('Sent Date', oldname='date', copy=False),
        'schedule_date': fields.datetime('Schedule Date'),
        'body_html': fields.html('Body'),
        'attachment_ids': fields.many2many(
            'ir.attachment', 'mass_mailing_ir_attachments_rel',
            'mass_mailing_id', 'attachment_id', 'Attachments'
        ),
        'keep_archives': fields.boolean('Keep Archives'),
        'mass_mailing_campaign_id': fields.many2one(
            'mail.mass_mailing.campaign', 'Mass Mailing Campaign',
            ondelete='set null',
        ),
        'state': fields.selection(
            [('draft', 'Draft'), ('test', 'Tested'), ('in_queue', 'In Queue'), ('sending', 'Sending'), ('done', 'Sent')],
            string='Status', required=True, copy=False,
        ),
        'color': fields.related(
            'mass_mailing_campaign_id', 'color',
            type='integer', string='Color Index',
        ),
        # mailing options
        'reply_to_mode': fields.selection(
            [('thread', 'In Document'), ('email', 'Specified Email Address')],
            string='Reply-To Mode', required=True,
        ),
        'reply_to': fields.char('Reply To', help='Preferred Reply-To Address'),
        # recipients
        'mailing_model': fields.selection(_mailing_model, string='Recipients Model', required=True),
        'mailing_domain': fields.char('Domain', oldname='domain'),
        'contact_list_ids': fields.many2many(
            'mail.mass_mailing.list', 'mail_mass_mailing_list_rel',
            string='Mailing Lists',
        ),
        'contact_ab_pc': fields.integer(
            'AB Testing percentage',
            help='Percentage of the contacts that will be mailed. Recipients will be taken randomly.'
        ),
        # statistics data
        'statistics_ids': fields.one2many(
            'mail.mail.statistics', 'mass_mailing_id',
            'Emails Statistics',
        ),
        'total': fields.function(
            _get_total, string='Total',
            type='integer',
        ),
        'scheduled': fields.function(
            _get_statistics, string='Scheduled',
            type='integer', multi='_get_statistics',
        ),
        'failed': fields.function(
            _get_statistics, string='Failed',
            type='integer', multi='_get_statistics',
        ),
        'sent': fields.function(
            _get_statistics, string='Sent',
            type='integer', multi='_get_statistics',
        ),
        'delivered': fields.function(
            _get_statistics, string='Delivered',
            type='integer', multi='_get_statistics',
        ),
        'opened': fields.function(
            _get_statistics, string='Opened',
            type='integer', multi='_get_statistics',
        ),
        'replied': fields.function(
            _get_statistics, string='Replied',
            type='integer', multi='_get_statistics',
        ),
        'bounced': fields.function(
            _get_statistics, string='Bounced',
            type='integer', multi='_get_statistics',
        ),
        'failed': fields.function(
            _get_statistics, string='Failed',
            type='integer', multi='_get_statistics',
        ),
        'received_ratio': fields.function(
            _get_statistics, string='Received Ratio',
            type='integer', multi='_get_statistics',
        ),
        'opened_ratio': fields.function(
            _get_statistics, string='Opened Ratio',
            type='integer', multi='_get_statistics',
        ),
        'replied_ratio': fields.function(
            _get_statistics, string='Replied Ratio',
            type='integer', multi='_get_statistics',
        ),
        'bounced_ratio': fields.function(
            _get_statistics, String='Bouncded Ratio',
            type='integer', multi='_get_statistics',
        ),
        'next_departure': fields.function(
            _get_next_departure, string='Next Departure',
            type='datetime'
        ),
    }

    def default_get(self, cr, uid, fields, context=None):
        res = super(MassMailing, self).default_get(cr, uid, fields, context=context)
        if 'reply_to_mode' in fields and not 'reply_to_mode' in res and res.get('mailing_model'):
            if res['mailing_model'] in ['res.partner', 'mail.mass_mailing.contact']:
                res['reply_to_mode'] = 'email'
            else:
                res['reply_to_mode'] = 'thread'
        return res

    _defaults = {
        'state': 'draft',
        'email_from': lambda self, cr, uid, ctx=None: self.pool['mail.message']._get_default_from(cr, uid, context=ctx),
        'reply_to': lambda self, cr, uid, ctx=None: self.pool['mail.message']._get_default_from(cr, uid, context=ctx),
        'mailing_model': 'mail.mass_mailing.contact',
        'contact_ab_pc': 100,
    }

    #------------------------------------------------------
    # Technical stuff
    #------------------------------------------------------

    def copy_data(self, cr, uid, id, default=None, context=None):
        mailing = self.browse(cr, uid, id, context=context)
        default = dict(default or {},
                       name=_('%s (copy)') % mailing.name)
        return super(MassMailing, self).copy_data(cr, uid, id, default, context=context)

    def read_group(self, cr, uid, domain, fields, groupby, offset=0, limit=None, context=None, orderby=False, lazy=True):
        """ Override read_group to always display all states. """
        if groupby and groupby[0] == "state":
            # Default result structure
            # states = self._get_state_list(cr, uid, context=context)
            states = [('draft', 'Draft'), ('test', 'Tested'), ('in_queue', 'In Queue'), ('sending', 'Sending'), ('done', 'Sent')]
            read_group_all_states = [{
                '__context': {'group_by': groupby[1:]},
                '__domain': domain + [('state', '=', state_value)],
                'state': state_value,
                'state_count': 0,
            } for state_value, state_name in states]
            # Get standard results
            read_group_res = super(MassMailing, self).read_group(cr, uid, domain, fields, groupby, offset=offset, limit=limit, context=context, orderby=orderby)
            # Update standard results with default results
            result = []
            for state_value, state_name in states:
                res = filter(lambda x: x['state'] == state_value, read_group_res)
                if not res:
                    res = filter(lambda x: x['state'] == state_value, read_group_all_states)
                res[0]['state'] = [state_value, state_name]
                result.append(res[0])
            return result
        else:
            return super(MassMailing, self).read_group(cr, uid, domain, fields, groupby, offset=offset, limit=limit, context=context, orderby=orderby)

    #------------------------------------------------------
    # Views & Actions
    #------------------------------------------------------

    def on_change_model_and_list(self, cr, uid, ids, mailing_model, list_ids, context=None):
        print mailing_model
        print list_ids

        value = {}
        if mailing_model == 'mail.mass_mailing.contact':
            mailing_list_ids = set()
            for item in list_ids:
                if isinstance(item, (int, long)):
                    mailing_list_ids.add(item)
                elif len(item) == 3:
                    mailing_list_ids |= set(item[2])
            if mailing_list_ids:
                value['mailing_domain'] = "[('list_id', 'in', %s)]" % list(mailing_list_ids)
            else:
                value['mailing_domain'] = "[('list_id', '=', False)]"
        else:
            value['mailing_domain'] = False
        return {'value': value}

    def action_duplicate(self, cr, uid, ids, context=None):
        copy_id = None
        for mid in ids:
            copy_id = self.copy(cr, uid, mid, context=context)
        if copy_id:
            return {
                'type': 'ir.actions.act_window',
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'mail.mass_mailing',
                'res_id': copy_id,
                'context': context,
            }
        return False

    def action_test_mailing(self, cr, uid, ids, context=None):
        ctx = dict(context, default_mass_mailing_id=ids[0])
        return {
            'name': _('Test Mailing'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'mail.mass_mailing.test',
            'target': 'new',
            'context': ctx,
        }

    def action_edit_html(self, cr, uid, ids, context=None):
        if not len(ids) == 1:
            raise ValueError('One and only one ID allowed for this action')
        mail = self.browse(cr, uid, ids[0], context=context)
        url = '/website_mail/email_designer?model=mail.mass_mailing&res_id=%d&template_model=%s&enable_editor=1' % (ids[0], mail.mailing_model)
        return {
            'name': _('Open with Visual Editor'),
            'type': 'ir.actions.act_url',
            'url': url,
            'target': 'self',
        }

    #------------------------------------------------------
    # Email Sending
    #------------------------------------------------------

    def get_recipients(self, cr, uid, mailing, context=None):
        if mailing.mailing_domain:
            domain = eval(mailing.mailing_domain)
            res_ids = self.pool[mailing.mailing_model].search(cr, uid, domain, context=context)
        else:
            res_ids = []
            domain = [('id', 'in', res_ids)]

        # randomly choose a fragment
        if mailing.contact_ab_pc < 100:
            contact_nbr = self.pool[mailing.mailing_model].search(cr, uid, domain, count=True, context=context)
            topick = int(contact_nbr / 100.0 * mailing.contact_ab_pc)
            if mailing.mass_mailing_campaign_id and mailing.mass_mailing_campaign_id.unique_ab_testing:
                already_mailed = self.pool['mail.mass_mailing.campaign'].get_recipients(cr, uid, [mailing.mass_mailing_campaign_id.id], context=context)[mailing.mass_mailing_campaign_id.id]
            else:
                already_mailed = set([])
            remaining = set(res_ids).difference(already_mailed)
            if topick > len(remaining):
                topick = len(remaining)
            res_ids = random.sample(remaining, topick)
        return res_ids

    def get_remaining_recipients(self, cr, uid, mailing, context=None):
        res_ids = self.get_recipients(cr, uid, mailing, context=context)
        already_mailed = self.pool['mail.mail.statistics'].search_read(cr, uid, [('model', '=', mailing.mailing_model),
                                                                                 ('res_id', 'in', res_ids),
                                                                                 ('mass_mailing_id', '=', mailing.id)], ['res_id'], context=context)
        already_mailed_res_ids = [record['res_id'] for record in already_mailed]
        return list(set(res_ids) - set(already_mailed_res_ids))

    def send_mail(self, cr, uid, ids, context=None):
        author_id = self.pool['res.users'].browse(cr, uid, uid, context=context).partner_id.id
        for mailing in self.browse(cr, uid, ids, context=context):
            # instantiate an email composer + send emails
            res_ids = self.get_remaining_recipients(cr, uid, mailing, context=context)
            if not res_ids:
                raise Warning('Please select recipients.')

            if context:
                comp_ctx = dict(context, active_ids=res_ids)
            else:
                comp_ctx = {'active_ids': res_ids}
            composer_values = {
                'author_id': author_id,
                'body': mailing.body_html,
                'subject': mailing.name,
                'model': mailing.mailing_model,
                'email_from': mailing.email_from,
                'record_name': False,
                'composition_mode': 'mass_mail',
                'mass_mailing_id': mailing.id,
                'mailing_list_ids': [(4, l.id) for l in mailing.contact_list_ids],
                'no_auto_thread': mailing.reply_to_mode != 'thread',
            }
            if mailing.reply_to_mode == 'email':
                composer_values['reply_to'] = mailing.reply_to

            composer_id = self.pool['mail.compose.message'].create(cr, uid, composer_values, context=comp_ctx)
            self.pool['mail.compose.message'].send_mail(cr, uid, [composer_id], auto_commit=True, context=comp_ctx)
            self.write(cr, uid, [mailing.id], {'sent_date': fields.datetime.now(), 'state': 'done'}, context=context)
        return True

    def put_in_queue(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'state': 'in_queue'}, context=context)

    def cancel_mass_mailing(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'state': 'draft'}, context=context)

    def retry_failed_mail(self, cr, uid, mass_mailing_ids, context=None):
        mail_mail_ids = self.pool.get('mail.mail').search(cr, uid, [('mailing_id', 'in', mass_mailing_ids), ('state', '=', 'exception')], context=context)
        self.pool.get('mail.mail').unlink(cr, uid, mail_mail_ids, context=context)

        mail_mail_statistics_ids = self.pool.get('mail.mail.statistics').search(cr, uid, [('mail_mail_id_int', 'in', mail_mail_ids)])
        self.pool.get('mail.mail.statistics').unlink(cr, uid, mail_mail_statistics_ids, context=context)

        self.write(cr, uid, mass_mailing_ids, {'state': 'in_queue'})

    def _process_mass_mailing_queue(self, cr, uid, context=None):
        now = datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT)
        mass_mailing_ids = self.search(cr, uid, [('state', 'in', ('in_queue', 'sending')), '|', ('schedule_date', '<', now), ('schedule_date', '=', False)], context=context)

        for mass_mailing_id in mass_mailing_ids:
            mass_mailing_record = self.browse(cr, uid, mass_mailing_id, context=context)

            if len(self.get_remaining_recipients(cr, uid, mass_mailing_record, context=context)) > 0:
                self.write(cr, uid, [mass_mailing_id], {'state': 'sending'}, context=context)
                self.send_mail(cr, uid, [mass_mailing_id], context=context)
            else:
                self.write(cr, uid, [mass_mailing_id], {'state': 'done'}, context=context)
