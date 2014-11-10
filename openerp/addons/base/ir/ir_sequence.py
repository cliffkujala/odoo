# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-TODAY OpenERP S.A. <http://www.openerp.com>
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

import logging
import time

import openerp
from openerp.osv import osv
from openerp.tools.translate import _

_logger = logging.getLogger(__name__)

class ir_sequence_type(openerp.osv.osv.osv):
    _name = 'ir.sequence.type'
    _order = 'name'
    _columns = {
        'name': openerp.osv.fields.char('Name', required=True),
        'code': openerp.osv.fields.char('Code', size=32, required=True),
    }

    _sql_constraints = [
        ('code_unique', 'unique(code)', '`code` must be unique.'),
    ]

def _code_get(self, cr, uid, context=None):
    cr.execute('select code, name from ir_sequence_type')
    return cr.fetchall()

class ir_sequence(openerp.osv.osv.osv):
    """ Sequence model.

    The sequence model allows to define and use so-called sequence objects.
    Such objects are used to generate unique identifiers in a transaction-safe
    way.

    """
    _name = 'ir.sequence'
    _order = 'name'
    
    def _get_number_next_actual(self, cr, user, ids, field_name, arg, context=None):
        '''Return number from ir_sequence row when no_gap implementation,
        and number from postgres sequence when standard implementation.'''
        res = dict.fromkeys(ids)
        for element in self.browse(cr, user, ids, context=context):
            if  element.implementation != 'standard':
                res[element.id] = element.number_next
            else:
                # get number from postgres sequence. Cannot use
                # currval, because that might give an error when
                # not having used nextval before.
                statement = (
                    "SELECT last_value, increment_by, is_called"
                    " FROM ir_sequence_%03d"
                    % element.id)
                cr.execute(statement)
                (last_value, increment_by, is_called) = cr.fetchone()
                if is_called:
                    res[element.id] = last_value + increment_by
                else:
                    res[element.id] = last_value
        return res

    def _set_number_next_actual(self, cr, uid, id, name, value, args=None, context=None):
        return self.write(cr, uid, id, {'number_next': value or 0}, context=context)


    _columns = {
        'name': openerp.osv.fields.char('Name', size=64, required=True),
        'code': openerp.osv.fields.selection(_code_get, 'Sequence Type', size=64),
        'implementation': openerp.osv.fields.selection( # TODO update the view
            [('standard', 'Standard'), ('no_gap', 'No gap')],
            'Implementation', required=True,
            help="Two sequence object implementations are offered: Standard "
            "and 'No gap'. The later is slower than the former but forbids any"
            " gap in the sequence (while they are possible in the former)."),
        'active': openerp.osv.fields.boolean('Active'),
        'prefix': openerp.osv.fields.char('Prefix', help="Prefix value of the record for the sequence"),
        'suffix': openerp.osv.fields.char('Suffix', help="Suffix value of the record for the sequence"),
        'number_next': openerp.osv.fields.integer('Next Number', required=True, help="Next number of this sequence"),
        'number_next_actual': openerp.osv.fields.function(_get_number_next_actual, fnct_inv=_set_number_next_actual, type='integer', required=True, string='Next Number', help='Next number that will be used. This number can be incremented frequently so the displayed value might already be obsolete'),
        'number_increment': openerp.osv.fields.integer('Increment Number', required=True, help="The next number of the sequence will be incremented by this number"),
        'padding' : openerp.osv.fields.integer('Number Padding', required=True, help="Odoo will automatically adds some '0' on the left of the 'Next Number' to get the required padding size."),
        'company_id': openerp.osv.fields.many2one('res.company', 'Company'),
        'use_date_range': openerp.osv.fields.boolean('Use subsequences per date_range'),
        'date_range_ids': openerp.osv.fields.one2many('ir.sequence.date_range', 'sequence_main_id', 'Subsequences'),
    }
    _defaults = {
        'implementation': 'standard',
        'active': True,
        'company_id': lambda s,cr,uid,c: s.pool.get('res.company')._company_default_get(cr, uid, 'ir.sequence', context=c),
        'number_increment': 1,
        'number_next': 1,
        'number_next_actual': 1,
        'padding' : 0,
    }

    def init(self, cr):
        return # Don't do the following index yet.
        # CONSTRAINT/UNIQUE INDEX on (code, company_id) 
        # /!\ The unique constraint 'unique_name_company_id' is not sufficient, because SQL92
        # only support field names in constraint definitions, and we need a function here:
        # we need to special-case company_id to treat all NULL company_id as equal, otherwise
        # we would allow duplicate (code, NULL) ir_sequences.
        cr.execute("""
            SELECT indexname FROM pg_indexes WHERE indexname =
            'ir_sequence_unique_code_company_id_idx'""")
        if not cr.fetchone():
            cr.execute("""
                CREATE UNIQUE INDEX ir_sequence_unique_code_company_id_idx
                ON ir_sequence (code, (COALESCE(company_id,-1)))""")

    def _create_sequence(self, cr, uid, id, number_increment, number_next, seq_date_id=False):
        """ Create a PostreSQL sequence.

        There is no access rights check.
        """
        if number_increment == 0:
             raise osv.except_osv(_('Warning!'),_("Increment number must not be zero."))
        assert isinstance(id, (int, long))
        if seq_date_id:
            sql = "CREATE SEQUENCE ir_sequence_%03d_%03d INCREMENT BY %%s START WITH %%s" % (id, seq_date_id)
        else:
            sql = "CREATE SEQUENCE ir_sequence_%03d INCREMENT BY %%s START WITH %%s" % id
        cr.execute(sql, (number_increment, number_next))

    def _drop_sequence(self, cr, uid, ids):
        """ Drop the PostreSQL sequence if it exists.

        There is no access rights check.
        """

        ids = ids if isinstance(ids, (list, tuple)) else [ids]
        assert all(isinstance(i, (int, long)) for i in ids), \
            "Only ids in (int, long) allowed."
        names =[]
        for id in ids:
            for seq_date_id in self.browse(cr, uid, id).date_range_ids:
                names.append('ir_sequence_%03d_%03d' % (id, seq_date_id))
            names.append('ir_sequence_%03d' % id)
        names = ','.join(names)

        # RESTRICT is the default; it prevents dropping the sequence if an
        # object depends on it.
        cr.execute("DROP SEQUENCE IF EXISTS %s RESTRICT " % names)

    def _alter_sequence(self, cr, uid, id, number_increment=None, number_next=None, seq_date_id=False):
        """ Alter a PostreSQL sequence.

        There is no access rights check.
        """
        if number_increment == 0:
            raise osv.except_osv(_('Warning!'),_("Increment number must not be zero."))
        assert isinstance(id, (int, long))
        if seq_date_id:
            assert isinstance(seq_date_id, (int, long))
            seq_name = 'ir_sequence_%03d_%03d' % (id, seq_date_id)
        else:
            seq_name = 'ir_sequence_%03d' % (id,)
        cr.execute("SELECT relname FROM pg_class WHERE relkind = %s AND relname=%s", ('S', seq_name))
        if not cr.fetchone():
            # sequence is not created yet, we're inside create() so ignore it, will be set later
            return
        statement = "ALTER SEQUENCE %s" % (seq_name, )
        if number_increment is not None:
            statement += " INCREMENT BY %d" % (number_increment, )
        if number_next is not None:
            statement += " RESTART WITH %d" % (number_next, )
        cr.execute(statement)

    def create(self, cr, uid, values, context=None):
        """ Create a sequence, in implementation == standard a fast gaps-allowed PostgreSQL sequence is used.
        """
        values = self._add_missing_default_values(cr, uid, values, context)
        values['id'] = super(ir_sequence, self).create(cr, uid, values, context)
        if values['implementation'] == 'standard':
            self._create_sequence(cr, uid, values['id'], values['number_increment'], values['number_next'])
        return values['id']

    def unlink(self, cr, uid, ids, context=None):
        super(ir_sequence, self).unlink(cr, uid, ids, context)
        self._drop_sequence(cr, uid, ids)
        return True

    def write(self, cr, uid, ids, values, context=None):
        if not isinstance(ids, (list, tuple)):
            ids = [ids]
        new_implementation = values.get('implementation')
        rows = self.read(cr, uid, ids, ['implementation', 'number_increment', 'number_next', 'date_range_ids'], context)
        super(ir_sequence, self).write(cr, uid, ids, values, context)

        for row in rows:
            # 4 cases: we test the previous impl. against the new one.
            i = values.get('number_increment', row['number_increment'])
            n = values.get('number_next', row['number_next'])
            if row['implementation'] == 'standard':
                if new_implementation in ('standard', None):
                    # Implementation has NOT changed.
                    # Only change sequence if really requested.
                    if row['number_next'] != n:
                        self._alter_sequence(cr, uid, row['id'], number_next=n)
                    if row['number_increment'] != i:
                        self._alter_sequence(cr, uid, row['id'], number_increment=i)
                        for seq_date_id in row['date_range_ids']:
                            self._alter_sequence(cr, uid, row['id'], number_increment=i, seq_date_id=seq_date_id)
                else:
                    self._drop_sequence(cr, row['id'])
            else:
                if new_implementation in ('no_gap', None):
                    pass
                else:
                    self._create_sequence(cr, uid, row['id'], i, n)

        return True

    def _interpolate(self, s, d):
        if s:
            return s % d
        return  ''

    def _interpolation_dict(self):
        t = time.localtime() # Actually, the server is always in UTC.
        return {
            'year': time.strftime('%Y', t),
            'month': time.strftime('%m', t),
            'day': time.strftime('%d', t),
            'y': time.strftime('%y', t),
            'doy': time.strftime('%j', t),
            'woy': time.strftime('%W', t),
            'weekday': time.strftime('%w', t),
            'h24': time.strftime('%H', t),
            'h12': time.strftime('%I', t),
            'min': time.strftime('%M', t),
            'sec': time.strftime('%S', t),
        }

    def _next_do(self, cr, uid, ids, seq_date_id=False, context=None):
        if not ids:
            return False
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        force_company = context.get('force_company')
        if not force_company:
            force_company = self.pool.get('res.users').browse(cr, uid, uid).company_id.id
        sequences = self.read(cr, uid, ids,
                              ['name', 'company_id', 'implementation', 'number_next',
                               'prefix', 'suffix', 'padding', 'number_increment']
                              )
        if seq_date_id:#if we have a seq_date_id it is not possible to have many ids
            assert len(ids) == 1
            seq = sequences[0]
        else:
            preferred_sequences = [s for s in sequences if s['company_id'] and s['company_id'][0] == force_company ]
            seq = preferred_sequences[0] if preferred_sequences else sequences[0]
        if seq['implementation'] == 'standard':
            if seq_date_id:
                assert isinstance(seq_date_id, (int, long))
                sql = "SELECT nextval('ir_sequence_%03d_%03d')" % (seq['id'], seq_date_id)
            else:
                sql = "SELECT nextval('ir_sequence_%03d')" % seq['id']
            cr.execute(sql)
            seq['number_next'] = cr.fetchone()
        else:
            if seq_date_id:
                model_name = 'ir_sequence_date_range'
                model_obj = self.pool.get('ir.sequence.date_range')
                id = seq_date_id
            else:
                model_name = 'ir_sequence'
                model_obj = self
                id = seq['id']
            cr.execute("SELECT number_next FROM %s WHERE id=%s FOR UPDATE NOWAIT" % (model_name, id))
            cr.execute("UPDATE %s SET number_next=number_next+%s WHERE id=%s " % (model_name, seq['number_increment'], id))
            model_obj.invalidate_cache(cr, uid, ['number_next'], [id], context=context)
            seq['number_next'] = model_obj.browse(cr, uid, id).number_next
        d = self._interpolation_dict()
        try:
            interpolated_prefix = self._interpolate(seq['prefix'], d)
            interpolated_suffix = self._interpolate(seq['suffix'], d)
        except ValueError:
            raise osv.except_osv(_('Warning'), _('Invalid prefix or suffix for sequence \'%s\'') % (seq.get('name')))
        return interpolated_prefix + '%%0%sd' % seq['padding'] % seq['number_next'] + interpolated_suffix

    def _create_date_range_seq(self, cr, uid, ids, date, context=None):
        for seq in self.browse(cr, uid, ids, context):
            year = date[0:4]
            date_from = '{}-01-01'.format(year)
            date_to = '{}-12-31'.format(year)
            for line in seq.date_range_ids:
                if line.date_from < date_to and line.date_from > date:
                    date_to = line.date_from
                elif line.date_to > date_from and line.date_to < date:
                    date_from = line.date_to
            vals = {}
            vals['date_from'] = date_from
            vals['date_to'] = date_to
            vals['sequence_main_id'] = seq.id
            seq_date_id = self.pool.get('ir.sequence.date_range').create(cr, uid, vals, context=context)
            if seq.implementation == 'standard':
                self._create_sequence(cr, seq.id, seq.number_increment, seq.number_next, seq_date_id=seq_date_id)
            return seq_date_id

    def _next(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        for seq in self.browse(cr, uid, ids, context):
            if seq.use_date_range:
                dt = context.get('date', openerp.osv.fields.date.today())
                seq_date_id = False
                for line in seq.date_range_ids:
                    if line.date_from < dt and line.date_to > dt:
                        seq_date_id = line.id
                        break
                if not seq_date_id:
                    seq_date_id = self._create_date_range_seq(cr, uid, seq.id, dt, context=context)
                return self._next_do(cr, uid, seq.id, seq_date_id=seq_date_id, context=context)
            else:
                return self._next_do(cr, uid, ids, context=context)

    def next_by_id(self, cr, uid, sequence_id, context=None):
        """ Draw an interpolated string using the specified sequence."""
        self.check_access_rights(cr, uid, 'read')
        company_ids = self.pool.get('res.company').search(cr, uid, [], context=context) + [False]
        ids = self.search(cr, uid, ['&',('id','=', sequence_id),('company_id','in',company_ids)])
        return self._next(cr, uid, ids, context)

    def next_by_code(self, cr, uid, sequence_code, context=None):
        """ Draw an interpolated string using a sequence with the requested code.
            If several sequences with the correct code are available to the user
            (multi-company cases), the one from the user's current company will
            be used.

            :param dict context: context dictionary may contain a
                ``force_company`` key with the ID of the company to
                use instead of the user's current company for the
                sequence selection. A matching sequence for that
                specific company will get higher priority. 
        """
        self.check_access_rights(cr, uid, 'read')
        company_ids = self.pool.get('res.company').search(cr, uid, [], context=context) + [False]
        ids = self.search(cr, uid, ['&', ('code', '=', sequence_code), ('company_id', 'in', company_ids)])
        return self._next(cr, uid, ids, context)

    def get_id(self, cr, uid, sequence_code_or_id, code_or_id='id', context=None):
        """ Draw an interpolated string using the specified sequence.

        The sequence to use is specified by the ``sequence_code_or_id``
        argument, which can be a code or an id (as controlled by the
        ``code_or_id`` argument. This method is deprecated.
        """
        # TODO: bump up to warning after 6.1 release
        _logger.debug("ir_sequence.get() and ir_sequence.get_id() are deprecated. "
            "Please use ir_sequence.next_by_code() or ir_sequence.next_by_id().")
        if code_or_id == 'id':
            return self.next_by_id(cr, uid, sequence_code_or_id, context)
        else:
            return self.next_by_code(cr, uid, sequence_code_or_id, context)

    def get(self, cr, uid, code, context=None):
        """ Draw an interpolated string using the specified sequence.

        The sequence to use is specified by its code. This method is
        deprecated.
        """
        return self.get_id(cr, uid, code, 'code', context)


class ir_sequence_date_range(openerp.osv.osv.osv):
    _name = 'ir.sequence.date_range'
    _rec_name = "sequence_main_id"

    _columns = {
        'date_from': openerp.osv.fields.date('From', required=True),
        'date_to': openerp.osv.fields.date('To', required=True),
        'sequence_main_id': openerp.osv.fields.many2one("ir.sequence", 'Main Sequence',
                                                        required=True, ondelete='cascade'),
        'number_next': openerp.osv.fields.integer('Next Number', required=True, help="Next number of this sequence"),
    }
    _defaults = {
        'number_next': 1,
    }

    def write(self, cr, uid, ids, values, context=None):
        if not isinstance(ids, (list, tuple)):
            ids = [ids]
        rows = self.read(cr, uid, ids, ['sequence_main_id', 'number_next'], context)
        super(ir_sequence_date_range, self).write(cr, uid, ids, values, context)

        for row in rows:
            n = values.get('number_next', row['number_next'])
            if self.pool.get('ir.sequence').browse(cr, uid, row['sequence_main_id'], context=context).implementation == 'standard':
                if row['number_next'] != n:
                    self._alter_sequence(cr, uid, row['sequence_main_id'], number_next=n, seq_date_id=rows['id'])
        return True

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
