# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2009 Tiny SPRL (<http://tiny.be>).
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


"""
    Object Relational Mapping module:
     * Hierarchical structure
     * Constraints consistency and validation
     * Object metadata depends on its status
     * Optimised processing by complex query (multiple actions at once)
     * Default field values
     * Permissions optimisation
     * Persistant object: DB postgresql
     * Data conversion
     * Multi-level caching system
     * Two different inheritance mechanisms
     * Rich set of field types:
          - classical (varchar, integer, boolean, ...)
          - relational (one2many, many2one, many2many)
          - functional

"""

import babel.dates
import calendar
from collections import defaultdict, Iterable
import copy
import datetime
import itertools
import logging
import operator
import pickle
import re
import simplejson
import time

import psycopg2
from lxml import etree

import api
from scope import proxy as scope_proxy
import fields
import openerp
import openerp.tools as tools
from openerp.tools import DEFAULT_SERVER_DATETIME_FORMAT
from openerp.tools.config import config
from openerp.tools.misc import CountingStream
from openerp.tools.safe_eval import safe_eval as eval
from openerp.tools.translate import _
from openerp import SUPERUSER_ID
from query import Query

_logger = logging.getLogger(__name__)
_schema = logging.getLogger(__name__ + '.schema')

# List of etree._Element subclasses that we choose to ignore when parsing XML.
from openerp.tools import SKIPPED_ELEMENT_TYPES

regex_order = re.compile('^(([a-z0-9_]+|"[a-z0-9_]+")( *desc| *asc)?( *, *|))+$', re.I)
regex_object_name = re.compile(r'^[a-z0-9_.]+$')

def transfer_field_to_modifiers(field, modifiers):
    default_values = {}
    state_exceptions = {}
    for attr in ('invisible', 'readonly', 'required'):
        state_exceptions[attr] = []
        default_values[attr] = bool(field.get(attr))
    for state, modifs in (field.get("states",{})).items():
        for modif in modifs:
            if default_values[modif[0]] != modif[1]:
                state_exceptions[modif[0]].append(state)

    for attr, default_value in default_values.items():
        if state_exceptions[attr]:
            modifiers[attr] = [("state", "not in" if default_value else "in", state_exceptions[attr])]
        else:
            modifiers[attr] = default_value


# Don't deal with groups, it is done by check_group().
# Need the context to evaluate the invisible attribute on tree views.
# For non-tree views, the context shouldn't be given.
def transfer_node_to_modifiers(node, modifiers, context=None, in_tree_view=False):
    if node.get('attrs'):
        modifiers.update(eval(node.get('attrs')))

    if node.get('states'):
        if 'invisible' in modifiers and isinstance(modifiers['invisible'], list):
            # TODO combine with AND or OR, use implicit AND for now.
            modifiers['invisible'].append(('state', 'not in', node.get('states').split(',')))
        else:
            modifiers['invisible'] = [('state', 'not in', node.get('states').split(','))]

    for a in ('invisible', 'readonly', 'required'):
        if node.get(a):
            v = bool(eval(node.get(a), {'context': context or {}}))
            if in_tree_view and a == 'invisible':
                # Invisible in a tree view has a specific meaning, make it a
                # new key in the modifiers attribute.
                modifiers['tree_invisible'] = v
            elif v or (a not in modifiers or not isinstance(modifiers[a], list)):
                # Don't set the attribute to False if a dynamic value was
                # provided (i.e. a domain from attrs or states).
                modifiers[a] = v


def simplify_modifiers(modifiers):
    for a in ('invisible', 'readonly', 'required'):
        if a in modifiers and not modifiers[a]:
            del modifiers[a]


def transfer_modifiers_to_node(modifiers, node):
    if modifiers:
        simplify_modifiers(modifiers)
        node.set('modifiers', simplejson.dumps(modifiers))

def setup_modifiers(node, field=None, context=None, in_tree_view=False):
    """ Processes node attributes and field descriptors to generate
    the ``modifiers`` node attribute and set it on the provided node.

    Alters its first argument in-place.

    :param node: ``field`` node from an OpenERP view
    :type node: lxml.etree._Element
    :param dict field: field descriptor corresponding to the provided node
    :param dict context: execution context used to evaluate node attributes
    :param bool in_tree_view: triggers the ``tree_invisible`` code
                              path (separate from ``invisible``): in
                              tree view there are two levels of
                              invisibility, cell content (a column is
                              present but the cell itself is not
                              displayed) with ``invisible`` and column
                              invisibility (the whole column is
                              hidden) with ``tree_invisible``.
    :returns: nothing
    """
    modifiers = {}
    if field is not None:
        transfer_field_to_modifiers(field, modifiers)
    transfer_node_to_modifiers(
        node, modifiers, context=context, in_tree_view=in_tree_view)
    transfer_modifiers_to_node(modifiers, node)

def test_modifiers(what, expected):
    modifiers = {}
    if isinstance(what, basestring):
        node = etree.fromstring(what)
        transfer_node_to_modifiers(node, modifiers)
        simplify_modifiers(modifiers)
        json = simplejson.dumps(modifiers)
        assert json == expected, "%s != %s" % (json, expected)
    elif isinstance(what, dict):
        transfer_field_to_modifiers(what, modifiers)
        simplify_modifiers(modifiers)
        json = simplejson.dumps(modifiers)
        assert json == expected, "%s != %s" % (json, expected)


# To use this test:
# import openerp
# openerp.osv.orm.modifiers_tests()
def modifiers_tests():
    test_modifiers('<field name="a"/>', '{}')
    test_modifiers('<field name="a" invisible="1"/>', '{"invisible": true}')
    test_modifiers('<field name="a" readonly="1"/>', '{"readonly": true}')
    test_modifiers('<field name="a" required="1"/>', '{"required": true}')
    test_modifiers('<field name="a" invisible="0"/>', '{}')
    test_modifiers('<field name="a" readonly="0"/>', '{}')
    test_modifiers('<field name="a" required="0"/>', '{}')
    test_modifiers('<field name="a" invisible="1" required="1"/>', '{"invisible": true, "required": true}') # TODO order is not guaranteed
    test_modifiers('<field name="a" invisible="1" required="0"/>', '{"invisible": true}')
    test_modifiers('<field name="a" invisible="0" required="1"/>', '{"required": true}')
    test_modifiers("""<field name="a" attrs="{'invisible': [('b', '=', 'c')]}"/>""", '{"invisible": [["b", "=", "c"]]}')

    # The dictionary is supposed to be the result of fields_get().
    test_modifiers({}, '{}')
    test_modifiers({"invisible": True}, '{"invisible": true}')
    test_modifiers({"invisible": False}, '{}')


def check_object_name(name):
    """ Check if the given name is a valid openerp object name.

        The _name attribute in osv and osv_memory object is subject to
        some restrictions. This function returns True or False whether
        the given name is allowed or not.

        TODO: this is an approximation. The goal in this approximation
        is to disallow uppercase characters (in some places, we quote
        table/column names and in other not, which leads to this kind
        of errors:

            psycopg2.ProgrammingError: relation "xxx" does not exist).

        The same restriction should apply to both osv and osv_memory
        objects for consistency.

    """
    if regex_object_name.match(name) is None:
        return False
    return True

def raise_on_invalid_object_name(name):
    if not check_object_name(name):
        msg = "The _name attribute %s is not valid." % name
        _logger.error(msg)
        raise except_orm('ValueError', msg)

POSTGRES_CONFDELTYPES = {
    'RESTRICT': 'r',
    'NO ACTION': 'a',
    'CASCADE': 'c',
    'SET NULL': 'n',
    'SET DEFAULT': 'd',
}

def intersect(la, lb):
    return filter(lambda x: x in lb, la)

def same_name(f, g):
    """ Test whether functions `f` and `g` are identical or have the same name """
    return f == g or getattr(f, '__name__', 0) == getattr(g, '__name__', 1)

def fix_import_export_id_paths(fieldname):
    """
    Fixes the id fields in import and exports, and splits field paths
    on '/'.

    :param str fieldname: name of the field to import/export
    :return: split field name
    :rtype: list of str
    """
    fixed_db_id = re.sub(r'([^/])\.id', r'\1/.id', fieldname)
    fixed_external_id = re.sub(r'([^/]):id', r'\1/id', fixed_db_id)
    return fixed_external_id.split('/')

class except_orm(Exception):
    def __init__(self, name, value):
        self.name = name
        self.value = value
        self.args = (name, value)


def pg_varchar(size=0):
    """ Returns the VARCHAR declaration for the provided size:

    * If no size (or an empty or negative size is provided) return an
      'infinite' VARCHAR
    * Otherwise return a VARCHAR(n)

    :type int size: varchar size, optional
    :rtype: str
    """
    if size:
        if not isinstance(size, int):
            raise TypeError("VARCHAR parameter should be an int, got %s"
                            % type(size))
        if size > 0:
            return 'VARCHAR(%d)' % size
    return 'VARCHAR'

FIELDS_TO_PGTYPES = {
    fields.boolean: 'bool',
    fields.integer: 'int4',
    fields.text: 'text',
    fields.html: 'text',
    fields.date: 'date',
    fields.datetime: 'timestamp',
    fields.binary: 'bytea',
    fields.many2one: 'int4',
    fields.serialized: 'text',
}

def get_pg_type(f, type_override=None):
    """
    :param fields._column f: field to get a Postgres type for
    :param type type_override: use the provided type for dispatching instead of the field's own type
    :returns: (postgres_identification_type, postgres_type_specification)
    :rtype: (str, str)
    """
    field_type = type_override or type(f)

    if field_type in FIELDS_TO_PGTYPES:
        pg_type =  (FIELDS_TO_PGTYPES[field_type], FIELDS_TO_PGTYPES[field_type])
    elif issubclass(field_type, fields.float):
        if f.digits:
            pg_type = ('numeric', 'NUMERIC')
        else:
            pg_type = ('float8', 'DOUBLE PRECISION')
    elif issubclass(field_type, (fields.char, fields.reference)):
        pg_type = ('varchar', pg_varchar(f.size))
    elif issubclass(field_type, fields.selection):
        if (isinstance(f.selection, list) and isinstance(f.selection[0][0], int))\
                or getattr(f, 'size', None) == -1:
            pg_type = ('int4', 'INTEGER')
        else:
            pg_type = ('varchar', pg_varchar(getattr(f, 'size', None)))
    elif issubclass(field_type, fields.function):
        if f._type == 'selection':
            pg_type = ('varchar', pg_varchar())
        else:
            pg_type = get_pg_type(f, getattr(fields, f._type))
    else:
        _logger.warning('%s type not supported!', field_type)
        pg_type = None

    return pg_type


class MetaModel(api.Meta):
    """ Metaclass for the models.

    This class is used as the metaclass for the class :class:`BaseModel` to
    discover the models defined in a module (without instanciating them).
    If the automatic discovery is not needed, it is possible to set the model's
    ``_register`` attribute to False.

    """

    module_to_models = {}

    def __init__(self, name, bases, attrs):
        if not self._register:
            self._register = True
            super(MetaModel, self).__init__(name, bases, attrs)
            return

        if not hasattr(self, '_module'):
            # The (OpenERP) module name can be in the `openerp.addons` namespace
            # or not.  For instance, module `sale` can be imported as
            # `openerp.addons.sale` (the right way) or `sale` (for backward
            # compatibility).
            module_parts = self.__module__.split('.')
            if len(module_parts) > 2 and module_parts[:2] == ['openerp', 'addons']:
                module_name = self.__module__.split('.')[2]
            else:
                module_name = self.__module__.split('.')[0]
            self._module = module_name

        # Remember which models to instanciate for this module.
        if not self._custom:
            self.module_to_models.setdefault(self._module, []).append(self)


# special columns automatically created by the ORM
MAGIC_COLUMNS = ['id', 'create_uid', 'create_date', 'write_uid', 'write_date']

class BaseModel(object):
    """ Base class for OpenERP models.

    OpenERP models are created by inheriting from this class' subclasses:

    *   :class:`Model` for regular database-persisted models

    *   :class:`TransientModel` for temporary data, stored in the database but
        automatically vaccuumed every so often

    *   :class:`AbstractModel` for abstract super classes meant to be shared by
        multiple inheriting model

    The system automatically instantiates every model once per database. Those
    instances represent the available models on each database, and depend on
    which modules are installed on that database. The actual class of each
    instance is built from the Python classes that create and inherit from the
    corresponding model.

    Every model instance is a "recordset", i.e., an ordered collection of
    records of the model. Recordsets are returned by methods like
    :meth:`~.browse`, :meth:`~.search`, or field accesses. Records have no
    explicit representation: a record is represented as a recordset of one
    record.

    To create a class that should not be instantiated, the _register class
    attribute may be set to False.
    """
    __metaclass__ = MetaModel
    _auto = True # create database backend
    _register = False # Set to false if the model shouldn't be automatically discovered.
    _name = None
    _columns = {}
    _constraints = []
    _custom = False
    _defaults = {}
    _rec_name = None
    _parent_name = 'parent_id'
    _parent_store = False
    _parent_order = False
    _date_name = 'date'
    _order = 'id'
    _sequence = None
    _description = None
    _needaction = False

    # dict of {field:method}, with method returning the (name_get of records, {id: fold})
    # to include in the _read_group, if grouped on this field
    _group_by_full = {}

    # Transience
    _transient = False # True in a TransientModel

    # structure:
    #  { 'parent_model': 'm2o_field', ... }
    _inherits = {}

    # Mapping from inherits'd field name to triple (m, r, f, n) where m is the
    # model from which it is inherits'd, r is the (local) field towards m, f
    # is the _column object itself, and n is the original (i.e. top-most)
    # parent model.
    # Example:
    #  { 'field_name': ('parent_model', 'm2o_field_to_reach_parent',
    #                   field_column_obj, origina_parent_model), ... }
    _inherit_fields = {}

    # Mapping field name/column_info object
    # This is similar to _inherit_fields but:
    # 1. includes self fields,
    # 2. uses column_info instead of a triple.
    _all_columns = {}

    _table = None
    _log_create = False
    _sql_constraints = []

    CONCURRENCY_CHECK_FIELD = '__last_update'

    def log(self, cr, uid, id, message, secondary=False, context=None):
        return _logger.warning("log() is deprecated. Please use OpenChatter notification system instead of the res.log mechanism.")

    def view_init(self, cr, uid, fields_list, context=None):
        """Override this method to do specific things when a view on the object is opened."""
        pass

    def _field_create(self, cr, context=None):
        """ Create entries in ir_model_fields for all the model's fields.

        If necessary, also create an entry in ir_model, and if called from the
        modules loading scheme (by receiving 'module' in the context), also
        create entries in ir_model_data (for the model and the fields).

        - create an entry in ir_model (if there is not already one),
        - create an entry in ir_model_data (if there is not already one, and if
          'module' is in the context),
        - update ir_model_fields with the fields found in _columns
          (TODO there is some redundancy as _columns is updated from
          ir_model_fields in __init__).

        """
        if context is None:
            context = {}
        cr.execute("SELECT id FROM ir_model WHERE model=%s", (self._name,))
        if not cr.rowcount:
            cr.execute('SELECT nextval(%s)', ('ir_model_id_seq',))
            model_id = cr.fetchone()[0]
            cr.execute("INSERT INTO ir_model (id,model, name, info,state) VALUES (%s, %s, %s, %s, %s)", (model_id, self._name, self._description, self.__doc__, 'base'))
        else:
            model_id = cr.fetchone()[0]
        if 'module' in context:
            name_id = 'model_'+self._name.replace('.', '_')
            cr.execute('select * from ir_model_data where name=%s and module=%s', (name_id, context['module']))
            if not cr.rowcount:
                cr.execute("INSERT INTO ir_model_data (name,date_init,date_update,module,model,res_id) VALUES (%s, (now() at time zone 'UTC'), (now() at time zone 'UTC'), %s, %s, %s)", \
                    (name_id, context['module'], 'ir.model', model_id)
                )

        cr.commit()

        cr.execute("SELECT * FROM ir_model_fields WHERE model=%s", (self._name,))
        cols = {}
        for rec in cr.dictfetchall():
            cols[rec['name']] = rec

        ir_model_fields_obj = self.pool.get('ir.model.fields')

        # sparse field should be created at the end, as it depends on its serialized field already existing
        model_fields = sorted(self._columns.items(), key=lambda x: 1 if x[1]._type == 'sparse' else 0)
        for (k, f) in model_fields:
            vals = {
                'model_id': model_id,
                'model': self._name,
                'name': k,
                'field_description': f.string,
                'ttype': f._type,
                'relation': f._obj or '',
                'select_level': tools.ustr(f.select or 0),
                'readonly': (f.readonly and 1) or 0,
                'required': (f.required and 1) or 0,
                'selectable': (f.selectable and 1) or 0,
                'translate': (f.translate and 1) or 0,
                'relation_field': f._fields_id if isinstance(f, fields.one2many) else '',
                'serialization_field_id': None,
            }
            if getattr(f, 'serialization_field', None):
                # resolve link to serialization_field if specified by name
                serialization_field_id = ir_model_fields_obj.search(cr, SUPERUSER_ID, [('model','=',vals['model']), ('name', '=', f.serialization_field)])
                if not serialization_field_id:
                    raise except_orm(_('Error'), _("Serialization field `%s` not found for sparse field `%s`!") % (f.serialization_field, k))
                vals['serialization_field_id'] = serialization_field_id[0]

            # When its a custom field,it does not contain f.select
            if context.get('field_state', 'base') == 'manual':
                if context.get('field_name', '') == k:
                    vals['select_level'] = context.get('select', '0')
                #setting value to let the problem NOT occur next time
                elif k in cols:
                    vals['select_level'] = cols[k]['select_level']

            if k not in cols:
                cr.execute('select nextval(%s)', ('ir_model_fields_id_seq',))
                id = cr.fetchone()[0]
                vals['id'] = id
                cr.execute("""INSERT INTO ir_model_fields (
                    id, model_id, model, name, field_description, ttype,
                    relation,state,select_level,relation_field, translate, serialization_field_id
                ) VALUES (
                    %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s
                )""", (
                    id, vals['model_id'], vals['model'], vals['name'], vals['field_description'], vals['ttype'],
                     vals['relation'], 'base',
                    vals['select_level'], vals['relation_field'], bool(vals['translate']), vals['serialization_field_id']
                ))
                if 'module' in context:
                    name1 = 'field_' + self._table + '_' + k
                    cr.execute("select name from ir_model_data where name=%s", (name1,))
                    if cr.fetchone():
                        name1 = name1 + "_" + str(id)
                    cr.execute("INSERT INTO ir_model_data (name,date_init,date_update,module,model,res_id) VALUES (%s, (now() at time zone 'UTC'), (now() at time zone 'UTC'), %s, %s, %s)", \
                        (name1, context['module'], 'ir.model.fields', id)
                    )
            else:
                for key, val in vals.items():
                    if cols[k][key] != vals[key]:
                        cr.execute('update ir_model_fields set field_description=%s where model=%s and name=%s', (vals['field_description'], vals['model'], vals['name']))
                        cr.commit()
                        cr.execute("""UPDATE ir_model_fields SET
                            model_id=%s, field_description=%s, ttype=%s, relation=%s,
                            select_level=%s, readonly=%s ,required=%s, selectable=%s, relation_field=%s, translate=%s, serialization_field_id=%s
                        WHERE
                            model=%s AND name=%s""", (
                                vals['model_id'], vals['field_description'], vals['ttype'],
                                vals['relation'],
                                vals['select_level'], bool(vals['readonly']), bool(vals['required']), bool(vals['selectable']), vals['relation_field'], bool(vals['translate']), vals['serialization_field_id'], vals['model'], vals['name']
                            ))
                        break
        self.invalidate_cache()
        cr.commit()

    @classmethod
    def _set_field_descriptor(cls, name, field):
        """ Add the given `field` under the given `name` in the class """
        field.set_model_name(cls._name, name)

        # add field in _fields (for reflection)
        cls._fields[name] = field

        # add field as an attribute, unless another kind of value already exists
        if isinstance(getattr(cls, name, field), Field):
            setattr(cls, name, field)
        else:
            _logger.warning("In model %r, member %r is not a field", cls._name, name)

        if field.store and not field.interface:
            _logger.debug("Create column for field %s.%s", cls._name, name)
            cls._columns[name] = field.to_column()

    @classmethod
    def _set_magic_fields(cls):
        """ Introduce magic fields on the current class

        * id is a "normal" field (with a specific getter)
        * create_uid, create_date, write_uid and write_date have become
          "normal" fields
        * $CONCURRENCY_CHECK_FIELD is a computed field with its computing
          method defined dynamically. Uses ``str(datetime.datetime.utcnow())``
          to get the same structure as the previous
          ``(now() at time zone 'UTC')::timestamp``::

              # select (now() at time zone 'UTC')::timestamp;
                        timezone
              ----------------------------
               2013-06-18 08:30:37.292809

              >>> str(datetime.datetime.utcnow())
              '2013-06-18 08:31:32.821177'
        """
        if 'id' not in cls._columns and not hasattr(cls, 'id'):
            cls._set_field_descriptor('id', fields2.Id())

        log_access = getattr(cls, '_log_access', getattr(cls, '_auto', True))
        compute_concurrency_field = "compute_concurrency_field"

        if log_access:
            # FIXME: what if these fields are already defined on the class?
            cls._set_field_descriptor(
                'create_uid', fields2.Many2one('res.users', ondelete='set null'))
            cls._set_field_descriptor('create_date', fields2.Datetime())

            cls._set_field_descriptor(
                'write_uid', fields2.Many2one('res.users', ondelete='set null'))
            cls._set_field_descriptor('write_date', fields2.Datetime())

            compute_concurrency_field = 'compute_concurrency_field_with_access'

        cls._set_field_descriptor(
            cls.CONCURRENCY_CHECK_FIELD,
            fields2.Datetime(compute=compute_concurrency_field, store=False))

    @api.one
    def compute_concurrency_field(self):
        self[self.CONCURRENCY_CHECK_FIELD] = \
            datetime.datetime.utcnow().strftime(DEFAULT_SERVER_DATETIME_FORMAT)

    @api.one
    @api.depends('create_date', 'write_date')
    def compute_concurrency_field_with_access(self):
        self[self.CONCURRENCY_CHECK_FIELD] = \
            self.write_date or self.create_date or \
            datetime.datetime.utcnow().strftime(DEFAULT_SERVER_DATETIME_FORMAT)

    #
    # Goal: try to apply inheritance at the instanciation level and
    #       put objects in the pool var
    #
    @classmethod
    def create_instance(cls, pool, cr):
        """ Instanciate a given model.

        This class method instanciates the class of some model (i.e. a class
        deriving from osv or osv_memory). The class might be the class passed
        in argument or, if it inherits from another class, a class constructed
        by combining the two classes.

        """

        # IMPORTANT: the registry contains an instance for each model. The class
        # of each model carries inferred metadata that is shared among the
        # model's instances for this registry, but not among registries. Hence
        # we cannot use that "registry class" for combining model classes by
        # inheritance, since it confuses the metadata inference process.

        parent_names = getattr(cls, '_inherit', None)
        if parent_names:
            parent_names = parent_names if isinstance(parent_names, list) else [parent_names]
            name = cls._name or (len(parent_names) == 1 and parent_names[0]) or cls.__name__

            for parent_name in parent_names:
                if parent_name not in pool:
                    raise TypeError('The model "%s" specifies an unexisting parent class "%s"\n'
                        'You may need to add a dependency on the parent class\' module.' % (name, parent_name))
                parent_model = pool[parent_name]
                if not getattr(cls, '_original_module', None) and name == parent_model._name:
                    cls._original_module = parent_model._original_module

                # do no use the class of parent_model, since that class contains
                # inferred metadata; use its ancestor instead
                parent_class = type(parent_model).__bases__[0]

                # don't inherit custom fields, and duplicate inherited fields
                # because some have a per-registry cache (like float)
                columns = dict(
                    (key, copy.copy(val))
                    for key, val in getattr(parent_class, '_columns', {}).iteritems()
                    if not val.manual)
                columns.update(getattr(cls, '_columns', {}))

                defaults = dict(getattr(parent_class, '_defaults', {}))
                defaults.update(getattr(cls, '_defaults', {}))

                inherits = dict(getattr(parent_class, '_inherits', {}))
                inherits.update(getattr(cls, '_inherits', {}))

                old_constraints = getattr(parent_class, '_constraints', [])
                new_constraints = getattr(cls, '_constraints', [])
                # filter out from old_constraints the ones overridden by a
                # constraint with the same function name in new_constraints
                constraints = new_constraints + [oldc
                    for oldc in old_constraints
                    if not any(newc[2] == oldc[2] and same_name(newc[0], oldc[0])
                               for newc in new_constraints)
                ]

                sql_constraints = getattr(cls, '_sql_constraints', []) + \
                    getattr(parent_class, '_sql_constraints', [])

                attrs = {
                    '_name': name,
                    '_register': False,
                    '_columns': columns,
                    '_defaults': defaults,
                    '_inherits': inherits,
                    '_constraints': constraints,
                    '_sql_constraints': sql_constraints,
                    # Keep links to non-inherited constraints; this is useful
                    # for instance when exporting translations
                    '_local_constraints': cls.__dict__.get('_constraints', []),
                    '_local_sql_constraints': cls.__dict__.get('_sql_constraints', []),
                }
                cls = type(name, (cls, parent_class), attrs)
        else:
            if not cls._name:
                cls._name = cls.__name__
            cls._local_constraints = cls.__dict__.get('_constraints', [])
            cls._local_sql_constraints = cls.__dict__.get('_sql_constraints', [])

        # introduce the "registry class" of the model;
        # duplicate some attributes so that the ORM can modify them
        attrs = {
            '_register': False,
            '_columns': dict(cls._columns),
            '_defaults': dict(cls._defaults),
            '_inherits': dict(cls._inherits),
            '_constraints': list(cls._constraints),
            '_sql_constraints': list(cls._sql_constraints),
        }
        cls = type(cls._name, (cls,), attrs)

        # duplicate all new-style fields to avoid clashes with inheritance
        cls._fields = {}
        for attr in dir(cls):
            value = getattr(cls, attr)
            if isinstance(value, Field):
                cls._set_field_descriptor(attr, value.copy())

        # introduce magic fields
        cls._set_magic_fields()

        if not getattr(cls, '_original_module', None):
            cls._original_module = cls._module

        instance = cls.browse()
        instance.__init__(pool, cr)
        return instance

    def __new__(cls):
        # In the past, this method was registering the model class in the server.
        # This job is now done entirely by the metaclass MetaModel.
        #
        # Do not create an instance here.  Model instances are created by method
        # create_instance().
        return None

    def __init__(self, pool, cr):
        """ Initialize a model and make it part of the given registry.

        - copy the stored fields' functions in the osv_pool,
        - update the _columns with the fields found in ir_model_fields,
        - ensure there is a many2one for each _inherits'd parent,
        - update the children's _columns,
        - give a chance to each field to initialize itself.

        """
        # all the important stuff is stored directly on the model's class
        cls = type(self)

        # insert self in the pool
        pool.add(cls._name, self)
        cls.pool = pool

        # determine description, table and log_access
        if not cls._description:
            cls._description = cls.__doc__ or cls._name
        if not cls._table:
            cls._table = cls._name.replace('.', '_')
        if not hasattr(cls, '_log_access'):
            # If _log_access is not specified, it is the same value as _auto.
            cls._log_access = getattr(cls, "_auto", True)

        # reinitialize the list of non-stored function fields for this model
        pool._pure_function_fields[cls._name] = []

        # process store of low-level function fields
        for fname, column in cls._columns.iteritems():
            if hasattr(column, 'digits_change'):
                column.digits_change(cr)
            # filter out existing store about this field
            pool._store_function[cls._name] = [
                stored
                for stored in pool._store_function.get(cls._name, [])
                if (stored[0], stored[1]) != (cls._name, fname)
            ]
            if not isinstance(column, fields.function):
                continue
            if not column.store:
                # register it on the pool for invalidation
                pool._pure_function_fields[cls._name].append(fname)
                continue
            # process store parameter
            store = column.store
            if store is True:
                store = {cls._name: (lambda self, cr, uid, ids, c={}: ids, None, 10, None)}
            for model, spec in store.iteritems():
                if len(spec) == 4:
                    (fnct, fields2, order, length) = spec
                elif len(spec) == 3:
                    (fnct, fields2, order) = spec
                    length = None
                else:
                    raise except_orm('Error',
                        ('Invalid function definition %s in object %s !\nYou must use the definition: store={object:(fnct, fields, priority, time length)}.' % (fname, cls._name)))
                pool._store_function.setdefault(model, [])
                pool._store_function[model].append(
                    (cls._name, fname, fnct, tuple(fields2) if fields2 else None, order, length))
                pool._store_function[model].sort(key=lambda x: x[4])

        # store sql constraint error messages
        for (key, _, msg) in cls._sql_constraints:
            pool._sql_error[cls._table + '_' + key] = msg

        # collect constraint methods
        cls._constraint_methods = []
        for attr in dir(cls):
            value = getattr(cls, attr)
            if callable(value) and hasattr(value, '_constrains'):
                cls._constraint_methods.append(value)

        # Load manual fields

        # Check the query is already done for all modules of if we need to
        # do it ourselves.
        if pool.fields_by_model is not None:
            manual_fields = pool.fields_by_model.get(cls._name, [])
        else:
            cr.execute('SELECT * FROM ir_model_fields WHERE model=%s AND state=%s', (cls._name, 'manual'))
            manual_fields = cr.dictfetchall()
        for field in manual_fields:
            if field['name'] in cls._columns:
                continue
            attrs = {
                'string': field['field_description'],
                'required': bool(field['required']),
                'readonly': bool(field['readonly']),
                'domain': eval(field['domain']) if field['domain'] else None,
                'size': field['size'] or None,
                'ondelete': field['on_delete'],
                'translate': (field['translate']),
                'manual': True,
                '_prefetch': False,
                #'select': int(field['select_level'])
            }
            if field['serialization_field_id']:
                cr.execute('SELECT name FROM ir_model_fields WHERE id=%s', (field['serialization_field_id'],))
                attrs.update({'serialization_field': cr.fetchone()[0], 'type': field['ttype']})
                if field['ttype'] in ['many2one', 'one2many', 'many2many']:
                    attrs.update({'relation': field['relation']})
                cls._columns[field['name']] = fields.sparse(**attrs)
            elif field['ttype'] == 'selection':
                cls._columns[field['name']] = fields.selection(eval(field['selection']), **attrs)
            elif field['ttype'] == 'reference':
                cls._columns[field['name']] = fields.reference(selection=eval(field['selection']), **attrs)
            elif field['ttype'] == 'many2one':
                cls._columns[field['name']] = fields.many2one(field['relation'], **attrs)
            elif field['ttype'] == 'one2many':
                cls._columns[field['name']] = fields.one2many(field['relation'], field['relation_field'], **attrs)
            elif field['ttype'] == 'many2many':
                _rel1 = field['relation'].replace('.', '_')
                _rel2 = field['model'].replace('.', '_')
                _rel_name = 'x_%s_%s_%s_rel' % (_rel1, _rel2, field['name'])
                cls._columns[field['name']] = fields.many2many(field['relation'], _rel_name, 'id1', 'id2', **attrs)
            else:
                cls._columns[field['name']] = getattr(fields, field['ttype'])(**attrs)

        self._inherits_check()
        self._inherits_reload()

        if not cls._sequence:
            cls._sequence = cls._table + '_id_seq'
        for k in cls._defaults:
            assert (k in cls._columns) or (k in cls._inherit_fields), \
                'Default function defined in %s but field %s does not exist !' % (cls._name, k,)

        # restart columns
        for column in cls._columns.itervalues():
            column.restart()

        # Transience
        if self.is_transient():
            cls._transient_check_count = 0
            cls._transient_max_count = config.get('osv_memory_count_limit')
            cls._transient_max_hours = config.get('osv_memory_age_limit')
            assert cls._log_access, "TransientModels must have log_access turned on, "\
                                     "in order to implement their access rights policy"

        # Validate rec_name
        if cls._rec_name:
            assert cls._rec_name in cls._fields, \
                "Invalid rec_name %s for model %s" % (cls._rec_name, cls._name)
        elif 'name' in cls._fields:
            cls._rec_name = 'name'

        # prepare ormcache, which must be shared by all instances of the model
        cls._ormcache = {}

    def __export_xml_id(self):
        """ Return a valid xml_id for the record `self`. """
        ir_model_data = self.pool['ir.model.data']
        with scope_proxy.SUDO():
            data = ir_model_data.search([('model', '=', self._name), ('res_id', '=', self.id)])
            if data:
                if data.module:
                    return '%s.%s' % (data.module, data.name)
                else:
                    return data.name
            else:
                postfix = 0
                name = '%s_%s' % (self._table, self.id)
                while ir_model_data.search([('module', '=', '__export__'), ('name', '=', name)]):
                    postfix += 1
                    name = '%s_%s_%s' % (self._table, self.id, postfix)
                ir_model_data.create({
                    'model': self._name,
                    'res_id': self.id,
                    'module': '__export__',
                    'name': name,
                })
                return '__export__.' + name

    @api.multi
    def __export_rows(self, fields):
        """ Export fields of the records in `self`.

            :param fields: list of lists of fields to traverse
            :return: list of lists of corresponding values
        """
        lines = []
        for record in self:
            # main line of record, initially empty
            current = [''] * len(fields)
            lines.append(current)

            # list of primary fields followed by secondary field(s)
            primary_done = []

            # process column by column
            for i, path in enumerate(fields):
                if not path:
                    continue

                name = path[0]
                if name in primary_done:
                    continue

                if name == '.id':
                    current[i] = str(record.id)
                elif name == 'id':
                    current[i] = record.__export_xml_id()
                else:
                    field = record._fields[name]
                    value = record[name]

                    # this part could be simpler, but it has to be done this way
                    # in order to reproduce the former behavior
                    if not isinstance(value, BaseModel):
                        current[i] = field.convert_to_export(value)
                    else:
                        primary_done.append(name)

                        # This is a special case, its strange behavior is intended!
                        if field.type == 'many2many' and len(path) > 1 and path[1] == 'id':
                            xml_ids = [r.__export_xml_id() for r in value]
                            current[i] = ','.join(xml_ids) or False
                            continue

                        # recursively export the fields that follow name
                        fields2 = [(p[1:] if p and p[0] == name else []) for p in fields]
                        lines2 = value.__export_rows(fields2)
                        if lines2:
                            # merge first line with record's main line
                            for j, val in enumerate(lines2[0]):
                                if val:
                                    current[j] = val
                            # check value of current field
                            if not current[i]:
                                # assign xml_ids, and forget about remaining lines
                                xml_ids = [item[1] for item in value.name_get()]
                                current[i] = ','.join(xml_ids)
                            else:
                                # append the other lines at the end
                                lines += lines2[1:]
                        else:
                            current[i] = False

        return lines

    @api.multi
    def export_data(self, fields_to_export):
        """ Export fields for selected objects

            :param fields_to_export: list of fields
            :rtype: dictionary with a *datas* matrix

            This method is used when exporting data via client menu
        """
        fields_to_export = map(fix_import_export_id_paths, fields_to_export)
        return {'datas': self.__export_rows(fields_to_export)}

    def import_data(self, cr, uid, fields, datas, mode='init', current_module='', noupdate=False, context=None, filename=None):
        """
        .. deprecated:: 7.0
            Use :meth:`~load` instead

        Import given data in given module

        This method is used when importing data via client menu.

        Example of fields to import for a sale.order::

            .id,                         (=database_id)
            partner_id,                  (=name_search)
            order_line/.id,              (=database_id)
            order_line/name,
            order_line/product_id/id,    (=xml id)
            order_line/price_unit,
            order_line/product_uom_qty,
            order_line/product_uom/id    (=xml_id)

        This method returns a 4-tuple with the following structure::

            (return_code, errored_resource, error_message, unused)

        * The first item is a return code, it is ``-1`` in case of
          import error, or the last imported row number in case of success
        * The second item contains the record data dict that failed to import
          in case of error, otherwise it's 0
        * The third item contains an error message string in case of error,
          otherwise it's 0
        * The last item is currently unused, with no specific semantics

        :param fields: list of fields to import
        :param datas: data to import
        :param mode: 'init' or 'update' for record creation
        :param current_module: module name
        :param noupdate: flag for record creation
        :param filename: optional file to store partial import state for recovery
        :returns: 4-tuple in the form (return_code, errored_resource, error_message, unused)
        :rtype: (int, dict or 0, str or 0, str or 0)
        """
        context = dict(context) if context is not None else {}
        context['_import_current_module'] = current_module

        fields = map(fix_import_export_id_paths, fields)
        ir_model_data_obj = self.pool.get('ir.model.data')

        def log(m):
            if m['type'] == 'error':
                raise Exception(m['message'])

        if config.get('import_partial') and filename:
            with open(config.get('import_partial'), 'rb') as partial_import_file:
                data = pickle.load(partial_import_file)
                position = data.get(filename, 0)

        position = 0
        try:
            for res_id, xml_id, res, info in self._convert_records(cr, uid,
                            self._extract_records(cr, uid, fields, datas,
                                                  context=context, log=log),
                            context=context, log=log):
                ir_model_data_obj._update(cr, uid, self._name,
                     current_module, res, mode=mode, xml_id=xml_id,
                     noupdate=noupdate, res_id=res_id, context=context)
                position = info.get('rows', {}).get('to', 0) + 1
                if config.get('import_partial') and filename and (not (position%100)):
                    with open(config.get('import_partial'), 'rb') as partial_import:
                        data = pickle.load(partial_import)
                    data[filename] = position
                    with open(config.get('import_partial'), 'wb') as partial_import:
                        pickle.dump(data, partial_import)
                    if context.get('defer_parent_store_computation'):
                        self._parent_store_compute(cr)
                    cr.commit()
        except Exception, e:
            cr.rollback()
            return -1, {}, 'Line %d : %s' % (position + 1, tools.ustr(e)), ''

        if context.get('defer_parent_store_computation'):
            self._parent_store_compute(cr)
        return position, 0, 0, 0

    def load(self, cr, uid, fields, data, context=None):
        """
        Attempts to load the data matrix, and returns a list of ids (or
        ``False`` if there was an error and no id could be generated) and a
        list of messages.

        The ids are those of the records created and saved (in database), in
        the same order they were extracted from the file. They can be passed
        directly to :meth:`~read`

        :param fields: list of fields to import, at the same index as the corresponding data
        :type fields: list(str)
        :param data: row-major matrix of data to import
        :type data: list(list(str))
        :param dict context:
        :returns: {ids: list(int)|False, messages: [Message]}
        """
        cr.execute('SAVEPOINT model_load')
        messages = []

        fields = map(fix_import_export_id_paths, fields)
        ModelData = self.pool['ir.model.data'].clear_caches()

        fg = self.fields_get(cr, uid, context=context)

        mode = 'init'
        current_module = ''
        noupdate = False

        ids = []
        for id, xid, record, info in self._convert_records(cr, uid,
                self._extract_records(cr, uid, fields, data,
                                      context=context, log=messages.append),
                context=context, log=messages.append):
            try:
                cr.execute('SAVEPOINT model_load_save')
            except psycopg2.InternalError, e:
                # broken transaction, exit and hope the source error was
                # already logged
                if not any(message['type'] == 'error' for message in messages):
                    messages.append(dict(info, type='error',message=
                        u"Unknown database error: '%s'" % e))
                break
            try:
                ids.append(ModelData._update(cr, uid, self._name,
                     current_module, record, mode=mode, xml_id=xid,
                     noupdate=noupdate, res_id=id, context=context))
                cr.execute('RELEASE SAVEPOINT model_load_save')
            except psycopg2.Warning, e:
                messages.append(dict(info, type='warning', message=str(e)))
                cr.execute('ROLLBACK TO SAVEPOINT model_load_save')
            except psycopg2.Error, e:
                messages.append(dict(
                    info, type='error',
                    **PGERROR_TO_OE[e.pgcode](self, fg, info, e)))
                # Failed to write, log to messages, rollback savepoint (to
                # avoid broken transaction) and keep going
                cr.execute('ROLLBACK TO SAVEPOINT model_load_save')
        if any(message['type'] == 'error' for message in messages):
            cr.execute('ROLLBACK TO SAVEPOINT model_load')
            ids = False
        return {'ids': ids, 'messages': messages}
    def _extract_records(self, cr, uid, fields_, data,
                         context=None, log=lambda a: None):
        """ Generates record dicts from the data sequence.

        The result is a generator of dicts mapping field names to raw
        (unconverted, unvalidated) values.

        For relational fields, if sub-fields were provided the value will be
        a list of sub-records

        The following sub-fields may be set on the record (by key):
        * None is the name_get for the record (to use with name_create/name_search)
        * "id" is the External ID for the record
        * ".id" is the Database ID for the record
        """
        columns = dict((k, v.column) for k, v in self._all_columns.iteritems())
        # Fake columns to avoid special cases in extractor
        columns[None] = fields.char('rec_name')
        columns['id'] = fields.char('External ID')
        columns['.id'] = fields.integer('Database ID')

        # m2o fields can't be on multiple lines so exclude them from the
        # is_relational field rows filter, but special-case it later on to
        # be handled with relational fields (as it can have subfields)
        is_relational = lambda field: columns[field]._type in ('one2many', 'many2many', 'many2one')
        get_o2m_values = itemgetter_tuple(
            [index for index, field in enumerate(fields_)
                  if columns[field[0]]._type == 'one2many'])
        get_nono2m_values = itemgetter_tuple(
            [index for index, field in enumerate(fields_)
                  if columns[field[0]]._type != 'one2many'])
        # Checks if the provided row has any non-empty non-relational field
        def only_o2m_values(row, f=get_nono2m_values, g=get_o2m_values):
            return any(g(row)) and not any(f(row))

        index = 0
        while True:
            if index >= len(data): return

            row = data[index]
            # copy non-relational fields to record dict
            record = dict((field[0], value)
                for field, value in itertools.izip(fields_, row)
                if not is_relational(field[0]))

            # Get all following rows which have relational values attached to
            # the current record (no non-relational values)
            record_span = itertools.takewhile(
                only_o2m_values, itertools.islice(data, index + 1, None))
            # stitch record row back on for relational fields
            record_span = list(itertools.chain([row], record_span))
            for relfield in set(
                    field[0] for field in fields_
                             if is_relational(field[0])):
                column = columns[relfield]
                # FIXME: how to not use _obj without relying on fields_get?
                Model = self.pool[column._obj]

                # get only cells for this sub-field, should be strictly
                # non-empty, field path [None] is for name_get column
                indices, subfields = zip(*((index, field[1:] or [None])
                                           for index, field in enumerate(fields_)
                                           if field[0] == relfield))

                # return all rows which have at least one value for the
                # subfields of relfield
                relfield_data = filter(any, map(itemgetter_tuple(indices), record_span))
                record[relfield] = [subrecord
                    for subrecord, _subinfo in Model._extract_records(
                        cr, uid, subfields, relfield_data,
                        context=context, log=log)]

            yield record, {'rows': {
                'from': index,
                'to': index + len(record_span) - 1
            }}
            index += len(record_span)
    def _convert_records(self, cr, uid, records,
                         context=None, log=lambda a: None):
        """ Converts records from the source iterable (recursive dicts of
        strings) into forms which can be written to the database (via
        self.create or (ir.model.data)._update)

        :returns: a list of triplets of (id, xid, record)
        :rtype: list((int|None, str|None, dict))
        """
        if context is None: context = {}
        Converter = self.pool['ir.fields.converter']
        columns = dict((k, v.column) for k, v in self._all_columns.iteritems())
        Translation = self.pool['ir.translation']
        field_names = dict(
            (f, (Translation._get_source(cr, uid, self._name + ',' + f, 'field',
                                         context.get('lang'))
                 or column.string))
            for f, column in columns.iteritems())

        convert = Converter.for_model(cr, uid, self, context=context)

        def _log(base, field, exception):
            type = 'warning' if isinstance(exception, Warning) else 'error'
            # logs the logical (not human-readable) field name for automated
            # processing of response, but injects human readable in message
            record = dict(base, type=type, field=field,
                          message=unicode(exception.args[0]) % base)
            if len(exception.args) > 1 and exception.args[1]:
                record.update(exception.args[1])
            log(record)

        stream = CountingStream(records)
        for record, extras in stream:
            dbid = False
            xid = False
            # name_get/name_create
            if None in record: pass
            # xid
            if 'id' in record:
                xid = record['id']
            # dbid
            if '.id' in record:
                try:
                    dbid = int(record['.id'])
                except ValueError:
                    # in case of overridden id column
                    dbid = record['.id']
                if not self.search(cr, uid, [('id', '=', dbid)], context=context):
                    log(dict(extras,
                        type='error',
                        record=stream.index,
                        field='.id',
                        message=_(u"Unknown database identifier '%s'") % dbid))
                    dbid = False

            converted = convert(record, lambda field, err:\
                _log(dict(extras, record=stream.index, field=field_names[field]), field, err))

            yield dbid, xid, converted, dict(extras, record=stream.index)

    @api.multi
    def _validate_fields(self, field_names):
        field_names = set(field_names)

        # old-style constraint methods
        trans = scope_proxy.model('ir.translation')
        cr, uid, context = scope_proxy.args
        lang = scope_proxy.lang
        ids = self.unbrowse()
        errors = []
        for fun, msg, names in self._constraints:
            # validation must be context-independent; call `fun` without context
            if set(names) & field_names and not fun(self, cr, uid, ids):
                if callable(msg):
                    res_msg = msg(self, cr, uid, ids, context=context)
                    if isinstance(res_msg, tuple):
                        template, params = res_msg
                        res_msg = template % params
                else:
                    res_msg = trans._get_source(self._name, 'constraint', lang, msg)
                errors.append(
                    _("Field(s) `%s` failed against a constraint: %s") %
                        (', '.join(names), res_msg)
                )
        if errors:
            raise except_orm('ValidateError', '\n'.join(errors))

        # new-style constraint methods
        for check in self._constraint_methods:
            if set(check._constrains) & field_names:
                check(self)

    def default_get(self, cr, uid, fields_list, context=None):
        """ Return default values for the fields in `fields_list`. Default
            values are determined by the context, user defaults, and the model
            itself.

            :param fields_list: a list of field names
            :return: a dictionary mapping each field name to its corresponding
                default value; the keys of the dictionary are the fields in
                `fields_list` that have a default value different from ``False``.

            This method should not be overridden. In order to change the
            mechanism for determining default values, you should override method
            :meth:`add_default_value` instead.
        """
        # trigger view init hook
        self.view_init(cr, uid, fields_list, context)

        # use a new record to determine default values
        record = self.new()
        for name in fields_list:
            record[name]                # force evaluation of defaults

        # retrieve defaults from record's values
        return self._convert_to_write(record.get_draft_values())

    def add_default_value(self, name):
        """ Set the default value of field `name` to the new record `self`.
            The value must be assigned to `self` as ``self.field = value`` or
            ``self[name] = value``.
        """
        assert not self._id, "Expected new record: %s" % self
        cr, uid, context = scope_proxy.args
        field = self._fields[name]

        # 1. look up context
        key = 'default_' + name
        if key in context:
            self[name] = context[key]
            return

        # 2. look up ir_values
        #    Note: performance is good, because get_defaults_dict is cached!
        ir_values_dict = self.pool['ir.values'].get_defaults_dict(self._name)
        if name in ir_values_dict:
            self[name] = ir_values_dict[name]
            return

        # 3. look up property fields
        #    TODO: get rid of this one
        column = self._columns.get(name)
        if isinstance(column, fields.property):
            self[name] = self.pool['ir.property'].get(name, self._name)
            return

        # 4. look up _defaults
        if name in self._defaults:
            value = self._defaults[name]
            if callable(value):
                value = value(self, cr, uid, context)
            self[name] = value
            return

        # 5. delegate to field
        field.determine_default(self)

    def fields_get_keys(self, cr, user, context=None):
        res = self._columns.keys()
        # TODO I believe this loop can be replace by
        # res.extend(self._inherit_fields.key())
        for parent in self._inherits:
            res.extend(self.pool[parent].fields_get_keys(cr, user, context))
        return res

    def _rec_name_fallback(self, cr, uid, context=None):
        rec_name = self._rec_name
        if rec_name not in self._columns:
            rec_name = self._columns.keys()[0] if len(self._columns.keys()) > 0 else "id"
        return rec_name

    #
    # Overload this method if you need a window title which depends on the context
    #
    def view_header_get(self, cr, user, view_id=None, view_type='form', context=None):
        return False

    def user_has_groups(self, cr, uid, groups, context=None):
        """Return true if the user is at least member of one of the groups
           in groups_str. Typically used to resolve `groups` attribute
           in view and model definitions.

           :param str groups: comma-separated list of fully-qualified group
                              external IDs, e.g.: ``base.group_user,base.group_system``
           :return: True if the current user is a member of one of the
                    given groups
        """
        return any([self.pool.get('res.users').has_group(cr, uid, group_ext_id)
                        for group_ext_id in groups.split(',')])

    def __view_look_dom(self, cr, user, node, view_id, in_tree_view, model_fields, context=None):
        """Return the description of the fields in the node.

        In a normal call to this method, node is a complete view architecture
        but it is actually possible to give some sub-node (this is used so
        that the method can call itself recursively).

        Originally, the field descriptions are drawn from the node itself.
        But there is now some code calling fields_get() in order to merge some
        of those information in the architecture.

        """
        if context is None:
            context = {}
        result = False
        fields = {}
        children = True

        modifiers = {}

        def encode(s):
            if isinstance(s, unicode):
                return s.encode('utf8')
            return s

        def check_group(node):
            """Apply group restrictions,  may be set at view level or model level::
               * at view level this means the element should be made invisible to
                 people who are not members
               * at model level (exclusively for fields, obviously), this means
                 the field should be completely removed from the view, as it is
                 completely unavailable for non-members

               :return: True if field should be included in the result of fields_view_get
            """
            if node.tag == 'field' and node.get('name') in self._all_columns:
                column = self._all_columns[node.get('name')].column
                if column.groups and not self.user_has_groups(cr, user,
                                                              groups=column.groups,
                                                              context=context):
                    node.getparent().remove(node)
                    fields.pop(node.get('name'), None)
                    # no point processing view-level ``groups`` anymore, return
                    return False
            if node.get('groups'):
                can_see = self.user_has_groups(cr, user,
                                               groups=node.get('groups'),
                                               context=context)
                if not can_see:
                    node.set('invisible', '1')
                    modifiers['invisible'] = True
                    if 'attrs' in node.attrib:
                        del(node.attrib['attrs']) #avoid making field visible later
                del(node.attrib['groups'])
            return True

        if node.tag in ('field', 'node', 'arrow'):
            if node.get('object'):
                attrs = {}
                views = {}
                xml = "<form>"
                for f in node:
                    if f.tag == 'field':
                        xml += etree.tostring(f, encoding="utf-8")
                xml += "</form>"
                new_xml = etree.fromstring(encode(xml))
                ctx = context.copy()
                ctx['base_model_name'] = self._name
                xarch, xfields = self.pool[node.get('object')].__view_look_dom_arch(cr, user, new_xml, view_id, ctx)
                views['form'] = {
                    'arch': xarch,
                    'fields': xfields
                }
                attrs = {'views': views}
                fields = xfields
            if node.get('name'):
                attrs = {}
                try:
                    if node.get('name') in self._columns:
                        column = self._columns[node.get('name')]
                    else:
                        column = self._inherit_fields[node.get('name')][2]
                except Exception:
                    column = False

                if column:
                    relation = self.pool[column._obj] if column._obj else None

                    children = False
                    views = {}
                    for f in node:
                        if f.tag in ('form', 'tree', 'graph', 'kanban'):
                            node.remove(f)
                            ctx = context.copy()
                            ctx['base_model_name'] = self._name
                            xarch, xfields = relation.__view_look_dom_arch(cr, user, f, view_id, ctx)
                            views[str(f.tag)] = {
                                'arch': xarch,
                                'fields': xfields
                            }
                    attrs = {'views': views}
                    if node.get('widget') and node.get('widget') == 'selection':
                        # Prepare the cached selection list for the client. This needs to be
                        # done even when the field is invisible to the current user, because
                        # other events could need to change its value to any of the selectable ones
                        # (such as on_change events, refreshes, etc.)

                        # If domain and context are strings, we keep them for client-side, otherwise
                        # we evaluate them server-side to consider them when generating the list of
                        # possible values
                        # TODO: find a way to remove this hack, by allow dynamic domains
                        dom = []
                        if column._domain and not isinstance(column._domain, basestring):
                            dom = list(column._domain)
                        dom += eval(node.get('domain', '[]'), {'uid': user, 'time': time})
                        search_context = dict(context)
                        if column._context and not isinstance(column._context, basestring):
                            search_context.update(column._context)
                        attrs['selection'] = relation._name_search(cr, user, '', dom, context=search_context, limit=None, name_get_uid=1)
                        if (node.get('required') and not int(node.get('required'))) or not column.required:
                            attrs['selection'].append((False, ''))
                fields[node.get('name')] = attrs

                field = model_fields.get(node.get('name'))
                if field:
                    transfer_field_to_modifiers(field, modifiers)


        elif node.tag in ('form', 'tree'):
            result = self.view_header_get(cr, user, False, node.tag, context)
            if result:
                node.set('string', result)
            in_tree_view = node.tag == 'tree'

        elif node.tag == 'calendar':
            for additional_field in ('date_start', 'date_delay', 'date_stop', 'color'):
                if node.get(additional_field):
                    fields[node.get(additional_field)] = {}

        if not check_group(node):
            # node must be removed, no need to proceed further with its children
            return fields

        # The view architeture overrides the python model.
        # Get the attrs before they are (possibly) deleted by check_group below
        transfer_node_to_modifiers(node, modifiers, context, in_tree_view)

        # TODO remove attrs couterpart in modifiers when invisible is true ?

        # translate view
        if 'lang' in context:
            if node.text and node.text.strip():
                trans = self.pool.get('ir.translation')._get_source(cr, user, self._name, 'view', context['lang'], node.text.strip())
                if trans:
                    node.text = node.text.replace(node.text.strip(), trans)
            if node.tail and node.tail.strip():
                trans = self.pool.get('ir.translation')._get_source(cr, user, self._name, 'view', context['lang'], node.tail.strip())
                if trans:
                    node.tail =  node.tail.replace(node.tail.strip(), trans)

            if node.get('string') and not result:
                trans = self.pool.get('ir.translation')._get_source(cr, user, self._name, 'view', context['lang'], node.get('string'))
                if trans == node.get('string') and ('base_model_name' in context):
                    # If translation is same as source, perhaps we'd have more luck with the alternative model name
                    # (in case we are in a mixed situation, such as an inherited view where parent_view.model != model
                    trans = self.pool.get('ir.translation')._get_source(cr, user, context['base_model_name'], 'view', context['lang'], node.get('string'))
                if trans:
                    node.set('string', trans)

            for attr_name in ('confirm', 'sum', 'avg', 'help', 'placeholder'):
                attr_value = node.get(attr_name)
                if attr_value:
                    trans = self.pool.get('ir.translation')._get_source(cr, user, self._name, 'view', context['lang'], attr_value)
                    if trans:
                        node.set(attr_name, trans)

        for f in node:
            if children or (node.tag == 'field' and f.tag in ('filter','separator')):
                fields.update(self.__view_look_dom(cr, user, f, view_id, in_tree_view, model_fields, context))

        transfer_modifiers_to_node(modifiers, node)
        return fields

    def _disable_workflow_buttons(self, cr, user, node):
        """ Set the buttons in node to readonly if the user can't activate them. """
        if user == 1:
            # admin user can always activate workflow buttons
            return node

        # TODO handle the case of more than one workflow for a model or multiple
        # transitions with different groups and same signal
        usersobj = self.pool.get('res.users')
        buttons = (n for n in node.getiterator('button') if n.get('type') != 'object')
        for button in buttons:
            user_groups = usersobj.read(cr, user, [user], ['groups_id'])[0]['groups_id']
            cr.execute("""SELECT DISTINCT t.group_id
                        FROM wkf
                  INNER JOIN wkf_activity a ON a.wkf_id = wkf.id
                  INNER JOIN wkf_transition t ON (t.act_to = a.id)
                       WHERE wkf.osv = %s
                         AND t.signal = %s
                         AND t.group_id is NOT NULL
                   """, (self._name, button.get('name')))
            group_ids = [x[0] for x in cr.fetchall() if x[0]]
            can_click = not group_ids or bool(set(user_groups).intersection(group_ids))
            button.set('readonly', str(int(not can_click)))
        return node

    def __view_look_dom_arch(self, cr, user, node, view_id, context=None):
        """ Return an architecture and a description of all the fields.

        The field description combines the result of fields_get() and
        __view_look_dom().

        :param node: the architecture as as an etree
        :return: a tuple (arch, fields) where arch is the given node as a
            string and fields is the description of all the fields.

        """
        fields = {}
        if node.tag == 'diagram':
            if node.getchildren()[0].tag == 'node':
                node_model = self.pool[node.getchildren()[0].get('object')]
                node_fields = node_model.fields_get(cr, user, None, context)
                fields.update(node_fields)
                if not node.get("create") and not node_model.check_access_rights(cr, user, 'create', raise_exception=False):
                    node.set("create", 'false')
            if node.getchildren()[1].tag == 'arrow':
                arrow_fields = self.pool[node.getchildren()[1].get('object')].fields_get(cr, user, None, context)
                fields.update(arrow_fields)
        else:
            fields = self.fields_get(cr, user, None, context)
        fields_def = self.__view_look_dom(cr, user, node, view_id, False, fields, context=context)
        node = self._disable_workflow_buttons(cr, user, node)
        if node.tag in ('kanban', 'tree', 'form', 'gantt'):
            for action, operation in (('create', 'create'), ('delete', 'unlink'), ('edit', 'write')):
                if not node.get(action) and not self.check_access_rights(cr, user, operation, raise_exception=False):
                    node.set(action, 'false')
        arch = etree.tostring(node, encoding="utf-8").replace('\t', '')
        for k in fields.keys():
            if k not in fields_def:
                del fields[k]
        for field in fields_def:
            if field == 'id':
                # sometime, the view may contain the (invisible) field 'id' needed for a domain (when 2 objects have cross references)
                fields['id'] = {'readonly': True, 'type': 'integer', 'string': 'ID'}
            elif field in fields:
                fields[field].update(fields_def[field])
            else:
                cr.execute('select name, model from ir_ui_view where (id=%s or inherit_id=%s) and arch like %s', (view_id, view_id, '%%%s%%' % field))
                res = cr.fetchall()[:]
                model = res[0][1]
                res.insert(0, ("Can't find field '%s' in the following view parts composing the view of object model '%s':" % (field, model), None))
                msg = "\n * ".join([r[0] for r in res])
                msg += "\n\nEither you wrongly customized this view, or some modules bringing those views are not compatible with your current data model"
                _logger.error(msg)
                raise except_orm('View error', msg)
        return arch, fields

    def _get_default_form_view(self, cr, user, context=None):
        """ Generates a default single-line form view using all fields
        of the current model except the m2m and o2m ones.

        :param cr: database cursor
        :param int user: user id
        :param dict context: connection context
        :returns: a form view as an lxml document
        :rtype: etree._Element
        """
        view = etree.Element('form', string=self._description)
        # TODO it seems fields_get can be replaced by _all_columns (no need for translation)
        for field, descriptor in self.fields_get(cr, user, context=context).iteritems():
            if descriptor['type'] in ('one2many', 'many2many'):
                continue
            etree.SubElement(view, 'field', name=field)
            if descriptor['type'] == 'text':
                etree.SubElement(view, 'newline')
        return view

    def _get_default_search_view(self, cr, user, context=None):
        """ Generates a single-field search view, based on _rec_name.

        :param cr: database cursor
        :param int user: user id
        :param dict context: connection context
        :returns: a tree view as an lxml document
        :rtype: etree._Element
        """
        view = etree.Element('search', string=self._description)
        etree.SubElement(view, 'field', name=self._rec_name_fallback(cr, user, context))
        return view

    def _get_default_tree_view(self, cr, user, context=None):
        """ Generates a single-field tree view, based on _rec_name.

        :param cr: database cursor
        :param int user: user id
        :param dict context: connection context
        :returns: a tree view as an lxml document
        :rtype: etree._Element
        """
        view = etree.Element('tree', string=self._description)
        etree.SubElement(view, 'field', name=self._rec_name_fallback(cr, user, context))
        return view

    def _get_default_calendar_view(self, cr, user, context=None):
        """ Generates a default calendar view by trying to infer
        calendar fields from a number of pre-set attribute names

        :param cr: database cursor
        :param int user: user id
        :param dict context: connection context
        :returns: a calendar view
        :rtype: etree._Element
        """
        def set_first_of(seq, in_, to):
            """Sets the first value of `seq` also found in `in_` to
            the `to` attribute of the view being closed over.

            Returns whether it's found a suitable value (and set it on
            the attribute) or not
            """
            for item in seq:
                if item in in_:
                    view.set(to, item)
                    return True
            return False

        view = etree.Element('calendar', string=self._description)
        etree.SubElement(view, 'field', self._rec_name_fallback(cr, user, context))

        if self._date_name not in self._columns:
            date_found = False
            for dt in ['date', 'date_start', 'x_date', 'x_date_start']:
                if dt in self._columns:
                    self._date_name = dt
                    date_found = True
                    break

            if not date_found:
                raise except_orm(_('Invalid Object Architecture!'), _("Insufficient fields for Calendar View!"))
        view.set('date_start', self._date_name)

        set_first_of(["user_id", "partner_id", "x_user_id", "x_partner_id"],
                     self._columns, 'color')

        if not set_first_of(["date_stop", "date_end", "x_date_stop", "x_date_end"],
                            self._columns, 'date_stop'):
            if not set_first_of(["date_delay", "planned_hours", "x_date_delay", "x_planned_hours"],
                                self._columns, 'date_delay'):
                raise except_orm(
                    _('Invalid Object Architecture!'),
                    _("Insufficient fields to generate a Calendar View for %s, missing a date_stop or a date_delay" % self._name))

        return view

    #
    # if view_id, view_type is not required
    #
    def fields_view_get(self, cr, user, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        """
        Get the detailed composition of the requested view like fields, model, view architecture

        :param cr: database cursor
        :param user: current user id
        :param view_id: id of the view or None
        :param view_type: type of the view to return if view_id is None ('form', tree', ...)
        :param context: context arguments, like lang, time zone
        :param toolbar: true to include contextual actions
        :param submenu: deprecated
        :return: dictionary describing the composition of the requested view (including inherited views and extensions)
        :raise AttributeError:
                            * if the inherited view has unknown position to work with other than 'before', 'after', 'inside', 'replace'
                            * if some tag other than 'position' is found in parent view
        :raise Invalid ArchitectureError: if there is view type other than form, tree, calendar, search etc defined on the structure

        """
        if context is None:
            context = {}

        def encode(s):
            if isinstance(s, unicode):
                return s.encode('utf8')
            return s

        def raise_view_error(error_msg, child_view_id):
            view, child_view = self.pool.get('ir.ui.view').browse(cr, user, [view_id, child_view_id], context)
            error_msg = error_msg % {'parent_xml_id': view.xml_id}
            raise AttributeError("View definition error for inherited view '%s' on model '%s': %s"
                                 %  (child_view.xml_id, self._name, error_msg))

        def locate(source, spec):
            """ Locate a node in a source (parent) architecture.

            Given a complete source (parent) architecture (i.e. the field
            `arch` in a view), and a 'spec' node (a node in an inheriting
            view that specifies the location in the source view of what
            should be changed), return (if it exists) the node in the
            source view matching the specification.

            :param source: a parent architecture to modify
            :param spec: a modifying node in an inheriting view
            :return: a node in the source matching the spec

            """
            if spec.tag == 'xpath':
                nodes = source.xpath(spec.get('expr'))
                return nodes[0] if nodes else None
            elif spec.tag == 'field':
                # Only compare the field name: a field can be only once in a given view
                # at a given level (and for multilevel expressions, we should use xpath
                # inheritance spec anyway).
                for node in source.getiterator('field'):
                    if node.get('name') == spec.get('name'):
                        return node
                return None

            for node in source.getiterator(spec.tag):
                if isinstance(node, SKIPPED_ELEMENT_TYPES):
                    continue
                if all(node.get(attr) == spec.get(attr) \
                        for attr in spec.attrib
                            if attr not in ('position','version')):
                    # Version spec should match parent's root element's version
                    if spec.get('version') and spec.get('version') != source.get('version'):
                        return None
                    return node
            return None

        def apply_inheritance_specs(source, specs_arch, inherit_id=None):
            """ Apply an inheriting view.

            Apply to a source architecture all the spec nodes (i.e. nodes
            describing where and what changes to apply to some parent
            architecture) given by an inheriting view.

            :param source: a parent architecture to modify
            :param specs_arch: a modifying architecture in an inheriting view
            :param inherit_id: the database id of the inheriting view
            :return: a modified source where the specs are applied

            """
            specs_tree = etree.fromstring(encode(specs_arch))
            # Queue of specification nodes (i.e. nodes describing where and
            # changes to apply to some parent architecture).
            specs = [specs_tree]

            while len(specs):
                spec = specs.pop(0)
                if isinstance(spec, SKIPPED_ELEMENT_TYPES):
                    continue
                if spec.tag == 'data':
                    specs += [ c for c in specs_tree ]
                    continue
                node = locate(source, spec)
                if node is not None:
                    pos = spec.get('position', 'inside')
                    if pos == 'replace':
                        if node.getparent() is None:
                            source = copy.deepcopy(spec[0])
                        else:
                            for child in spec:
                                node.addprevious(child)
                            node.getparent().remove(node)
                    elif pos == 'attributes':
                        for child in spec.getiterator('attribute'):
                            attribute = (child.get('name'), child.text and child.text.encode('utf8') or None)
                            if attribute[1]:
                                node.set(attribute[0], attribute[1])
                            else:
                                del(node.attrib[attribute[0]])
                    else:
                        sib = node.getnext()
                        for child in spec:
                            if pos == 'inside':
                                node.append(child)
                            elif pos == 'after':
                                if sib is None:
                                    node.addnext(child)
                                    node = child
                                else:
                                    sib.addprevious(child)
                            elif pos == 'before':
                                node.addprevious(child)
                            else:
                                raise_view_error("Invalid position value: '%s'" % pos, inherit_id)
                else:
                    attrs = ''.join([
                        ' %s="%s"' % (attr, spec.get(attr))
                        for attr in spec.attrib
                        if attr != 'position'
                    ])
                    tag = "<%s%s>" % (spec.tag, attrs)
                    if spec.get('version') and spec.get('version') != source.get('version'):
                        raise_view_error("Mismatching view API version for element '%s': %r vs %r in parent view '%%(parent_xml_id)s'" % \
                                            (tag, spec.get('version'), source.get('version')), inherit_id)
                    raise_view_error("Element '%s' not found in parent view '%%(parent_xml_id)s'" % tag, inherit_id)

            return source

        def apply_view_inheritance(cr, user, source, inherit_id):
            """ Apply all the (directly and indirectly) inheriting views.

            :param source: a parent architecture to modify (with parent
                modifications already applied)
            :param inherit_id: the database view_id of the parent view
            :return: a modified source where all the modifying architecture
                are applied

            """
            sql_inherit = self.pool.get('ir.ui.view').get_inheriting_views_arch(cr, user, inherit_id, self._name, context=context)
            for (view_arch, view_id) in sql_inherit:
                source = apply_inheritance_specs(source, view_arch, view_id)
                source = apply_view_inheritance(cr, user, source, view_id)
            return source

        result = {'type': view_type, 'model': self._name}

        sql_res = False
        parent_view_model = None
        view_ref_key = view_type + '_view_ref'
        view_ref = context.get(view_ref_key)
        # Search for a root (i.e. without any parent) view.
        while True:
            if view_ref and not view_id:
                if '.' in view_ref:
                    module, view_ref = view_ref.split('.', 1)
                    cr.execute("SELECT res_id FROM ir_model_data WHERE model='ir.ui.view' AND module=%s AND name=%s", (module, view_ref))
                    view_ref_res = cr.fetchone()
                    if view_ref_res:
                        view_id = view_ref_res[0]
                else:
                    _logger.warning('%r requires a fully-qualified external id (got: %r for model %s). '
                        'Please use the complete `module.view_id` form instead.', view_ref_key, view_ref,
                        self._name)

            if view_id:
                cr.execute("""SELECT arch,name,field_parent,id,type,inherit_id,model
                              FROM ir_ui_view
                              WHERE id=%s""", (view_id,))
            else:
                cr.execute("""SELECT arch,name,field_parent,id,type,inherit_id,model
                              FROM ir_ui_view
                              WHERE model=%s AND type=%s AND inherit_id IS NULL
                              ORDER BY priority""", (self._name, view_type))
            sql_res = cr.dictfetchone()

            if not sql_res:
                break

            view_id = sql_res['inherit_id'] or sql_res['id']
            parent_view_model = sql_res['model']
            if not sql_res['inherit_id']:
                break

        # if a view was found
        if sql_res:
            source = etree.fromstring(encode(sql_res['arch']))
            result.update(
                arch=apply_view_inheritance(cr, user, source, sql_res['id']),
                type=sql_res['type'],
                view_id=sql_res['id'],
                name=sql_res['name'],
                field_parent=sql_res['field_parent'] or False)
        else:
            # otherwise, build some kind of default view
            try:
                view = getattr(self, '_get_default_%s_view' % view_type)(
                    cr, user, context)
            except AttributeError:
                # what happens here, graph case?
                raise except_orm(_('Invalid Architecture!'), _("There is no view of type '%s' defined for the structure!") % view_type)

            result.update(
                arch=view,
                name='default',
                field_parent=False,
                view_id=0)

        if parent_view_model != self._name:
            ctx = context.copy()
            ctx['base_model_name'] = parent_view_model
        else:
            ctx = context
        xarch, xfields = self.__view_look_dom_arch(cr, user, result['arch'], view_id, context=ctx)
        result['arch'] = xarch
        result['fields'] = xfields

        if toolbar:
            def clean(x):
                x = x[2]
                for key in ('report_sxw_content', 'report_rml_content',
                        'report_sxw', 'report_rml',
                        'report_sxw_content_data', 'report_rml_content_data'):
                    if key in x:
                        del x[key]
                return x
            ir_values_obj = self.pool.get('ir.values')
            resprint = ir_values_obj.get(cr, user, 'action',
                    'client_print_multi', [(self._name, False)], False,
                    context)
            resaction = ir_values_obj.get(cr, user, 'action',
                    'client_action_multi', [(self._name, False)], False,
                    context)

            resrelate = ir_values_obj.get(cr, user, 'action',
                    'client_action_relate', [(self._name, False)], False,
                    context)
            resaction = [clean(action) for action in resaction
                         if view_type == 'tree' or not action[2].get('multi')]
            resprint = [clean(print_) for print_ in resprint
                        if view_type == 'tree' or not print_[2].get('multi')]
            #When multi="True" set it will display only in More of the list view
            resrelate = [clean(action) for action in resrelate
                         if (action[2].get('multi') and view_type == 'tree') or (not action[2].get('multi') and view_type == 'form')]

            for x in itertools.chain(resprint, resaction, resrelate):
                x['string'] = x['name']

            result['toolbar'] = {
                'print': resprint,
                'action': resaction,
                'relate': resrelate
            }
        return result

    _view_look_dom_arch = __view_look_dom_arch

    def search_count(self, cr, user, args, context=None):
        if not context:
            context = {}
        res = self.search(cr, user, args, context=context, count=True)
        if isinstance(res, list):
            return len(res)
        return res

    @api.returns('self')
    def search(self, cr, user, args, offset=0, limit=None, order=None, context=None, count=False):
        """
        Search for records based on a search domain.

        :param cr: database cursor
        :param user: current user id
        :param args: list of tuples specifying the search domain [('field_name', 'operator', value), ...]. Pass an empty list to match all records.
        :param offset: optional number of results to skip in the returned values (default: 0)
        :param limit: optional max number of records to return (default: **None**)
        :param order: optional columns to sort by (default: self._order=id )
        :param context: optional context arguments, like lang, time zone
        :type context: dictionary
        :param count: optional (default: **False**), if **True**, returns only the number of records matching the criteria, not their ids
        :return: id or list of ids of records matching the criteria
        :rtype: integer or list of integers
        :raise AccessError: * if user tries to bypass access rules for read on the requested object.

        **Expressing a search domain (args)**

        Each tuple in the search domain needs to have 3 elements, in the form: **('field_name', 'operator', value)**, where:

            * **field_name** must be a valid name of field of the object model, possibly following many-to-one relationships using dot-notation, e.g 'street' or 'partner_id.country' are valid values.
            * **operator** must be a string with a valid comparison operator from this list: ``=, !=, >, >=, <, <=, like, ilike, in, not in, child_of, parent_left, parent_right``
              The semantics of most of these operators are obvious.
              The ``child_of`` operator will look for records who are children or grand-children of a given record,
              according to the semantics of this model (i.e following the relationship field named by
              ``self._parent_name``, by default ``parent_id``.
            * **value** must be a valid value to compare with the values of **field_name**, depending on its type.

        Domain criteria can be combined using 3 logical operators than can be added between tuples:  '**&**' (logical AND, default), '**|**' (logical OR), '**!**' (logical NOT).
        These are **prefix** operators and the arity of the '**&**' and '**|**' operator is 2, while the arity of the '**!**' is just 1.
        Be very careful about this when you combine them the first time.

        Here is an example of searching for Partners named *ABC* from Belgium and Germany whose language is not english ::

            [('name','=','ABC'),'!',('language.code','=','en_US'),'|',('country_id.code','=','be'),('country_id.code','=','de'))

        The '&' is omitted as it is the default, and of course we could have used '!=' for the language, but what this domain really represents is::

            (name is 'ABC' AND (language is NOT english) AND (country is Belgium OR Germany))

        """
        return self._search(cr, user, args, offset=offset, limit=limit, order=order, context=context, count=count)

    def name_get(self, cr, user, ids, context=None):
        """Returns the preferred display value (text representation) for the records with the
           given ``ids``. By default this will be the value of the ``name`` column, unless
           the model implements a custom behavior.
           Can sometimes be seen as the inverse function of :meth:`~.name_search`, but it is not
           guaranteed to be.

           :rtype: list(tuple)
           :return: list of pairs ``(id,text_repr)`` for all records with the given ``ids``.
        """
        if not ids:
            return []
        if isinstance(ids, (int, long)):
            ids = [ids]

        if self._rec_name in self._all_columns:
            rec_name_column = self._all_columns[self._rec_name].column
            return [(r['id'], rec_name_column.as_display_name(cr, user, self, r[self._rec_name], context=context))
                        for r in self.read(cr, user, ids, [self._rec_name],
                                       load='_classic_write', context=context)]
        return [(id, "%s,%s" % (self._name, id)) for id in ids]

    def name_search(self, cr, user, name='', args=None, operator='ilike', context=None, limit=100):
        """Search for records that have a display name matching the given ``name`` pattern if compared
           with the given ``operator``, while also matching the optional search domain (``args``).
           This is used for example to provide suggestions based on a partial value for a relational
           field.
           Sometimes be seen as the inverse function of :meth:`~.name_get`, but it is not
           guaranteed to be.

           This method is equivalent to calling :meth:`~.search` with a search domain based on ``name``
           and then :meth:`~.name_get` on the result of the search.

           :param list args: optional search domain (see :meth:`~.search` for syntax),
                             specifying further restrictions
           :param str operator: domain operator for matching the ``name`` pattern, such as ``'like'``
                                or ``'='``.
           :param int limit: optional max number of records to return
           :rtype: list
           :return: list of pairs ``(id,text_repr)`` for all matching records.
        """
        return self._name_search(cr, user, name, args, operator, context, limit)

    def name_create(self, cr, uid, name, context=None):
        """Creates a new record by calling :meth:`~.create` with only one
           value provided: the name of the new record (``_rec_name`` field).
           The new record will also be initialized with any default values applicable
           to this model, or provided through the context. The usual behavior of
           :meth:`~.create` applies.
           Similarly, this method may raise an exception if the model has multiple
           required fields and some do not have default values.

           :param name: name of the record to create

           :rtype: tuple
           :return: the :meth:`~.name_get` pair value for the newly-created record.
        """
        rec_id = self.create(cr, uid, {self._rec_name: name}, context)
        return self.name_get(cr, uid, [rec_id], context)[0]

    # private implementation of name_search, allows passing a dedicated user for the name_get part to
    # solve some access rights issues
    def _name_search(self, cr, user, name='', args=None, operator='ilike', context=None, limit=100, name_get_uid=None):
        if args is None:
            args = []
        if context is None:
            context = {}
        args = args[:]
        # optimize out the default criterion of ``ilike ''`` that matches everything
        if not (name == '' and operator == 'ilike'):
            args += [(self._rec_name, operator, name)]
        access_rights_uid = name_get_uid or user
        ids = self._search(cr, user, args, limit=limit, context=context, access_rights_uid=access_rights_uid)
        res = self.name_get(cr, access_rights_uid, ids, context)
        return res

    def read_string(self, cr, uid, id, langs, fields=None, context=None):
        res = {}
        res2 = {}
        self.pool.get('ir.translation').check_access_rights(cr, uid, 'read')
        if not fields:
            fields = self._columns.keys() + self._inherit_fields.keys()
        #FIXME: collect all calls to _get_source into one SQL call.
        for lang in langs:
            res[lang] = {'code': lang}
            for f in fields:
                if f in self._columns:
                    res_trans = self.pool.get('ir.translation')._get_source(cr, uid, self._name+','+f, 'field', lang)
                    if res_trans:
                        res[lang][f] = res_trans
                    else:
                        res[lang][f] = self._columns[f].string
        for table in self._inherits:
            cols = intersect(self._inherit_fields.keys(), fields)
            res2 = self.pool[table].read_string(cr, uid, id, langs, cols, context)
        for lang in res2:
            if lang in res:
                res[lang]['code'] = lang
            for f in res2[lang]:
                res[lang][f] = res2[lang][f]
        return res

    def write_string(self, cr, uid, id, langs, vals, context=None):
        self.pool.get('ir.translation').check_access_rights(cr, uid, 'write')
        #FIXME: try to only call the translation in one SQL
        for lang in langs:
            for field in vals:
                if field in self._columns:
                    src = self._columns[field].string
                    self.pool.get('ir.translation')._set_ids(cr, uid, self._name+','+field, 'field', lang, [0], vals[field], src)
        for table in self._inherits:
            cols = intersect(self._inherit_fields.keys(), vals)
            if cols:
                self.pool[table].write_string(cr, uid, id, langs, vals, context)
        return True

    def _add_missing_default_values(self, cr, uid, values, context=None):
        missing_defaults = []
        avoid_tables = [] # avoid overriding inherited values when parent is set
        for tables, parent_field in self._inherits.items():
            if parent_field in values:
                avoid_tables.append(tables)
        for field in self._columns.keys():
            if not field in values:
                missing_defaults.append(field)
        for field in self._inherit_fields.keys():
            if (field not in values) and (self._inherit_fields[field][0] not in avoid_tables):
                missing_defaults.append(field)

        if len(missing_defaults):
            # override defaults with the provided values, never allow the other way around
            defaults = self.default_get(cr, uid, missing_defaults, context)
            for dv in defaults:
                if ((dv in self._columns and self._columns[dv]._type == 'many2many') \
                     or (dv in self._inherit_fields and self._inherit_fields[dv][2]._type == 'many2many')) \
                        and defaults[dv] and isinstance(defaults[dv][0], (int, long)):
                    defaults[dv] = [(6, 0, defaults[dv])]
                if (dv in self._columns and self._columns[dv]._type == 'one2many' \
                    or (dv in self._inherit_fields and self._inherit_fields[dv][2]._type == 'one2many')) \
                        and isinstance(defaults[dv], (list, tuple)) and defaults[dv] and isinstance(defaults[dv][0], dict):
                    defaults[dv] = [(0, 0, x) for x in defaults[dv]]
            defaults.update(values)
            values = defaults
        return values

    def clear_caches(self):
        """ Clear the caches

        This clears the caches associated to methods decorated with
        ``tools.ormcache`` or ``tools.ormcache_multi``.
        """
        try:
            getattr(self, '_ormcache')
            self._ormcache = {}
            self.pool._any_cache_cleared = True
        except AttributeError:
            pass


    def _read_group_fill_results(self, cr, uid, domain, groupby, groupby_list, aggregated_fields,
                                 read_group_result, read_group_order=None, context=None):
        """Helper method for filling in empty groups for all possible values of
           the field being grouped by"""

        # self._group_by_full should map groupable fields to a method that returns
        # a list of all aggregated values that we want to display for this field,
        # in the form of a m2o-like pair (key,label).
        # This is useful to implement kanban views for instance, where all columns
        # should be displayed even if they don't contain any record.

        # Grab the list of all groups that should be displayed, including all present groups
        present_group_ids = [x[groupby][0] for x in read_group_result if x[groupby]]
        all_groups,folded = self._group_by_full[groupby](self, cr, uid, present_group_ids, domain,
                                                  read_group_order=read_group_order,
                                                  access_rights_uid=openerp.SUPERUSER_ID,
                                                  context=context)

        result_template = dict.fromkeys(aggregated_fields, False)
        result_template[groupby + '_count'] = 0
        if groupby_list and len(groupby_list) > 1:
            result_template['__context'] = {'group_by': groupby_list[1:]}

        # Merge the left_side (current results as dicts) with the right_side (all
        # possible values as m2o pairs). Both lists are supposed to be using the
        # same ordering, and can be merged in one pass.
        result = []
        known_values = {}
        def append_left(left_side):
            grouped_value = left_side[groupby] and left_side[groupby][0]
            if not grouped_value in known_values:
                result.append(left_side)
                known_values[grouped_value] = left_side
            else:
                count_attr = groupby + '_count'
                known_values[grouped_value].update({count_attr: left_side[count_attr]})
        def append_right(right_side):
            grouped_value = right_side[0]
            if not grouped_value in known_values:
                line = dict(result_template)
                line[groupby] = right_side
                line['__domain'] = [(groupby,'=',grouped_value)] + domain
                result.append(line)
                known_values[grouped_value] = line
        while read_group_result or all_groups:
            left_side = read_group_result[0] if read_group_result else None
            right_side = all_groups[0] if all_groups else None
            assert left_side is None or left_side[groupby] is False \
                 or isinstance(left_side[groupby], (tuple,list)), \
                'M2O-like pair expected, got %r' % left_side[groupby]
            assert right_side is None or isinstance(right_side, (tuple,list)), \
                'M2O-like pair expected, got %r' % right_side
            if left_side is None:
                append_right(all_groups.pop(0))
            elif right_side is None:
                append_left(read_group_result.pop(0))
            elif left_side[groupby] == right_side:
                append_left(read_group_result.pop(0))
                all_groups.pop(0) # discard right_side
            elif not left_side[groupby] or not left_side[groupby][0]:
                # left side == "Undefined" entry, not present on right_side
                append_left(read_group_result.pop(0))
            else:
                append_right(all_groups.pop(0))

        if folded:
            for r in result:
                r['__fold'] = folded.get(r[groupby] and r[groupby][0], False)
        return result

    def read_group(self, cr, uid, domain, fields, groupby, offset=0, limit=None, context=None, orderby=False):
        """
        Get the list of records in list view grouped by the given ``groupby`` fields

        :param cr: database cursor
        :param uid: current user id
        :param domain: list specifying search criteria [['field_name', 'operator', 'value'], ...]
        :param list fields: list of fields present in the list view specified on the object
        :param list groupby: fields by which the records will be grouped
        :param int offset: optional number of records to skip
        :param int limit: optional max number of records to return
        :param dict context: context arguments, like lang, time zone. A special
                             context key exist for datetime fields : ``datetime_format``.
                             context[``datetime_format``] = {
                                'field_name': {
                                    groupby_format: format for to_char (default: yyyy-mm)
                                    display_format: format for displaying the value
                                                    in the result (default: MMM yyyy)
                                    interval: day, month or year; used for begin
                                              and end date of group_by intervals
                                              computation (default: month)
                                }
                             }
        :param list orderby: optional ``order by`` specification, for
                             overriding the natural sort ordering of the
                             groups, see also :py:meth:`~osv.osv.osv.search`
                             (supported only for many2one fields currently)
        :return: list of dictionaries(one dictionary for each record) containing:

                    * the values of fields grouped by the fields in ``groupby`` argument
                    * __domain: list of tuples specifying the search criteria
                    * __context: dictionary with argument like ``groupby``
        :rtype: [{'field_name_1': value, ...]
        :raise AccessError: * if user has no read rights on the requested object
                            * if user tries to bypass access rules for read on the requested object

        """
        context = context or {}
        self.check_access_rights(cr, uid, 'read')
        if not fields:
            fields = self._columns.keys()

        query = self._where_calc(cr, uid, domain, context=context)
        self._apply_ir_rules(cr, uid, query, 'read', context=context)

        # Take care of adding join(s) if groupby is an '_inherits'ed field
        groupby_list = groupby
        qualified_groupby_field = groupby
        if groupby:
            if isinstance(groupby, list):
                groupby = groupby[0]
            qualified_groupby_field = self._inherits_join_calc(groupby, query)

        if groupby:
            assert not groupby or groupby in fields, "Fields in 'groupby' must appear in the list of fields to read (perhaps it's missing in the list view?)"
            groupby_def = self._columns.get(groupby) or (self._inherit_fields.get(groupby) and self._inherit_fields.get(groupby)[2])
            assert groupby_def and groupby_def._classic_write, "Fields in 'groupby' must be regular database-persisted fields (no function or related fields), or function fields with store=True"

        # TODO it seems fields_get can be replaced by _all_columns (no need for translation)
        fget = self.fields_get(cr, uid, fields)
        flist = ''
        group_count = group_by = groupby
        group_by_params = {}
        if groupby:
            if fget.get(groupby):
                groupby_type = fget[groupby]['type']
                if groupby_type in ('date', 'datetime'):
                    if context.get('datetime_format') and isinstance(context['datetime_format'], dict) \
                            and context['datetime_format'].get(groupby) and isinstance(context['datetime_format'][groupby], dict):
                        groupby_format = context['datetime_format'][groupby].get('groupby_format', 'yyyy-mm')
                        display_format = context['datetime_format'][groupby].get('display_format', 'MMMM yyyy')
                        interval = context['datetime_format'][groupby].get('interval', 'month')
                    else:
                        groupby_format = 'yyyy-mm'
                        display_format = 'MMMM yyyy'
                        interval = 'month'
                    group_by_params = {
                        'groupby_format': groupby_format,
                        'display_format': display_format,
                        'interval': interval,
                    }
                    qualified_groupby_field = "to_char(%s,%%s)" % qualified_groupby_field
                    flist = "%s as %s " % (qualified_groupby_field, groupby)
                elif groupby_type == 'boolean':
                    qualified_groupby_field = "coalesce(%s,false)" % qualified_groupby_field
                    flist = "%s as %s " % (qualified_groupby_field, groupby)
                else:
                    flist = qualified_groupby_field
            else:
                # Don't allow arbitrary values, as this would be a SQL injection vector!
                raise except_orm(_('Invalid group_by'),
                                 _('Invalid group_by specification: "%s".\nA group_by specification must be a list of valid fields.')%(groupby,))

        aggregated_fields = [
            f for f in fields
            if f not in ('id', 'sequence')
            if fget[f]['type'] in ('integer', 'float')
            if (f in self._columns and getattr(self._columns[f], '_classic_write'))]
        for f in aggregated_fields:
            group_operator = fget[f].get('group_operator', 'sum')
            if flist:
                flist += ', '
            qualified_field = '"%s"."%s"' % (self._table, f)
            flist += "%s(%s) AS %s" % (group_operator, qualified_field, f)

        gb = groupby and (' GROUP BY ' + qualified_groupby_field) or ''

        from_clause, where_clause, where_clause_params = query.get_sql()
        if group_by_params and group_by_params.get('groupby_format'):
            where_clause_params = [group_by_params['groupby_format']] + where_clause_params + [group_by_params['groupby_format']]
        where_clause = where_clause and ' WHERE ' + where_clause
        limit_str = limit and ' limit %d' % limit or ''
        offset_str = offset and ' offset %d' % offset or ''
        if len(groupby_list) < 2 and context.get('group_by_no_leaf'):
            group_count = '_'
        cr.execute('SELECT min(%s.id) AS id, count(%s.id) AS %s_count' % (self._table, self._table, group_count) + (flist and ',') + flist + ' FROM ' + from_clause + where_clause + gb + limit_str + offset_str, where_clause_params)
        alldata = {}
        groupby = group_by
        for r in cr.dictfetchall():
            for fld, val in r.items():
                if val is None: r[fld] = False
            alldata[r['id']] = r
            del r['id']

        order = orderby or groupby
        data_ids = self.search(cr, uid, [('id', 'in', alldata.keys())], order=order, context=context)

        # the IDs of records that have groupby field value = False or '' should be included too
        data_ids += set(alldata.keys()).difference(data_ids)

        if groupby:
            data = self.read(cr, uid, data_ids, [groupby], context=context)
            # restore order of the search as read() uses the default _order (this is only for groups, so the footprint of data should be small):
            data_dict = dict((d['id'], d[groupby] ) for d in data)
            result = [{'id': i, groupby: data_dict[i]} for i in data_ids]
        else:
            result = [{'id': i} for i in data_ids]

        for d in result:
            if groupby:
                d['__domain'] = [(groupby, '=', alldata[d['id']][groupby] or False)] + domain
                if not isinstance(groupby_list, (str, unicode)):
                    if groupby or not context.get('group_by_no_leaf', False):
                        d['__context'] = {'group_by': groupby_list[1:]}
            if groupby and groupby in fget:
                if d[groupby] and fget[groupby]['type'] in ('date', 'datetime'):
                    groupby_datetime = datetime.datetime.strptime(alldata[d['id']][groupby], '%Y-%m-%d')
                    d[groupby] = babel.dates.format_date(
                        groupby_datetime, format=group_by_params.get('display_format', 'MMMM yyyy'), locale=context.get('lang', 'en_US'))
                    if group_by_params.get('interval') == 'month':
                        days = calendar.monthrange(groupby_datetime.year, groupby_datetime.month)[1]
                        domain_dt_begin = groupby_datetime.replace(day=1)
                        domain_dt_end = groupby_datetime.replace(day=days)
                    elif group_by_params.get('interval') == 'day':
                        domain_dt_begin = groupby_datetime.replace(hour=0, minute=0)
                        domain_dt_end = groupby_datetime.replace(hour=23, minute=59, second=59)
                    else:
                        domain_dt_begin = groupby_datetime.replace(month=1, day=1)
                        domain_dt_end = groupby_datetime.replace(month=12, day=31)
                    d['__domain'] = [(groupby, '>=', domain_dt_begin.strftime('%Y-%m-%d')), (groupby, '<=', domain_dt_end.strftime('%Y-%m-%d'))] + domain
                del alldata[d['id']][groupby]
            d.update(alldata[d['id']])
            del d['id']

        if groupby and groupby in self._group_by_full:
            result = self._read_group_fill_results(cr, uid, domain, groupby, groupby_list,
                                                   aggregated_fields, result, read_group_order=order,
                                                   context=context)

        return result

    def _inherits_join_add(self, current_model, parent_model_name, query):
        """
        Add missing table SELECT and JOIN clause to ``query`` for reaching the parent table (no duplicates)
        :param current_model: current model object
        :param parent_model_name: name of the parent model for which the clauses should be added
        :param query: query object on which the JOIN should be added
        """
        inherits_field = current_model._inherits[parent_model_name]
        parent_model = self.pool[parent_model_name]
        parent_alias, parent_alias_statement = query.add_join((current_model._table, parent_model._table, inherits_field, 'id', inherits_field), implicit=True)
        return parent_alias

    def _inherits_join_calc(self, field, query):
        """
        Adds missing table select and join clause(s) to ``query`` for reaching
        the field coming from an '_inherits' parent table (no duplicates).

        :param field: name of inherited field to reach
        :param query: query object on which the JOIN should be added
        :return: qualified name of field, to be used in SELECT clause
        """
        current_table = self
        parent_alias = '"%s"' % current_table._table
        while field in current_table._inherit_fields and not field in current_table._columns:
            parent_model_name = current_table._inherit_fields[field][0]
            parent_table = self.pool[parent_model_name]
            parent_alias = self._inherits_join_add(current_table, parent_model_name, query)
            current_table = parent_table
        return '%s."%s"' % (parent_alias, field)

    def _parent_store_compute(self, cr):
        if not self._parent_store:
            return
        _logger.info('Computing parent left and right for table %s...', self._table)
        def browse_rec(root, pos=0):
            # TODO: set order
            where = self._parent_name+'='+str(root)
            if not root:
                where = self._parent_name+' IS NULL'
            if self._parent_order:
                where += ' order by '+self._parent_order
            cr.execute('SELECT id FROM '+self._table+' WHERE '+where)
            pos2 = pos + 1
            for id in cr.fetchall():
                pos2 = browse_rec(id[0], pos2)
            cr.execute('update '+self._table+' set parent_left=%s, parent_right=%s where id=%s', (pos, pos2, root))
            return pos2 + 1
        query = 'SELECT id FROM '+self._table+' WHERE '+self._parent_name+' IS NULL'
        if self._parent_order:
            query += ' order by ' + self._parent_order
        pos = 0
        cr.execute(query)
        for (root,) in cr.fetchall():
            pos = browse_rec(root, pos)
        self.invalidate_cache(['parent_left', 'parent_right'])
        return True

    def _update_store(self, cr, f, k):
        _logger.info("storing computed values of fields.function '%s'", k)
        ss = self._columns[k]._symbol_set
        update_query = 'UPDATE "%s" SET "%s"=%s WHERE id=%%s' % (self._table, k, ss[0])
        cr.execute('select id from '+self._table)
        ids_lst = map(lambda x: x[0], cr.fetchall())
        while ids_lst:
            iids = ids_lst[:40]
            ids_lst = ids_lst[40:]
            res = f.get(cr, self, iids, k, SUPERUSER_ID, {})
            for key, val in res.items():
                if f._multi:
                    val = val[k]
                # if val is a many2one, just write the ID
                if type(val) == tuple:
                    val = val[0]
                if val is not False:
                    cr.execute(update_query, (ss[1](val), key))

    def _check_selection_field_value(self, cr, uid, field, value, context=None):
        """Raise except_orm if value is not among the valid values for the selection field"""
        if self._columns[field]._type == 'reference':
            val_model, val_id_str = value.split(',', 1)
            val_id = False
            try:
                val_id = long(val_id_str)
            except ValueError:
                pass
            if not val_id:
                raise except_orm(_('ValidateError'),
                                 _('Invalid value for reference field "%s.%s" (last part must be a non-zero integer): "%s"') % (self._table, field, value))
            val = val_model
        else:
            val = value
        if isinstance(self._columns[field].selection, (tuple, list)):
            if val in dict(self._columns[field].selection):
                return
        elif val in dict(self._columns[field].selection(self, cr, uid, context=context)):
            return
        raise except_orm(_('ValidateError'),
                         _('The value "%s" for the field "%s.%s" is not in the selection') % (value, self._table, field))

    def _check_removed_columns(self, cr, log=False):
        # iterate on the database columns to drop the NOT NULL constraints
        # of fields which were required but have been removed (or will be added by another module)
        columns = [c for c in self._columns if not (isinstance(self._columns[c], fields.function) and not self._columns[c].store)]
        columns += MAGIC_COLUMNS
        cr.execute("SELECT a.attname, a.attnotnull"
                   "  FROM pg_class c, pg_attribute a"
                   " WHERE c.relname=%s"
                   "   AND c.oid=a.attrelid"
                   "   AND a.attisdropped=%s"
                   "   AND pg_catalog.format_type(a.atttypid, a.atttypmod) NOT IN ('cid', 'tid', 'oid', 'xid')"
                   "   AND a.attname NOT IN %s", (self._table, False, tuple(columns))),

        for column in cr.dictfetchall():
            if log:
                _logger.debug("column %s is in the table %s but not in the corresponding object %s",
                              column['attname'], self._table, self._name)
            if column['attnotnull']:
                cr.execute('ALTER TABLE "%s" ALTER COLUMN "%s" DROP NOT NULL' % (self._table, column['attname']))
                _schema.debug("Table '%s': column '%s': dropped NOT NULL constraint",
                              self._table, column['attname'])

    def _save_constraint(self, cr, constraint_name, type):
        """
        Record the creation of a constraint for this model, to make it possible
        to delete it later when the module is uninstalled. Type can be either
        'f' or 'u' depending on the constraing being a foreign key or not.
        """
        assert type in ('f', 'u')
        cr.execute("""
            SELECT 1 FROM ir_model_constraint, ir_module_module
            WHERE ir_model_constraint.module=ir_module_module.id
                AND ir_model_constraint.name=%s
                AND ir_module_module.name=%s
            """, (constraint_name, self._module))
        if not cr.rowcount:
            cr.execute("""
                INSERT INTO ir_model_constraint
                    (name, date_init, date_update, module, model, type)
                VALUES (%s, now() AT TIME ZONE 'UTC', now() AT TIME ZONE 'UTC',
                    (SELECT id FROM ir_module_module WHERE name=%s),
                    (SELECT id FROM ir_model WHERE model=%s), %s)""",
                    (constraint_name, self._module, self._name, type))

    def _save_relation_table(self, cr, relation_table):
        """
        Record the creation of a many2many for this model, to make it possible
        to delete it later when the module is uninstalled.
        """
        cr.execute("""
            SELECT 1 FROM ir_model_relation, ir_module_module
            WHERE ir_model_relation.module=ir_module_module.id
                AND ir_model_relation.name=%s
                AND ir_module_module.name=%s
            """, (relation_table, self._module))
        if not cr.rowcount:
            cr.execute("""INSERT INTO ir_model_relation (name, date_init, date_update, module, model)
                                 VALUES (%s, now() AT TIME ZONE 'UTC', now() AT TIME ZONE 'UTC',
                    (SELECT id FROM ir_module_module WHERE name=%s),
                    (SELECT id FROM ir_model WHERE model=%s))""",
                       (relation_table, self._module, self._name))
            self.invalidate_cache()

    # checked version: for direct m2o starting from `self`
    def _m2o_add_foreign_key_checked(self, source_field, dest_model, ondelete):
        assert self.is_transient() or not dest_model.is_transient(), \
            'Many2One relationships from non-transient Model to TransientModel are forbidden'
        if self.is_transient() and not dest_model.is_transient():
            # TransientModel relationships to regular Models are annoying
            # usually because they could block deletion due to the FKs.
            # So unless stated otherwise we default them to ondelete=cascade.
            ondelete = ondelete or 'cascade'
        fk_def = (self._table, source_field, dest_model._table, ondelete or 'set null')
        self._foreign_keys.add(fk_def)
        _schema.debug("Table '%s': added foreign key '%s' with definition=REFERENCES \"%s\" ON DELETE %s", *fk_def)

    # unchecked version: for custom cases, such as m2m relationships
    def _m2o_add_foreign_key_unchecked(self, source_table, source_field, dest_model, ondelete):
        fk_def = (source_table, source_field, dest_model._table, ondelete or 'set null')
        self._foreign_keys.add(fk_def)
        _schema.debug("Table '%s': added foreign key '%s' with definition=REFERENCES \"%s\" ON DELETE %s", *fk_def)

    def _drop_constraint(self, cr, source_table, constraint_name):
        cr.execute("ALTER TABLE %s DROP CONSTRAINT %s" % (source_table,constraint_name))

    def _m2o_fix_foreign_key(self, cr, source_table, source_field, dest_model, ondelete):
        # Find FK constraint(s) currently established for the m2o field,
        # and see whether they are stale or not
        cr.execute("""SELECT confdeltype as ondelete_rule, conname as constraint_name,
                             cl2.relname as foreign_table
                      FROM pg_constraint as con, pg_class as cl1, pg_class as cl2,
                           pg_attribute as att1, pg_attribute as att2
                      WHERE con.conrelid = cl1.oid
                        AND cl1.relname = %s
                        AND con.confrelid = cl2.oid
                        AND array_lower(con.conkey, 1) = 1
                        AND con.conkey[1] = att1.attnum
                        AND att1.attrelid = cl1.oid
                        AND att1.attname = %s
                        AND array_lower(con.confkey, 1) = 1
                        AND con.confkey[1] = att2.attnum
                        AND att2.attrelid = cl2.oid
                        AND att2.attname = %s
                        AND con.contype = 'f'""", (source_table, source_field, 'id'))
        constraints = cr.dictfetchall()
        if constraints:
            if len(constraints) == 1:
                # Is it the right constraint?
                cons, = constraints
                if cons['ondelete_rule'] != POSTGRES_CONFDELTYPES.get((ondelete or 'set null').upper(), 'a')\
                    or cons['foreign_table'] != dest_model._table:
                    # Wrong FK: drop it and recreate
                    _schema.debug("Table '%s': dropping obsolete FK constraint: '%s'",
                                  source_table, cons['constraint_name'])
                    self._drop_constraint(cr, source_table, cons['constraint_name'])
                else:
                    # it's all good, nothing to do!
                    return
            else:
                # Multiple FKs found for the same field, drop them all, and re-create
                for cons in constraints:
                    _schema.debug("Table '%s': dropping duplicate FK constraints: '%s'",
                                  source_table, cons['constraint_name'])
                    self._drop_constraint(cr, source_table, cons['constraint_name'])

        # (re-)create the FK
        self._m2o_add_foreign_key_checked(source_field, dest_model, ondelete)


    def set_default_value_on_column(self, cr, column_name, context=None):
        # ideally should use add_default_value but fails
        # due to ir.values not being ready

        # get old-style default
        default = self._defaults.get(column_name)
        if callable(default):
            default = default(self, cr, SUPERUSER_ID, context)

        # get new_style default if no old-style
        if default is None:
            record = self.new()
            field = self._fields[column_name]
            field.determine_default(record)
            defaults = record.get_draft_values()
            if column_name in defaults:
                default = field.convert_to_write(defaults[column_name])

        if default is not None:
            _logger.debug("Table '%s': setting default value of new column %s",
                          self._table, column_name)
            ss = self._columns[column_name]._symbol_set
            query = 'UPDATE "%s" SET "%s"=%s WHERE "%s" is NULL' % (
                self._table, column_name, ss[0], column_name)
            cr.execute(query, (ss[1](default),))
            # this is a disgrace
            cr.commit()

    def _auto_init(self, cr, context=None):
        """

        Call _field_create and, unless _auto is False:

        - create the corresponding table in database for the model,
        - possibly add the parent columns in database,
        - possibly add the columns 'create_uid', 'create_date', 'write_uid',
          'write_date' in database if _log_access is True (the default),
        - report on database columns no more existing in _columns,
        - remove no more existing not null constraints,
        - alter existing database columns to match _columns,
        - create database tables to match _columns,
        - add database indices to match _columns,
        - save in self._foreign_keys a list a foreign keys to create (see
          _auto_end).

        """
        self._foreign_keys = set()
        raise_on_invalid_object_name(self._name)
        if context is None:
            context = {}
        store_compute = False
        stored_fields = []              # new-style stored fields with compute
        todo_end = []
        update_custom_fields = context.get('update_custom_fields', False)
        self._field_create(cr, context=context)
        create = not self._table_exist(cr)
        if self._auto:

            if create:
                self._create_table(cr)

            cr.commit()
            if self._parent_store:
                if not self._parent_columns_exist(cr):
                    self._create_parent_columns(cr)
                    store_compute = True

            self._check_removed_columns(cr, log=False)

            # iterate on the "object columns"
            column_data = self._select_column_data(cr)

            for k, f in self._columns.iteritems():
                if k == 'id': # FIXME: maybe id should be a regular column?
                    continue
                # Don't update custom (also called manual) fields
                if f.manual and not update_custom_fields:
                    continue

                if isinstance(f, fields.one2many):
                    self._o2m_raise_on_missing_reference(cr, f)

                elif isinstance(f, fields.many2many):
                    self._m2m_raise_or_create_relation(cr, f)

                else:
                    res = column_data.get(k)

                    # The field is not found as-is in database, try if it
                    # exists with an old name.
                    if not res and hasattr(f, 'oldname'):
                        res = column_data.get(f.oldname)
                        if res:
                            cr.execute('ALTER TABLE "%s" RENAME "%s" TO "%s"' % (self._table, f.oldname, k))
                            res['attname'] = k
                            column_data[k] = res
                            _schema.debug("Table '%s': renamed column '%s' to '%s'",
                                self._table, f.oldname, k)

                    # The field already exists in database. Possibly
                    # change its type, rename it, drop it or change its
                    # constraints.
                    if res:
                        f_pg_type = res['typname']
                        f_pg_size = res['size']
                        f_pg_notnull = res['attnotnull']
                        if isinstance(f, fields.function) and not f.store and\
                                not getattr(f, 'nodrop', False):
                            _logger.info('column %s (%s) in table %s removed: converted to a function !\n',
                                         k, f.string, self._table)
                            cr.execute('ALTER TABLE "%s" DROP COLUMN "%s" CASCADE' % (self._table, k))
                            cr.commit()
                            _schema.debug("Table '%s': dropped column '%s' with cascade",
                                self._table, k)
                            f_obj_type = None
                        else:
                            f_obj_type = get_pg_type(f) and get_pg_type(f)[0]

                        if f_obj_type:
                            ok = False
                            casts = [
                                ('text', 'char', pg_varchar(f.size), '::%s' % pg_varchar(f.size)),
                                ('varchar', 'text', 'TEXT', ''),
                                ('int4', 'float', get_pg_type(f)[1], '::'+get_pg_type(f)[1]),
                                ('date', 'datetime', 'TIMESTAMP', '::TIMESTAMP'),
                                ('timestamp', 'date', 'date', '::date'),
                                ('numeric', 'float', get_pg_type(f)[1], '::'+get_pg_type(f)[1]),
                                ('float8', 'float', get_pg_type(f)[1], '::'+get_pg_type(f)[1]),
                            ]
                            if f_pg_type == 'varchar' and f._type == 'char' and ((f.size is None and f_pg_size) or f_pg_size < f.size):
                                cr.execute('ALTER TABLE "%s" RENAME COLUMN "%s" TO temp_change_size' % (self._table, k))
                                cr.execute('ALTER TABLE "%s" ADD COLUMN "%s" %s' % (self._table, k, pg_varchar(f.size)))
                                cr.execute('UPDATE "%s" SET "%s"=temp_change_size::%s' % (self._table, k, pg_varchar(f.size)))
                                cr.execute('ALTER TABLE "%s" DROP COLUMN temp_change_size CASCADE' % (self._table,))
                                cr.commit()
                                _schema.debug("Table '%s': column '%s' (type varchar) changed size from %s to %s",
                                    self._table, k, f_pg_size or 'unlimited', f.size or 'unlimited')
                            for c in casts:
                                if (f_pg_type==c[0]) and (f._type==c[1]):
                                    if f_pg_type != f_obj_type:
                                        ok = True
                                        cr.execute('ALTER TABLE "%s" RENAME COLUMN "%s" TO temp_change_size' % (self._table, k))
                                        cr.execute('ALTER TABLE "%s" ADD COLUMN "%s" %s' % (self._table, k, c[2]))
                                        cr.execute(('UPDATE "%s" SET "%s"=temp_change_size'+c[3]) % (self._table, k))
                                        cr.execute('ALTER TABLE "%s" DROP COLUMN temp_change_size CASCADE' % (self._table,))
                                        cr.commit()
                                        _schema.debug("Table '%s': column '%s' changed type from %s to %s",
                                            self._table, k, c[0], c[1])
                                    break

                            if f_pg_type != f_obj_type:
                                if not ok:
                                    i = 0
                                    while True:
                                        newname = k + '_moved' + str(i)
                                        cr.execute("SELECT count(1) FROM pg_class c,pg_attribute a " \
                                            "WHERE c.relname=%s " \
                                            "AND a.attname=%s " \
                                            "AND c.oid=a.attrelid ", (self._table, newname))
                                        if not cr.fetchone()[0]:
                                            break
                                        i += 1
                                    if f_pg_notnull:
                                        cr.execute('ALTER TABLE "%s" ALTER COLUMN "%s" DROP NOT NULL' % (self._table, k))
                                    cr.execute('ALTER TABLE "%s" RENAME COLUMN "%s" TO "%s"' % (self._table, k, newname))
                                    cr.execute('ALTER TABLE "%s" ADD COLUMN "%s" %s' % (self._table, k, get_pg_type(f)[1]))
                                    cr.execute("COMMENT ON COLUMN %s.\"%s\" IS %%s" % (self._table, k), (f.string,))
                                    _schema.debug("Table '%s': column '%s' has changed type (DB=%s, def=%s), data moved to column %s !",
                                        self._table, k, f_pg_type, f._type, newname)

                            # if the field is required and hasn't got a NOT NULL constraint
                            if f.required and f_pg_notnull == 0:
                                self.set_default_value_on_column(cr, k, context=context)
                                # add the NOT NULL constraint
                                try:
                                    cr.execute('ALTER TABLE "%s" ALTER COLUMN "%s" SET NOT NULL' % (self._table, k), log_exceptions=False)
                                    cr.commit()
                                    _schema.debug("Table '%s': column '%s': added NOT NULL constraint",
                                        self._table, k)
                                except Exception:
                                    msg = "Table '%s': unable to set a NOT NULL constraint on column '%s' !\n"\
                                        "If you want to have it, you should update the records and execute manually:\n"\
                                        "ALTER TABLE %s ALTER COLUMN %s SET NOT NULL"
                                    _schema.warning(msg, self._table, k, self._table, k)
                                cr.commit()
                            elif not f.required and f_pg_notnull == 1:
                                cr.execute('ALTER TABLE "%s" ALTER COLUMN "%s" DROP NOT NULL' % (self._table, k))
                                cr.commit()
                                _schema.debug("Table '%s': column '%s': dropped NOT NULL constraint",
                                    self._table, k)
                            # Verify index
                            indexname = '%s_%s_index' % (self._table, k)
                            cr.execute("SELECT indexname FROM pg_indexes WHERE indexname = %s and tablename = %s", (indexname, self._table))
                            res2 = cr.dictfetchall()
                            if not res2 and f.select:
                                cr.execute('CREATE INDEX "%s_%s_index" ON "%s" ("%s")' % (self._table, k, self._table, k))
                                cr.commit()
                                if f._type == 'text':
                                    # FIXME: for fields.text columns we should try creating GIN indexes instead (seems most suitable for an ERP context)
                                    msg = "Table '%s': Adding (b-tree) index for %s column '%s'."\
                                        "This is probably useless (does not work for fulltext search) and prevents INSERTs of long texts"\
                                        " because there is a length limit for indexable btree values!\n"\
                                        "Use a search view instead if you simply want to make the field searchable."
                                    _schema.warning(msg, self._table, f._type, k)
                            if res2 and not f.select:
                                cr.execute('DROP INDEX "%s_%s_index"' % (self._table, k))
                                cr.commit()
                                msg = "Table '%s': dropping index for column '%s' of type '%s' as it is not required anymore"
                                _schema.debug(msg, self._table, k, f._type)

                            if isinstance(f, fields.many2one):
                                dest_model = self.pool[f._obj]
                                if dest_model._table != 'ir_actions':
                                    self._m2o_fix_foreign_key(cr, self._table, k, dest_model, f.ondelete)

                    # The field doesn't exist in database. Create it if necessary.
                    else:
                        if not isinstance(f, fields.function) or f.store:
                            # add the missing field
                            cr.execute('ALTER TABLE "%s" ADD COLUMN "%s" %s' % (self._table, k, get_pg_type(f)[1]))
                            cr.execute("COMMENT ON COLUMN %s.\"%s\" IS %%s" % (self._table, k), (f.string,))
                            _schema.debug("Table '%s': added column '%s' with definition=%s",
                                self._table, k, get_pg_type(f)[1])

                            # initialize it
                            if not create:
                                self.set_default_value_on_column(cr, k, context=context)

                            # remember the functions to call for the stored fields
                            if isinstance(f, fields.function):
                                order = 10
                                if f.store is not True: # i.e. if f.store is a dict
                                    order = f.store[f.store.keys()[0]][2]
                                todo_end.append((order, self._update_store, (f, k)))

                            # remember new-style stored fields with compute method
                            if k in self._fields and self._fields[k].compute:
                                stored_fields.append(self._fields[k])

                            # and add constraints if needed
                            if isinstance(f, fields.many2one):
                                if f._obj not in self.pool:
                                    raise except_orm('Programming Error', 'There is no reference available for %s' % (f._obj,))
                                dest_model = self.pool[f._obj]
                                ref = dest_model._table
                                # ir_actions is inherited so foreign key doesn't work on it
                                if ref != 'ir_actions':
                                    self._m2o_add_foreign_key_checked(k, dest_model, f.ondelete)
                            if f.select:
                                cr.execute('CREATE INDEX "%s_%s_index" ON "%s" ("%s")' % (self._table, k, self._table, k))
                            if f.required:
                                try:
                                    cr.commit()
                                    cr.execute('ALTER TABLE "%s" ALTER COLUMN "%s" SET NOT NULL' % (self._table, k))
                                    _schema.debug("Table '%s': column '%s': added a NOT NULL constraint",
                                        self._table, k)
                                except Exception:
                                    msg = "WARNING: unable to set column %s of table %s not null !\n"\
                                        "Try to re-run: openerp-server --update=module\n"\
                                        "If it doesn't work, update records and execute manually:\n"\
                                        "ALTER TABLE %s ALTER COLUMN %s SET NOT NULL"
                                    _logger.warning(msg, k, self._table, self._table, k, exc_info=True)
                            cr.commit()

        else:
            cr.execute("SELECT relname FROM pg_class WHERE relkind IN ('r','v') AND relname=%s", (self._table,))
            create = not bool(cr.fetchone())

        cr.commit()     # start a new transaction

        if self._auto:
            self._add_sql_constraints(cr)

        if create:
            self._execute_sql(cr)

        if store_compute:
            self._parent_store_compute(cr)
            cr.commit()

        if stored_fields:
            # trigger computation of new-style stored fields with a compute
            def func(cr):
                _logger.info("Storing computed values of %s fields %s",
                    self._name, ', '.join(f.name for f in stored_fields))
                with scope_proxy(cr, SUPERUSER_ID, {'active_test': False}):
                    recs = self.search([])
                for f in stored_fields:
                    scope_proxy.recomputation.todo(f, recs)
                self.recompute()

            todo_end.append((1000, func, ()))

        return todo_end

    def _auto_end(self, cr, context=None):
        """ Create the foreign keys recorded by _auto_init. """
        for t, k, r, d in self._foreign_keys:
            cr.execute('ALTER TABLE "%s" ADD FOREIGN KEY ("%s") REFERENCES "%s" ON DELETE %s' % (t, k, r, d))
            self._save_constraint(cr, "%s_%s_fkey" % (t, k), 'f')
        cr.commit()
        del self._foreign_keys


    def _table_exist(self, cr):
        cr.execute("SELECT relname FROM pg_class WHERE relkind IN ('r','v') AND relname=%s", (self._table,))
        return cr.rowcount


    def _create_table(self, cr):
        cr.execute('CREATE TABLE "%s" (id SERIAL NOT NULL, PRIMARY KEY(id))' % (self._table,))
        cr.execute(("COMMENT ON TABLE \"%s\" IS %%s" % self._table), (self._description,))
        _schema.debug("Table '%s': created", self._table)


    def _parent_columns_exist(self, cr):
        cr.execute("""SELECT c.relname
            FROM pg_class c, pg_attribute a
            WHERE c.relname=%s AND a.attname=%s AND c.oid=a.attrelid
            """, (self._table, 'parent_left'))
        return cr.rowcount


    def _create_parent_columns(self, cr):
        cr.execute('ALTER TABLE "%s" ADD COLUMN "parent_left" INTEGER' % (self._table,))
        cr.execute('ALTER TABLE "%s" ADD COLUMN "parent_right" INTEGER' % (self._table,))
        if 'parent_left' not in self._columns:
            _logger.error('create a column parent_left on object %s: fields.integer(\'Left Parent\', select=1)',
                          self._table)
            _schema.debug("Table '%s': added column '%s' with definition=%s",
                self._table, 'parent_left', 'INTEGER')
        elif not self._columns['parent_left'].select:
            _logger.error('parent_left column on object %s must be indexed! Add select=1 to the field definition)',
                          self._table)
        if 'parent_right' not in self._columns:
            _logger.error('create a column parent_right on object %s: fields.integer(\'Right Parent\', select=1)',
                          self._table)
            _schema.debug("Table '%s': added column '%s' with definition=%s",
                self._table, 'parent_right', 'INTEGER')
        elif not self._columns['parent_right'].select:
            _logger.error('parent_right column on object %s must be indexed! Add select=1 to the field definition)',
                          self._table)
        if self._columns[self._parent_name].ondelete not in ('cascade', 'restrict'):
            _logger.error("The column %s on object %s must be set as ondelete='cascade' or 'restrict'",
                          self._parent_name, self._name)

        cr.commit()


    def _select_column_data(self, cr):
        # attlen is the number of bytes necessary to represent the type when
        # the type has a fixed size. If the type has a varying size attlen is
        # -1 and atttypmod is the size limit + 4, or -1 if there is no limit.
        cr.execute("SELECT c.relname,a.attname,a.attlen,a.atttypmod,a.attnotnull,a.atthasdef,t.typname,CASE WHEN a.attlen=-1 THEN (CASE WHEN a.atttypmod=-1 THEN 0 ELSE a.atttypmod-4 END) ELSE a.attlen END as size " \
           "FROM pg_class c,pg_attribute a,pg_type t " \
           "WHERE c.relname=%s " \
           "AND c.oid=a.attrelid " \
           "AND a.atttypid=t.oid", (self._table,))
        return dict(map(lambda x: (x['attname'], x),cr.dictfetchall()))


    def _o2m_raise_on_missing_reference(self, cr, f):
        # TODO this check should be a method on fields.one2many.
        if f._obj in self.pool:
            other = self.pool[f._obj]
            # TODO the condition could use fields_get_keys().
            if f._fields_id not in other._columns.keys():
                if f._fields_id not in other._inherit_fields.keys():
                    raise except_orm('Programming Error', "There is no reference field '%s' found for '%s'" % (f._fields_id, f._obj,))

    def _m2m_raise_or_create_relation(self, cr, f):
        m2m_tbl, col1, col2 = f._sql_names(self)
        self._save_relation_table(cr, m2m_tbl)
        cr.execute("SELECT relname FROM pg_class WHERE relkind IN ('r','v') AND relname=%s", (m2m_tbl,))
        if not cr.dictfetchall():
            if f._obj not in self.pool:
                raise except_orm('Programming Error', 'Many2Many destination model does not exist: `%s`' % (f._obj,))
            dest_model = self.pool[f._obj]
            ref = dest_model._table
            cr.execute('CREATE TABLE "%s" ("%s" INTEGER NOT NULL, "%s" INTEGER NOT NULL, UNIQUE("%s","%s"))' % (m2m_tbl, col1, col2, col1, col2))
            # create foreign key references with ondelete=cascade, unless the targets are SQL views
            cr.execute("SELECT relkind FROM pg_class WHERE relkind IN ('v') AND relname=%s", (ref,))
            if not cr.fetchall():
                self._m2o_add_foreign_key_unchecked(m2m_tbl, col2, dest_model, 'cascade')
            cr.execute("SELECT relkind FROM pg_class WHERE relkind IN ('v') AND relname=%s", (self._table,))
            if not cr.fetchall():
                self._m2o_add_foreign_key_unchecked(m2m_tbl, col1, self, 'cascade')

            cr.execute('CREATE INDEX "%s_%s_index" ON "%s" ("%s")' % (m2m_tbl, col1, m2m_tbl, col1))
            cr.execute('CREATE INDEX "%s_%s_index" ON "%s" ("%s")' % (m2m_tbl, col2, m2m_tbl, col2))
            cr.execute("COMMENT ON TABLE \"%s\" IS 'RELATION BETWEEN %s AND %s'" % (m2m_tbl, self._table, ref))
            cr.commit()
            _schema.debug("Create table '%s': m2m relation between '%s' and '%s'", m2m_tbl, self._table, ref)


    def _add_sql_constraints(self, cr):
        """

        Modify this model's database table constraints so they match the one in
        _sql_constraints.

        """
        def unify_cons_text(txt):
            return txt.lower().replace(', ',',').replace(' (','(')

        for (key, con, _) in self._sql_constraints:
            conname = '%s_%s' % (self._table, key)

            self._save_constraint(cr, conname, 'u')
            cr.execute("SELECT conname, pg_catalog.pg_get_constraintdef(oid, true) as condef FROM pg_constraint where conname=%s", (conname,))
            existing_constraints = cr.dictfetchall()
            sql_actions = {
                'drop': {
                    'execute': False,
                    'query': 'ALTER TABLE "%s" DROP CONSTRAINT "%s"' % (self._table, conname, ),
                    'msg_ok': "Table '%s': dropped constraint '%s'. Reason: its definition changed from '%%s' to '%s'" % (
                        self._table, conname, con),
                    'msg_err': "Table '%s': unable to drop \'%s\' constraint !" % (self._table, con),
                    'order': 1,
                },
                'add': {
                    'execute': False,
                    'query': 'ALTER TABLE "%s" ADD CONSTRAINT "%s" %s' % (self._table, conname, con,),
                    'msg_ok': "Table '%s': added constraint '%s' with definition=%s" % (self._table, conname, con),
                    'msg_err': "Table '%s': unable to add \'%s\' constraint !\n If you want to have it, you should update the records and execute manually:\n%%s" % (
                        self._table, con),
                    'order': 2,
                },
            }

            if not existing_constraints:
                # constraint does not exists:
                sql_actions['add']['execute'] = True
                sql_actions['add']['msg_err'] = sql_actions['add']['msg_err'] % (sql_actions['add']['query'], )
            elif unify_cons_text(con) not in [unify_cons_text(item['condef']) for item in existing_constraints]:
                # constraint exists but its definition has changed:
                sql_actions['drop']['execute'] = True
                sql_actions['drop']['msg_ok'] = sql_actions['drop']['msg_ok'] % (existing_constraints[0]['condef'].lower(), )
                sql_actions['add']['execute'] = True
                sql_actions['add']['msg_err'] = sql_actions['add']['msg_err'] % (sql_actions['add']['query'], )

            # we need to add the constraint:
            sql_actions = [item for item in sql_actions.values()]
            sql_actions.sort(key=lambda x: x['order'])
            for sql_action in [action for action in sql_actions if action['execute']]:
                try:
                    cr.execute(sql_action['query'])
                    cr.commit()
                    _schema.debug(sql_action['msg_ok'])
                except:
                    _schema.warning(sql_action['msg_err'])
                    cr.rollback()


    def _execute_sql(self, cr):
        """ Execute the SQL code from the _sql attribute (if any)."""
        if hasattr(self, "_sql"):
            for line in self._sql.split(';'):
                line2 = line.replace('\n', '').strip()
                if line2:
                    cr.execute(line2)
                    cr.commit()

    #
    # Update objects that uses this one to update their _inherits fields
    #

    @classmethod
    def _inherits_reload_src(cls):
        """ Recompute the _inherit_fields mapping on each _inherits'd child model."""
        for model in cls.pool.values():
            if cls._name in model._inherits:
                model._inherits_reload()

    @classmethod
    def _inherits_reload(cls):
        """ Recompute the _inherit_fields mapping.

        This will also call itself on each inherits'd child model.

        """
        res = {}
        for table in cls._inherits:
            other = cls.pool[table]
            for col in other._columns.keys():
                res[col] = (table, cls._inherits[table], other._columns[col], table)
            for col in other._inherit_fields.keys():
                res[col] = (table, cls._inherits[table], other._inherit_fields[col][2], other._inherit_fields[col][3])
        cls._inherit_fields = res
        cls._all_columns = cls._get_column_infos()

        # interface columns and inherited fields with new-style fields
        new_fields = {}
        for parent_model, parent_field in cls._inherits.iteritems():
            for attr, field in cls.pool[parent_model]._fields.iteritems():
                new_fields[attr] = field.copy(
                    related=(parent_field, attr), store=False, interface=True)
        for attr, column in cls._columns.iteritems():
            new_fields[attr] = Field.from_column(column)

        # update the model with the new fields
        for attr, field in new_fields.iteritems():
            old_field = cls._fields.get(attr)
            if not old_field or old_field.interface:
                # replace old_field if it is an interface
                cls._set_field_descriptor(attr, field)

        cls._inherits_reload_src()

    @classmethod
    def _get_column_infos(cls):
        """Returns a dict mapping all fields names (direct fields and
           inherited field via _inherits) to a ``column_info`` struct
           giving detailed columns """
        result = {}
        # do not inverse for loops, since local fields may hide inherited ones!
        for k, (parent, m2o, col, original_parent) in cls._inherit_fields.iteritems():
            result[k] = fields.column_info(k, col, parent, m2o, original_parent)
        for k, col in cls._columns.iteritems():
            result[k] = fields.column_info(k, col)
        return result

    @classmethod
    def _inherits_check(cls):
        for table, field_name in cls._inherits.items():
            if field_name not in cls._columns:
                _logger.info('Missing many2one field definition for _inherits reference "%s" in "%s", using default one.', field_name, cls._name)
                cls._columns[field_name] = fields.many2one(table, string="Automatically created field to link to parent %s" % table,
                                                             required=True, ondelete="cascade")
            elif not cls._columns[field_name].required or cls._columns[field_name].ondelete.lower() not in ("cascade", "restrict"):
                _logger.warning('Field definition for _inherits reference "%s" in "%s" must be marked as "required" with ondelete="cascade" or "restrict", forcing it to required + cascade.', field_name, cls._name)
                cls._columns[field_name].required = True
                cls._columns[field_name].ondelete = "cascade"

    def _before_registry_update(self):
        """ method called on all models before updating the registry """
        # reset setup of all fields
        for field in self._fields.itervalues():
            field.reset()

    def _after_registry_update(self):
        """ method called on all models after updating the registry """
        # complete the initialization of all fields
        for field in self._fields.itervalues():
            field.setup()

    def fields_get(self, cr, user, allfields=None, context=None, write_access=True):
        """ Return the definition of each field.

        The returned value is a dictionary (indiced by field name) of
        dictionaries. The _inherits'd fields are included. The string, help,
        and selection (if present) attributes are translated.

        :param cr: database cursor
        :param user: current user id
        :param allfields: list of fields
        :param context: context arguments, like lang, time zone
        :return: dictionary of field dictionaries, each one describing a field of the business object
        :raise AccessError: * if user has no create/write rights on the requested object

        """
        if context is None:
            context = {}

        write_access = self.check_access_rights(cr, user, 'write', raise_exception=False) \
            or self.check_access_rights(cr, user, 'create', raise_exception=False)

        translation_obj = self.pool.get('ir.translation')

        res = {}

        for f, field in self._fields.iteritems():
            if allfields and f not in allfields:
                continue
            if field.groups and not self.user_has_groups(cr, user, field.groups, context=context):
                continue

            res[f] = field.get_description()

            if not write_access:
                res[f]['readonly'] = True
                res[f]['states'] = {}

            if 'lang' in context:
                if 'string' in res[f]:
                    res_trans = translation_obj._get_source(cr, user, self._name + ',' + f, 'field', context['lang'])
                    if res_trans:
                        res[f]['string'] = res_trans
                if 'help' in res[f]:
                    help_trans = translation_obj._get_source(cr, user, self._name + ',' + f, 'help', context['lang'])
                    if help_trans:
                        res[f]['help'] = help_trans
                if 'selection' in res[f]:
                    if isinstance(field.selection, (tuple, list)):
                        sel = field.selection
                        sel2 = []
                        for key, val in sel:
                            val2 = None
                            if val:
                                val2 = translation_obj._get_source(cr, user, self._name + ',' + f, 'selection',  context['lang'], val)
                            sel2.append((key, val2 or val))
                        res[f]['selection'] = sel2

        return res

    def get_empty_list_help(self, cr, user, help, context=None):
        """ Generic method giving the help message displayed when having
            no result to display in a list or kanban view. By default it returns
            the help given in parameter that is generally the help message
            defined in the action.
        """
        return help

    def check_field_access_rights(self, cr, user, operation, fields, context=None):
        """
        Check the user access rights on the given fields. This raises Access
        Denied if the user does not have the rights. Otherwise it returns the
        fields (as is if the fields is not falsy, or the readable/writable
        fields if fields is falsy).
        """
        def p(field_name):
            """Predicate to test if the user has access to the given field name."""
            # Ignore requested field if it doesn't exist. This is ugly but
            # it seems to happen at least with 'name_alias' on res.partner.
            if field_name not in self._all_columns:
                return True
            field = self._all_columns[field_name].column
            if user != SUPERUSER_ID and field.groups:
                return self.user_has_groups(cr, user, groups=field.groups, context=context)
            else:
                return True
        if not fields:
            fields = filter(p, self._all_columns.keys())
        else:
            filtered_fields = filter(lambda a: not p(a), fields)
            if filtered_fields:
                _logger.warning('Access Denied by ACLs for operation: %s, uid: %s, model: %s, fields: %s', operation, user, self._name, ', '.join(filtered_fields))
                raise except_orm(
                    _('Access Denied'),
                    _('The requested operation cannot be completed due to security restrictions. '
                    'Please contact your system administrator.\n\n(Document type: %s, Operation: %s)') % \
                    (self._description, operation))
        return fields

    def read(self, cr, user, ids, fields=None, context=None, load='_classic_read'):
        """ Read records with given ids with the given fields.
            As a side-effect, the result is stored in the corresponding records' cache.

        :param cr: database cursor
        :param user: current user id
        :param ids: id or list of the ids of the records to read
        :param fields: optional list of field names to return (default: all fields would be returned)
        :type fields: list (example ['field_name_1', ...])
        :param context: optional context dictionary - it may contains keys for specifying certain options
                        like ``context_lang``, ``context_tz`` to alter the results of the call.
                        A special ``bin_size`` boolean flag may also be passed in the context to request the
                        value of all fields.binary columns to be returned as the size of the binary instead of its
                        contents. This can also be selectively overriden by passing a field-specific flag
                        in the form ``bin_size_XXX: True/False`` where ``XXX`` is the name of the field.
                        Note: The ``bin_size_XXX`` form is new in OpenERP v6.0.
        :return: list of dictionaries((dictionary per record asked)) with requested field values
        :rtype: [{‘name_of_the_field’: value, ...}, ...]
        :raise AccessError: * if user has no read rights on the requested object
                            * if user tries to bypass access rules for read on the requested object

        """
        # first check access rights
        self.check_access_rights(cr, user, 'read')
        fields = self.check_field_access_rights(cr, user, 'read', fields)

        if fields is None:
            fields = self._fields.keys()

        # split up fields into old-style and pure new-style ones
        old_fields, new_fields, unknown = [], [], []
        for key in fields:
            if key in self._columns:
                old_fields.append(key)
            elif key in self._fields:
                new_fields.append(key)
            else:
                unknown.append(key)

        if unknown:
            _logger.warning("%s.read() with unknown fields: %s", self._name, ', '.join(sorted(unknown)))

        # read old-style fields with (low-level) method _read_flat
        select = self.browse(ids)
        result = select._read_flat(old_fields, load=load)

        # update record caches with old-style fields
        select._prepare_cache(old_fields)
        for values in result:
            record = self.browse(values['id'])
            for name in old_fields:
                record[name] = values[name]

        # read new-style fields on records
        for values in result:
            record = self.browse(values['id'])
            for name in new_fields:
                values[name] = self._fields[name].convert_to_read(record[name])

        return result if isinstance(ids, list) else (bool(result) and result[0])

    def _read_flat(self, cr, user, ids, fields_to_read, context=None, load='_classic_read'):
        if not context:
            context = {}
        if not ids:
            return []
        if fields_to_read is None:
            fields_to_read = self._columns.keys()

        # Construct a clause for the security rules.
        # 'tables' hold the list of tables necessary for the SELECT including the ir.rule clauses,
        # or will at least contain self._table.
        rule_clause, rule_params, tables = self.pool.get('ir.rule').domain_get(cr, user, self._name, 'read', context=context)

        # all inherited fields + all non inherited fields for which the attribute whose name is in load is True
        fields_pre = [f for f in fields_to_read
                      if getattr(self._columns.get(f), '_classic_write', False)
                     ] + self._inherits.values()

        res = []
        if fields_pre or rule_clause:
            def convert_field(f):
                f_qual = '%s."%s"' % (self._table, f) # need fully-qualified references in case len(tables) > 1
                if isinstance(self._columns[f], fields.binary) and context.get('bin_size', False):
                    return 'length(%s) as "%s"' % (f_qual, f)
                return f_qual

            fields_pre2 = map(convert_field, fields_pre)
            order_by = self._parent_order or self._order
            select_fields = ','.join(fields_pre2 + ['%s.id' % self._table])
            query = 'SELECT %s FROM %s WHERE %s.id IN %%s' % (select_fields, ','.join(tables), self._table)
            if rule_clause:
                query += " AND " + (' OR '.join(rule_clause))
            query += " ORDER BY " + order_by
            for sub_ids in cr.split_for_in_conditions(ids):
                cr.execute(query, [tuple(sub_ids)] + rule_params)
                results = cr.dictfetchall()
                result_ids = [x['id'] for x in results]
                self._check_record_rules_result_count(cr, user, sub_ids, result_ids, 'read', context=context)
                res.extend(results)
        else:
            res = map(lambda x: {'id': x}, ids)

        if context.get('lang'):
            for f in fields_pre:
                if self._columns[f].translate:
                    ids = [x['id'] for x in res]
                    #TODO: optimize out of this loop
                    res_trans = self.pool.get('ir.translation')._get_ids(cr, user, self._name+','+f, 'model', context['lang'], ids)
                    for r in res:
                        r[f] = res_trans.get(r['id'], False) or r[f]

        for table in self._inherits:
            col = self._inherits[table]
            cols = [x for x in intersect(self._inherit_fields.keys(), fields_to_read) if x not in self._columns.keys()]
            if not cols:
                continue
            res2 = self.pool[table].read(cr, user, [x[col] for x in res], cols, context, load)

            res3 = {}
            for r in res2:
                res3[r['id']] = r
                del r['id']

            for record in res:
                if not record[col]: # if the record is deleted from _inherits table?
                    continue
                record.update(res3[record[col]])
                if col not in fields_to_read:
                    del record[col]

        # all fields which need to be post-processed by a simple function (symbol_get)
        fields_post = filter(lambda x: x in self._columns and self._columns[x]._symbol_get, fields_to_read)
        if fields_post:
            for r in res:
                for f in fields_post:
                    r[f] = self._columns[f]._symbol_get(r[f])
        ids = [x['id'] for x in res]

        # all non inherited fields for which the attribute whose name is in load is False
        fields_post = filter(lambda x: x in self._columns and not getattr(self._columns[x], load), fields_to_read)

        # Compute POST fields
        todo = {}
        for f in fields_post:
            todo.setdefault(self._columns[f]._multi, [])
            todo[self._columns[f]._multi].append(f)
        for key, val in todo.items():
            if key:
                res2 = self._columns[val[0]].get(cr, self, ids, val, user, context=context, values=res)
                assert res2 is not None, \
                    'The function field "%s" on the "%s" model returned None\n' \
                    '(a dictionary was expected).' % (val[0], self._name)
                for pos in val:
                    for record in res:
                        if isinstance(res2[record['id']], str): res2[record['id']] = eval(res2[record['id']]) #TOCHECK : why got string instend of dict in python2.6
                        multi_fields = res2.get(record['id'],{})
                        if multi_fields:
                            record[pos] = multi_fields.get(pos,[])
            else:
                for f in val:
                    res2 = self._columns[f].get(cr, self, ids, f, user, context=context, values=res)
                    for record in res:
                        if res2:
                            record[f] = res2[record['id']]
                        else:
                            record[f] = []

        # Warn about deprecated fields now that fields_pre and fields_post are computed
        # Explicitly use list() because we may receive tuples
        for f in list(fields_pre) + list(fields_post):
            field_column = self._all_columns.get(f) and self._all_columns.get(f).column
            if field_column and field_column.deprecated:
                _logger.warning('Field %s.%s is deprecated: %s', self._name, f, field_column.deprecated)

        readonly = None
        for vals in res:
            for field in vals.keys():
                fobj = None
                if field in self._columns:
                    fobj = self._columns[field]

                if fobj:
                    groups = fobj.read
                    if groups:
                        edit = False
                        for group in groups:
                            module = group.split(".")[0]
                            grp = group.split(".")[1]
                            cr.execute("select count(*) from res_groups_users_rel where gid IN (select res_id from ir_model_data where name=%s and module=%s and model=%s) and uid=%s",  \
                                       (grp, module, 'res.groups', user))
                            readonly = cr.fetchall()
                            if readonly[0][0] >= 1:
                                edit = True
                                break
                            elif readonly[0][0] == 0:
                                edit = False
                            else:
                                edit = False

                        if not edit:
                            if type(vals[field]) == type([]):
                                vals[field] = []
                            elif type(vals[field]) == type(0.0):
                                vals[field] = 0
                            elif type(vals[field]) == type(''):
                                vals[field] = '=No Permission='
                            else:
                                vals[field] = False

                if vals[field] is None:
                    vals[field] = False

        return res

    # TODO check READ access
    def perm_read(self, cr, user, ids, context=None, details=True):
        """
        Returns some metadata about the given records.

        :param details: if True, \*_uid fields are replaced with the name of the user
        :return: list of ownership dictionaries for each requested record
        :rtype: list of dictionaries with the following keys:

                    * id: object id
                    * create_uid: user who created the record
                    * create_date: date when the record was created
                    * write_uid: last user who changed the record
                    * write_date: date of the last change to the record
                    * xmlid: XML ID to use to refer to this record (if there is one), in format ``module.name``
        """
        if not context:
            context = {}
        if not ids:
            return []
        fields = ''
        uniq = isinstance(ids, (int, long))
        if uniq:
            ids = [ids]
        fields = ['id']
        if self._log_access:
            fields += ['create_uid', 'create_date', 'write_uid', 'write_date']
        quoted_table = '"%s"' % self._table
        fields_str = ",".join('%s.%s'%(quoted_table, field) for field in fields)
        query = '''SELECT %s, __imd.module, __imd.name
                   FROM %s LEFT JOIN ir_model_data __imd
                       ON (__imd.model = %%s and __imd.res_id = %s.id)
                   WHERE %s.id IN %%s''' % (fields_str, quoted_table, quoted_table, quoted_table)
        cr.execute(query, (self._name, tuple(ids)))
        res = cr.dictfetchall()
        for r in res:
            for key in r:
                r[key] = r[key] or False
                if details and key in ('write_uid', 'create_uid') and r[key]:
                    try:
                        r[key] = self.pool.get('res.users').name_get(cr, user, [r[key]])[0]
                    except Exception:
                        pass # Leave the numeric uid there
            r['xmlid'] = ("%(module)s.%(name)s" % r) if r['name'] else False
            del r['name'], r['module']
        if uniq:
            return res[ids[0]]
        return res

    def _check_concurrency(self, cr, ids, context):
        if not context:
            return
        if not (context.get(self.CONCURRENCY_CHECK_FIELD) and self._log_access):
            return
        check_clause = "(id = %s AND %s < COALESCE(write_date, create_date, (now() at time zone 'UTC'))::timestamp)"
        for sub_ids in cr.split_for_in_conditions(ids):
            ids_to_check = []
            for id in sub_ids:
                id_ref = "%s,%s" % (self._name, id)
                update_date = context[self.CONCURRENCY_CHECK_FIELD].pop(id_ref, None)
                if update_date:
                    ids_to_check.extend([id, update_date])
            if not ids_to_check:
                continue
            cr.execute("SELECT id FROM %s WHERE %s" % (self._table, " OR ".join([check_clause]*(len(ids_to_check)/2))), tuple(ids_to_check))
            res = cr.fetchone()
            if res:
                # mention the first one only to keep the error message readable
                raise except_orm('ConcurrencyException', _('A document was modified since you last viewed it (%s:%d)') % (self._description, res[0]))

    def _check_record_rules_result_count(self, cr, uid, ids, result_ids, operation, context=None):
        """Verify the returned rows after applying record rules matches
           the length of `ids`, and raise an appropriate exception if it does not.
        """
        ids, result_ids = set(ids), set(result_ids)
        missing_ids = ids - result_ids
        if missing_ids:
            # Attempt to distinguish record rule restriction vs deleted records,
            # to provide a more specific error message - check if the missinf
            cr.execute('SELECT id FROM ' + self._table + ' WHERE id IN %s', (tuple(missing_ids),))
            forbidden_ids = [x[0] for x in cr.fetchall()]
            if forbidden_ids:
                # the missing ids are (at least partially) hidden by access rules
                if uid == SUPERUSER_ID:
                    return
                _logger.warning('Access Denied by record rules for operation: %s on record ids: %r, uid: %s, model: %s', operation, forbidden_ids, uid, self._name)
                raise except_orm(_('Access Denied'),
                                 _('The requested operation cannot be completed due to security restrictions. Please contact your system administrator.\n\n(Document type: %s, Operation: %s)') % \
                                    (self._description, operation))
            else:
                # If we get here, the missing_ids are not in the database
                if operation in ('read','unlink'):
                    # No need to warn about deleting an already deleted record.
                    # And no error when reading a record that was deleted, to prevent spurious
                    # errors for non-transactional search/read sequences coming from clients
                    return
                _logger.warning('Failed operation on deleted record(s): %s, uid: %s, model: %s', operation, uid, self._name)
                raise except_orm(_('Missing document(s)'),
                                 _('One of the documents you are trying to access has been deleted, please try again after refreshing.'))


    def check_access_rights(self, cr, uid, operation, raise_exception=True): # no context on purpose.
        """Verifies that the operation given by ``operation`` is allowed for the user
           according to the access rights."""
        return self.pool.get('ir.model.access').check(cr, uid, self._name, operation, raise_exception)

    def check_access_rule(self, cr, uid, ids, operation, context=None):
        """Verifies that the operation given by ``operation`` is allowed for the user
           according to ir.rules.

           :param operation: one of ``write``, ``unlink``
           :raise except_orm: * if current ir.rules do not permit this operation.
           :return: None if the operation is allowed
        """
        if uid == SUPERUSER_ID:
            return

        if self.is_transient():
            # Only one single implicit access rule for transient models: owner only!
            # This is ok to hardcode because we assert that TransientModels always
            # have log_access enabled so that the create_uid column is always there.
            # And even with _inherits, these fields are always present in the local
            # table too, so no need for JOINs.
            cr.execute("""SELECT distinct create_uid
                          FROM %s
                          WHERE id IN %%s""" % self._table, (tuple(ids),))
            uids = [x[0] for x in cr.fetchall()]
            if len(uids) != 1 or uids[0] != uid:
                raise except_orm(_('Access Denied'),
                                 _('For this kind of document, you may only access records you created yourself.\n\n(Document type: %s)') % (self._description,))
        else:
            where_clause, where_params, tables = self.pool.get('ir.rule').domain_get(cr, uid, self._name, operation, context=context)
            if where_clause:
                where_clause = ' and ' + ' and '.join(where_clause)
                for sub_ids in cr.split_for_in_conditions(ids):
                    cr.execute('SELECT ' + self._table + '.id FROM ' + ','.join(tables) +
                               ' WHERE ' + self._table + '.id IN %s' + where_clause,
                               [sub_ids] + where_params)
                    returned_ids = [x['id'] for x in cr.dictfetchall()]
                    self._check_record_rules_result_count(cr, uid, sub_ids, returned_ids, operation, context=context)

    def create_workflow(self, cr, uid, ids, context=None):
        """Create a workflow instance for each given record IDs."""
        from openerp import workflow
        for res_id in ids:
            workflow.trg_create(uid, self._name, res_id, cr)
        # self.invalidate_cache() ?
        return True

    def delete_workflow(self, cr, uid, ids, context=None):
        """Delete the workflow instances bound to the given record IDs."""
        from openerp import workflow
        for res_id in ids:
            workflow.trg_delete(uid, self._name, res_id, cr)
        self.invalidate_cache()
        return True

    def step_workflow(self, cr, uid, ids, context=None):
        """Reevaluate the workflow instances of the given record IDs."""
        from openerp import workflow
        for res_id in ids:
            workflow.trg_write(uid, self._name, res_id, cr)
        # self.invalidate_cache() ?
        return True

    def signal_workflow(self, cr, uid, ids, signal, context=None):
        """Send given workflow signal and return a dict mapping ids to workflow results"""
        from openerp import workflow
        result = {}
        for res_id in ids:
            result[res_id] = workflow.trg_validate(uid, self._name, res_id, signal, cr)
        # self.invalidate_cache() ?
        return result

    def redirect_workflow(self, cr, uid, old_new_ids, context=None):
        """ Rebind the workflow instance bound to the given 'old' record IDs to
            the given 'new' IDs. (``old_new_ids`` is a list of pairs ``(old, new)``.
        """
        from openerp import workflow
        for old_id, new_id in old_new_ids:
            workflow.trg_redirect(uid, self._name, old_id, new_id, cr)
        self.invalidate_cache()
        return True

    def unlink(self, cr, uid, ids, context=None):
        """
        Delete records with given ids

        :param cr: database cursor
        :param uid: current user id
        :param ids: id or list of ids
        :param context: (optional) context arguments, like lang, time zone
        :return: True
        :raise AccessError: * if user has no unlink rights on the requested object
                            * if user tries to bypass access rules for unlink on the requested object
        :raise UserError: if the record is default property for other records

        """
        if not ids:
            return True
        if isinstance(ids, (int, long)):
            ids = [ids]

        result_store = self._store_get_values(cr, uid, ids, self._all_columns.keys(), context)

        # for recomputing new-style fields
        recs = self.browse(ids)
        recs.modified(self._all_columns)

        self._check_concurrency(cr, ids, context)

        self.check_access_rights(cr, uid, 'unlink')

        ir_property = self.pool.get('ir.property')

        # Check if the records are used as default properties.
        domain = [('res_id', '=', False),
                  ('value_reference', 'in', ['%s,%s' % (self._name, i) for i in ids]),
                 ]
        if ir_property.search(cr, uid, domain, context=context):
            raise except_orm(_('Error'), _('Unable to delete this document because it is used as a default property'))

        # Delete the records' properties.
        property_ids = ir_property.search(cr, uid, [('res_id', 'in', ['%s,%s' % (self._name, i) for i in ids])], context=context)
        ir_property.unlink(cr, uid, property_ids, context=context)

        self.delete_workflow(cr, uid, ids, context=context)

        self.check_access_rule(cr, uid, ids, 'unlink', context=context)
        pool_model_data = self.pool.get('ir.model.data')
        ir_values_obj = self.pool.get('ir.values')
        for sub_ids in cr.split_for_in_conditions(ids):
            cr.execute('delete from ' + self._table + ' ' \
                       'where id IN %s', (sub_ids,))

            # Removing the ir_model_data reference if the record being deleted is a record created by xml/csv file,
            # as these are not connected with real database foreign keys, and would be dangling references.
            # Note: following steps performed as admin to avoid access rights restrictions, and with no context
            #       to avoid possible side-effects during admin calls.
            # Step 1. Calling unlink of ir_model_data only for the affected IDS
            reference_ids = pool_model_data.search(cr, SUPERUSER_ID, [('res_id','in',list(sub_ids)),('model','=',self._name)])
            # Step 2. Marching towards the real deletion of referenced records
            if reference_ids:
                pool_model_data.unlink(cr, SUPERUSER_ID, reference_ids)

            # For the same reason, removing the record relevant to ir_values
            ir_value_ids = ir_values_obj.search(cr, uid,
                    ['|',('value','in',['%s,%s' % (self._name, sid) for sid in sub_ids]),'&',('res_id','in',list(sub_ids)),('model','=',self._name)],
                    context=context)
            if ir_value_ids:
                ir_values_obj.unlink(cr, uid, ir_value_ids, context=context)

        # invalidate the *whole* cache, since the orm does not handle all
        # changes made in the database, like cascading delete!
        self.invalidate_cache()

        for order, obj_name, store_ids, fields in result_store:
            if obj_name != self._name:
                obj = self.pool[obj_name]
                cr.execute('select id from '+obj._table+' where id IN %s', (tuple(store_ids),))
                rids = map(lambda x: x[0], cr.fetchall())
                if rids:
                    obj._store_set_values(cr, uid, rids, fields, context)

        # recompute new-style fields
        recs.recompute()

        return True

    #
    # TODO: Validate
    #
    @api.multi
    def write(self, vals):
        """
        Update records in `self` with the given field values.

        :param vals: field values to update, e.g {'field_name': new_field_value, ...}
        :type vals: dictionary
        :return: True
        :raise AccessError: * if user has no write rights on the requested object
                            * if user tries to bypass access rules for write on the requested object
        :raise ValidateError: if user tries to enter invalid value for a field that is not in selection
        :raise UserError: if a loop would be created in a hierarchy of objects a result of the operation (such as setting an object as its own parent)

        **Note**: The type of field values to pass in ``vals`` for relationship fields is specific:

            + For a many2many field, a list of tuples is expected.
              Here is the list of tuple that are accepted, with the corresponding semantics ::

                 (0, 0,  { values })    link to a new record that needs to be created with the given values dictionary
                 (1, ID, { values })    update the linked record with id = ID (write *values* on it)
                 (2, ID)                remove and delete the linked record with id = ID (calls unlink on ID, that will delete the object completely, and the link to it as well)
                 (3, ID)                cut the link to the linked record with id = ID (delete the relationship between the two objects but does not delete the target object itself)
                 (4, ID)                link to existing record with id = ID (adds a relationship)
                 (5)                    unlink all (like using (3,ID) for all linked records)
                 (6, 0, [IDs])          replace the list of linked IDs (like using (5) then (4,ID) for each ID in the list of IDs)

                 Example:
                    [(6, 0, [8, 5, 6, 4])] sets the many2many to ids [8, 5, 6, 4]

            + For a one2many field, a lits of tuples is expected.
              Here is the list of tuple that are accepted, with the corresponding semantics ::

                 (0, 0,  { values })    link to a new record that needs to be created with the given values dictionary
                 (1, ID, { values })    update the linked record with id = ID (write *values* on it)
                 (2, ID)                remove and delete the linked record with id = ID (calls unlink on ID, that will delete the object completely, and the link to it as well)

                 Example:
                    [(0, 0, {'field_name':field_value_record1, ...}), (0, 0, {'field_name':field_value_record2, ...})]

            + For a many2one field, simply use the ID of target record, which must already exist, or ``False`` to remove the link.
            + For a reference field, use a string with the model name, a comma, and the target object id (example: ``'product.product, 5'``)

        """
        if not self:
            return True

        cr, uid, context = scope_proxy.args
        self._check_concurrency(cr, self._ids, context)
        self.check_access_rights(cr, uid, 'write')

        # No user-driven update of these columns
        for field in itertools.chain(MAGIC_COLUMNS, ('parent_left', 'parent_right')):
            vals.pop(field, None)

        # split up fields into old-style and pure new-style ones
        old_vals, new_vals, unknown = {}, {}, []
        for key, val in vals.iteritems():
            if key in self._columns:
                old_vals[key] = val
            elif key in self._fields:
                new_vals[key] = val
            else:
                unknown.append(key)

        if unknown:
            _logger.warning("%s.write() with unknown fields: %s", self._name, ', '.join(sorted(unknown)))

        # write old-style fields with (low-level) method _write
        if old_vals:
            self._write(old_vals)

        # put the values of pure new-style fields into cache, and inverse them
        if new_vals:
            for record in self:
                record._update_cache(new_vals)
            for key in new_vals:
                self._fields[key].determine_inverse(self)

        return True

    def _write(self, cr, user, ids, vals, context=None):
        # low-level implementation of write()
        if not context:
            context = {}

        readonly = None
        self.check_field_access_rights(cr, user, 'write', vals.keys())
        for field in vals.keys():
            fobj = None
            if field in self._columns:
                fobj = self._columns[field]
            elif field in self._inherit_fields:
                fobj = self._inherit_fields[field][2]
            if not fobj:
                continue
            groups = fobj.write

            if groups:
                edit = False
                for group in groups:
                    module = group.split(".")[0]
                    grp = group.split(".")[1]
                    cr.execute("select count(*) from res_groups_users_rel where gid IN (select res_id from ir_model_data where name=%s and module=%s and model=%s) and uid=%s", \
                               (grp, module, 'res.groups', user))
                    readonly = cr.fetchall()
                    if readonly[0][0] >= 1:
                        edit = True
                        break

                if not edit:
                    vals.pop(field)

        result = self._store_get_values(cr, user, ids, vals.keys(), context) or []

        # for recomputing new-style fields
        recs = self.browse(ids)
        recs.modified(vals)

        parents_changed = []
        parent_order = self._parent_order or self._order
        if self._parent_store and (self._parent_name in vals):
            # The parent_left/right computation may take up to
            # 5 seconds. No need to recompute the values if the
            # parent is the same.
            # Note: to respect parent_order, nodes must be processed in
            # order, so ``parents_changed`` must be ordered properly.
            parent_val = vals[self._parent_name]
            if parent_val:
                query = "SELECT id FROM %s WHERE id IN %%s AND (%s != %%s OR %s IS NULL) ORDER BY %s" % \
                                (self._table, self._parent_name, self._parent_name, parent_order)
                cr.execute(query, (tuple(ids), parent_val))
            else:
                query = "SELECT id FROM %s WHERE id IN %%s AND (%s IS NOT NULL) ORDER BY %s" % \
                                (self._table, self._parent_name, parent_order)
                cr.execute(query, (tuple(ids),))
            parents_changed = map(operator.itemgetter(0), cr.fetchall())

        upd0 = []
        upd1 = []
        upd_todo = []
        updend = []
        direct = []
        totranslate = context.get('lang', False) and (context['lang'] != 'en_US')
        for field in vals:
            field_column = self._all_columns.get(field) and self._all_columns.get(field).column
            if field_column and field_column.deprecated:
                _logger.warning('Field %s.%s is deprecated: %s', self._name, field, field_column.deprecated)
            if field in self._columns:
                if self._columns[field]._classic_write and not (hasattr(self._columns[field], '_fnct_inv')):
                    if (not totranslate) or not self._columns[field].translate:
                        upd0.append('"'+field+'"='+self._columns[field]._symbol_set[0])
                        upd1.append(self._columns[field]._symbol_set[1](vals[field]))
                    direct.append(field)
                else:
                    upd_todo.append(field)
            else:
                updend.append(field)
            if field in self._columns \
                    and hasattr(self._columns[field], 'selection') \
                    and vals[field]:
                self._check_selection_field_value(cr, user, field, vals[field], context=context)

        if self._log_access:
            upd0.append('write_uid=%s')
            upd0.append("write_date=(now() at time zone 'UTC')")
            upd1.append(user)
            recs.modified(('write_uid', 'write_date'))

        if len(upd0):
            self.check_access_rule(cr, user, ids, 'write', context=context)
            for sub_ids in cr.split_for_in_conditions(ids):
                cr.execute('update ' + self._table + ' set ' + ','.join(upd0) + ' ' \
                           'where id IN %s', upd1 + [sub_ids])
                if cr.rowcount != len(sub_ids):
                    raise except_orm(_('AccessError'),
                                     _('One of the records you are trying to modify has already been deleted (Document type: %s).') % self._description)

            if totranslate:
                # TODO: optimize
                for f in direct:
                    if self._columns[f].translate:
                        src_trans = self.pool[self._name].read(cr, user, ids, [f])[0][f]
                        if not src_trans:
                            src_trans = vals[f]
                            # Inserting value to DB
                            self.write(cr, user, ids, {f: vals[f]})
                        self.pool.get('ir.translation')._set_ids(cr, user, self._name+','+f, 'model', context['lang'], ids, vals[f], src_trans)

        # call the 'set' method of fields which are not classic_write
        upd_todo.sort(lambda x, y: self._columns[x].priority-self._columns[y].priority)

        # default element in context must be removed when call a one2many or many2many
        rel_context = context.copy()
        for c in context.items():
            if c[0].startswith('default_'):
                del rel_context[c[0]]

        for field in upd_todo:
            for id in ids:
                result += self._columns[field].set(cr, self, id, field, vals[field], user, context=rel_context) or []

        unknown_fields = updend[:]
        for table in self._inherits:
            col = self._inherits[table]
            nids = []
            for sub_ids in cr.split_for_in_conditions(ids):
                cr.execute('select distinct "'+col+'" from "'+self._table+'" ' \
                           'where id IN %s', (sub_ids,))
                nids.extend([x[0] for x in cr.fetchall()])

            v = {}
            for val in updend:
                if self._inherit_fields[val][0] == table:
                    v[val] = vals[val]
                    unknown_fields.remove(val)
            if v:
                self.pool[table].write(cr, user, nids, v, context)

        if unknown_fields:
            _logger.warning(
                'No such field(s) in model %s: %s.',
                self._name, ', '.join(unknown_fields))

        # check Python constraints
        recs._validate_fields(vals)

        # TODO: use _order to set dest at the right position and not first node of parent
        # We can't defer parent_store computation because the stored function
        # fields that are computer may refer (directly or indirectly) to
        # parent_left/right (via a child_of domain)
        if parents_changed:
            if self.pool._init:
                self.pool._init_parent[self._name] = True
            else:
                order = self._parent_order or self._order
                parent_val = vals[self._parent_name]
                if parent_val:
                    clause, params = '%s=%%s' % (self._parent_name,), (parent_val,)
                else:
                    clause, params = '%s IS NULL' % (self._parent_name,), ()

                for id in parents_changed:
                    cr.execute('SELECT parent_left, parent_right FROM %s WHERE id=%%s' % (self._table,), (id,))
                    pleft, pright = cr.fetchone()
                    distance = pright - pleft + 1

                    # Positions of current siblings, to locate proper insertion point;
                    # this can _not_ be fetched outside the loop, as it needs to be refreshed
                    # after each update, in case several nodes are sequentially inserted one
                    # next to the other (i.e computed incrementally)
                    cr.execute('SELECT parent_right, id FROM %s WHERE %s ORDER BY %s' % (self._table, clause, parent_order), params)
                    parents = cr.fetchall()

                    # Find Position of the element
                    position = None
                    for (parent_pright, parent_id) in parents:
                        if parent_id == id:
                            break
                        position = parent_pright + 1

                    # It's the first node of the parent
                    if not position:
                        if not parent_val:
                            position = 1
                        else:
                            cr.execute('select parent_left from '+self._table+' where id=%s', (parent_val,))
                            position = cr.fetchone()[0] + 1

                    if pleft < position <= pright:
                        raise except_orm(_('UserError'), _('Recursivity Detected.'))

                    if pleft < position:
                        cr.execute('update '+self._table+' set parent_left=parent_left+%s where parent_left>=%s', (distance, position))
                        cr.execute('update '+self._table+' set parent_right=parent_right+%s where parent_right>=%s', (distance, position))
                        cr.execute('update '+self._table+' set parent_left=parent_left+%s, parent_right=parent_right+%s where parent_left>=%s and parent_left<%s', (position-pleft, position-pleft, pleft, pright))
                    else:
                        cr.execute('update '+self._table+' set parent_left=parent_left+%s where parent_left>=%s', (distance, position))
                        cr.execute('update '+self._table+' set parent_right=parent_right+%s where parent_right>=%s', (distance, position))
                        cr.execute('update '+self._table+' set parent_left=parent_left-%s, parent_right=parent_right-%s where parent_left>=%s and parent_left<%s', (pleft-position+distance, pleft-position+distance, pleft+distance, pright+distance))
                    self.invalidate_cache(['parent_left', 'parent_right'])

        result += self._store_get_values(cr, user, ids, vals.keys(), context)
        result.sort()

        # for recomputing new-style fields
        recs.modified(vals)
        if self._log_access:
            recs.modified(('write_uid', 'write_date'))

        done = {}
        for order, model_name, ids_to_update, fields_to_recompute in result:
            key = (model_name, tuple(fields_to_recompute))
            done.setdefault(key, {})
            # avoid to do several times the same computation
            todo = []
            for id in ids_to_update:
                if id not in done[key]:
                    done[key][id] = True
                    todo.append(id)
            self.pool[model_name]._store_set_values(cr, user, todo, fields_to_recompute, context)

        # recompute new-style fields
        recs.recompute()

        self.step_workflow(cr, user, ids, context=context)
        return True

    #
    # TODO: Should set perm to user.xxx
    #
    @api.model
    @api.returns('self', lambda self, value: value.id)
    def create(self, vals):
        """ Create a new record for the model.

            The values for the new record are initialized using the dictionary
            `vals`, and if necessary the result of :meth:`default_get`.

            :param vals: field values like ``{'field_name': field_value, ...}``,
                see :meth:`write` for details about the values format
            :return: new record created
            :raise AccessError: * if user has no create rights on the requested object
                                * if user tries to bypass access rules for create on the requested object
            :raise ValidateError: if user tries to enter invalid value for a field that is not in selection
            :raise UserError: if a loop would be created in a hierarchy of objects a result of the operation (such as setting an object as its own parent)
        """
        self.check_access_rights('create')

        # add missing defaults, and drop fields that may not be set by user
        vals = self._add_missing_default_values(vals)
        for field in itertools.chain(MAGIC_COLUMNS, ('parent_left', 'parent_right')):
            vals.pop(field, None)

        # split up fields into old-style and pure new-style ones
        old_vals, new_vals, unknown = {}, {}, []
        for key, val in vals.iteritems():
            if key in self._all_columns:
                old_vals[key] = val
            elif key in self._fields:
                new_vals[key] = val
            else:
                unknown.append(key)

        if unknown:
            _logger.warning("%s.create() with unknown fields: %s", self._name, ', '.join(sorted(unknown)))

        # create record with old-style fields
        record = self.browse(self._create(old_vals))

        # put the values of pure new-style fields into cache, and inverse them
        record._update_cache(new_vals)
        for key in new_vals:
            self._fields[key].determine_inverse(record)

        return record

    def _create(self, cr, user, vals, context=None):
        # low-level implementation of create()
        if not context:
            context = {}

        if self.is_transient():
            self._transient_vacuum(cr, user)

        tocreate = {}
        for v in self._inherits:
            if self._inherits[v] not in vals:
                tocreate[v] = {}
            else:
                tocreate[v] = {'id': vals[self._inherits[v]]}
        upd_todo = []
        unknown_fields = []
        for v in vals.keys():
            if v in self._inherit_fields and v not in self._columns:
                (table, col, col_detail, original_parent) = self._inherit_fields[v]
                tocreate[table][v] = vals[v]
                del vals[v]
            else:
                if (v not in self._inherit_fields) and (v not in self._columns):
                    del vals[v]
                    unknown_fields.append(v)
        if unknown_fields:
            _logger.warning(
                'No such field(s) in model %s: %s.',
                self._name, ', '.join(unknown_fields))

        # Try-except added to filter the creation of those records whose filds are readonly.
        # Example : any dashboard which has all the fields readonly.(due to Views(database views))
        try:
            cr.execute("SELECT nextval('"+self._sequence+"')")
        except:
            raise except_orm(_('UserError'),
                _('You cannot perform this operation. New Record Creation is not allowed for this object as this object is for reporting purpose.'))

        id_new = cr.fetchone()[0]
        (upd0, upd1, upd2) = (['id'], [str(id_new)], [])
        for table in tocreate:
            if self._inherits[table] in vals:
                del vals[self._inherits[table]]

            record_id = tocreate[table].pop('id', None)

            # When linking/creating parent records, force context without 'no_store_function' key that
            # defers stored functions computing, as these won't be computed in batch at the end of create().
            parent_context = dict(context)
            parent_context.pop('no_store_function', None)

            if record_id is None or not record_id:
                record_id = self.pool[table].create(cr, user, tocreate[table], context=parent_context)
            else:
                self.pool[table].write(cr, user, [record_id], tocreate[table], context=parent_context)

            upd0.append(self._inherits[table])
            upd1.append('%s')
            upd2.append(record_id)

        #Start : Set bool fields to be False if they are not touched(to make search more powerful)
        bool_fields = [x for x in self._columns.keys() if self._columns[x]._type=='boolean']

        for bool_field in bool_fields:
            if bool_field not in vals:
                vals[bool_field] = False
        #End
        for field in vals.keys():
            fobj = None
            if field in self._columns:
                fobj = self._columns[field]
            else:
                fobj = self._inherit_fields[field][2]
            if not fobj:
                continue
            groups = fobj.write
            if groups:
                edit = False
                for group in groups:
                    module = group.split(".")[0]
                    grp = group.split(".")[1]
                    cr.execute("select count(*) from res_groups_users_rel where gid IN (select res_id from ir_model_data where name='%s' and module='%s' and model='%s') and uid=%s" % \
                               (grp, module, 'res.groups', user))
                    readonly = cr.fetchall()
                    if readonly[0][0] >= 1:
                        edit = True
                        break
                    elif readonly[0][0] == 0:
                        edit = False
                    else:
                        edit = False

                if not edit:
                    vals.pop(field)
        for field in vals:
            if self._columns[field]._classic_write:
                upd0.append('"%s"' % field)
                upd1.append(self._columns[field]._symbol_set[0])
                upd2.append(self._columns[field]._symbol_set[1](vals[field]))
                #for the function fields that receive a value, we set them directly in the database
                #(they may be required), but we also need to trigger the _fct_inv()
                if (hasattr(self._columns[field], '_fnct_inv')) and not isinstance(self._columns[field], fields.related):
                    #TODO: this way to special case the related fields is really creepy but it shouldn't be changed at
                    #one week of the release candidate. It seems the only good way to handle correctly this is to add an
                    #attribute to make a field `really readonly´ and thus totally ignored by the create()... otherwise
                    #if, for example, the related has a default value (for usability) then the fct_inv is called and it
                    #may raise some access rights error. Changing this is a too big change for now, and is thus postponed
                    #after the release but, definitively, the behavior shouldn't be different for related and function
                    #fields.
                    upd_todo.append(field)
            else:
                #TODO: this `if´ statement should be removed because there is no good reason to special case the fields
                #related. See the above TODO comment for further explanations.
                if not isinstance(self._columns[field], fields.related):
                    upd_todo.append(field)
            if field in self._columns \
                    and hasattr(self._columns[field], 'selection') \
                    and vals[field]:
                self._check_selection_field_value(cr, user, field, vals[field], context=context)
        if self._log_access:
            upd0.extend(('create_uid', 'create_date', 'write_uid', 'write_date'))
            upd1.extend(("%s","(now() at time zone 'UTC')","%s","(now() at time zone 'UTC')"))
            upd2.extend((user, user))
        cr.execute('insert into "' +self._table + '" '
                     '(' + ','.join(upd0) + ') '
                     'values (' + ','.join(upd1) + ')',
                   tuple(upd2))
        upd_todo.sort(lambda x, y: self._columns[x].priority-self._columns[y].priority)

        if self._parent_store and not context.get('defer_parent_store_computation'):
            if self.pool._init:
                self.pool._init_parent[self._name] = True
            else:
                parent = vals.get(self._parent_name, False)
                if parent:
                    cr.execute('select parent_right from '+self._table+' where '+self._parent_name+'=%s order by '+(self._parent_order or self._order), (parent,))
                    pleft_old = None
                    result_p = cr.fetchall()
                    for (pleft,) in result_p:
                        if not pleft:
                            break
                        pleft_old = pleft
                    if not pleft_old:
                        cr.execute('select parent_left from '+self._table+' where id=%s', (parent,))
                        pleft_old = cr.fetchone()[0]
                    pleft = pleft_old
                else:
                    cr.execute('select max(parent_right) from '+self._table)
                    pleft = cr.fetchone()[0] or 0
                cr.execute('update '+self._table+' set parent_left=parent_left+2 where parent_left>%s', (pleft,))
                cr.execute('update '+self._table+' set parent_right=parent_right+2 where parent_right>%s', (pleft,))
                cr.execute('update '+self._table+' set parent_left=%s,parent_right=%s where id=%s', (pleft+1, pleft+2, id_new))
                self.invalidate_cache(['parent_left', 'parent_right'])

        # default element in context must be remove when call a one2many or many2many
        rel_context = context.copy()
        for c in context.items():
            if c[0].startswith('default_'):
                del rel_context[c[0]]

        result = []
        for field in upd_todo:
            result += self._columns[field].set(cr, self, id_new, field, vals[field], user, rel_context) or []

        # check Python constraints
        recs = self.browse(id_new)
        recs._validate_fields(vals)

        if not context.get('no_store_function', False):
            result += self._store_get_values(cr, user, [id_new], vals.keys(), context)
            result.sort()
            done = []
            for order, model_name, ids, fields2 in result:
                if not (model_name, ids, fields2) in done:
                    self.pool[model_name]._store_set_values(cr, user, ids, fields2, context)
                    done.append((model_name, ids, fields2))

            # recompute new-style fields
            recs.modified(vals)
            if self._log_access:
                recs.modified(('create_uid', 'create_date', 'write_uid', 'write_date'))
            recs.recompute()

        if self._log_create and not (context and context.get('no_store_function', False)):
            message = self._description + \
                " '" + \
                self.name_get(cr, user, [id_new], context=context)[0][1] + \
                "' " + _("created.")
            self.log(cr, user, id_new, message, True, context=context)

        self.check_access_rule(cr, user, [id_new], 'create', context=context)
        self.create_workflow(cr, user, [id_new], context=context)
        return id_new

    def _store_get_values(self, cr, uid, ids, fields, context):
        """Returns an ordered list of fields.functions to call due to
           an update operation on ``fields`` of records with ``ids``,
           obtained by calling the 'store' functions of these fields,
           as setup by their 'store' attribute.

           :return: [(priority, model_name, [record_ids,], [function_fields,])]
        """
        if fields is None: fields = []
        stored_functions = self.pool._store_function.get(self._name, [])

        # use indexed names for the details of the stored_functions:
        model_name_, func_field_to_compute_, id_mapping_fnct_, trigger_fields_, priority_ = range(5)

        # only keep functions that should be triggered for the ``fields``
        # being written to.
        to_compute = [f for f in stored_functions \
                if ((not f[trigger_fields_]) or set(fields).intersection(f[trigger_fields_]))]

        mapping = {}
        for function in to_compute:
            # use admin user for accessing objects having rules defined on store fields
            target_ids = [id for id in function[id_mapping_fnct_](self, cr, SUPERUSER_ID, ids, context) if id]

            # the compound key must consider the priority and model name
            key = (function[priority_], function[model_name_])
            for target_id in target_ids:
                mapping.setdefault(key, {}).setdefault(target_id,set()).add(tuple(function))

        # Here mapping looks like:
        # { (10, 'model_a') : { target_id1: [ (function_1_tuple, function_2_tuple) ], ... }
        #   (20, 'model_a') : { target_id2: [ (function_3_tuple, function_4_tuple) ], ... }
        #   (99, 'model_a') : { target_id1: [ (function_5_tuple, function_6_tuple) ], ... }
        # }

        # Now we need to generate the batch function calls list
        # call_map =
        #   { (10, 'model_a') : [(10, 'model_a', [record_ids,], [function_fields,])] }
        call_map = {}
        for ((priority,model), id_map) in mapping.iteritems():
            functions_ids_maps = {}
            # function_ids_maps =
            #   { (function_1_tuple, function_2_tuple) : [target_id1, target_id2, ..] }
            for id, functions in id_map.iteritems():
                functions_ids_maps.setdefault(tuple(functions), []).append(id)
            for functions, ids in functions_ids_maps.iteritems():
                call_map.setdefault((priority,model),[]).append((priority, model, ids,
                                                                 [f[func_field_to_compute_] for f in functions]))
        ordered_keys = call_map.keys()
        ordered_keys.sort()
        result = []
        if ordered_keys:
            result = reduce(operator.add, (call_map[k] for k in ordered_keys))
        return result

    def _store_set_values(self, cr, uid, ids, fields, context):
        """Calls the fields.function's "implementation function" for all ``fields``, on records with ``ids`` (taking care of
           respecting ``multi`` attributes), and stores the resulting values in the database directly."""
        if not ids:
            return True
        field_flag = False
        field_dict = {}
        if self._log_access:
            cr.execute('select id,write_date from '+self._table+' where id IN %s', (tuple(ids),))
            res = cr.fetchall()
            for r in res:
                if r[1]:
                    field_dict.setdefault(r[0], [])
                    res_date = time.strptime((r[1])[:19], '%Y-%m-%d %H:%M:%S')
                    write_date = datetime.datetime.fromtimestamp(time.mktime(res_date))
                    for i in self.pool._store_function.get(self._name, []):
                        if i[5]:
                            up_write_date = write_date + datetime.timedelta(hours=i[5])
                            if datetime.datetime.now() < up_write_date:
                                if i[1] in fields:
                                    field_dict[r[0]].append(i[1])
                                    if not field_flag:
                                        field_flag = True
        todo = {}
        keys = []
        for f in fields:
            if self._columns[f]._multi not in keys:
                keys.append(self._columns[f]._multi)
            todo.setdefault(self._columns[f]._multi, [])
            todo[self._columns[f]._multi].append(f)
        for key in keys:
            val = todo[key]
            if key:
                # use admin user for accessing objects having rules defined on store fields
                result = self._columns[val[0]].get(cr, self, ids, val, SUPERUSER_ID, context=context)
                for id, value in result.items():
                    if field_flag:
                        for f in value.keys():
                            if f in field_dict[id]:
                                value.pop(f)
                    upd0 = []
                    upd1 = []
                    for v in value:
                        if v not in val:
                            continue
                        if self._columns[v]._type == 'many2one':
                            try:
                                value[v] = value[v][0]
                            except:
                                pass
                        upd0.append('"'+v+'"='+self._columns[v]._symbol_set[0])
                        upd1.append(self._columns[v]._symbol_set[1](value[v]))
                    upd1.append(id)
                    if upd0 and upd1:
                        cr.execute('update "' + self._table + '" set ' + \
                            ','.join(upd0) + ' where id = %s', upd1)

            else:
                for f in val:
                    # use admin user for accessing objects having rules defined on store fields
                    result = self._columns[f].get(cr, self, ids, f, SUPERUSER_ID, context=context)
                    for r in result.keys():
                        if field_flag:
                            if r in field_dict.keys():
                                if f in field_dict[r]:
                                    result.pop(r)
                    for id, value in result.items():
                        if self._columns[f]._type == 'many2one':
                            try:
                                value = value[0]
                            except:
                                pass
                        cr.execute('update "' + self._table + '" set ' + \
                            '"'+f+'"='+self._columns[f]._symbol_set[0] + ' where id = %s', (self._columns[f]._symbol_set[1](value), id))

        # invalidate the cache for the modified fields
        self.browse(ids).modified(fields)

        return True

    #
    # TODO: Validate
    #
    def perm_write(self, cr, user, ids, fields, context=None):
        raise NotImplementedError(_('This method does not exist anymore'))

    # TODO: ameliorer avec NULL
    def _where_calc(self, cr, user, domain, active_test=True, context=None):
        """Computes the WHERE clause needed to implement an OpenERP domain.
        :param domain: the domain to compute
        :type domain: list
        :param active_test: whether the default filtering of records with ``active``
                            field set to ``False`` should be applied.
        :return: the query expressing the given domain as provided in domain
        :rtype: osv.query.Query
        """
        if not context:
            context = {}
        domain = domain[:]
        # if the object has a field named 'active', filter out all inactive
        # records unless they were explicitely asked for
        if 'active' in self._all_columns and (active_test and context.get('active_test', True)):
            if domain:
                # the item[0] trick below works for domain items and '&'/'|'/'!'
                # operators too
                if not any(item[0] == 'active' for item in domain):
                    domain.insert(0, ('active', '=', 1))
            else:
                domain = [('active', '=', 1)]

        if domain:
            e = expression.expression(cr, user, domain, self, context)
            tables = e.get_tables()
            where_clause, where_params = e.to_sql()
            where_clause = where_clause and [where_clause] or []
        else:
            where_clause, where_params, tables = [], [], ['"%s"' % self._table]

        return Query(tables, where_clause, where_params)

    def _check_qorder(self, word):
        if not regex_order.match(word):
            raise except_orm(_('AccessError'), _('Invalid "order" specified. A valid "order" specification is a comma-separated list of valid field names (optionally followed by asc/desc for the direction)'))
        return True

    def _apply_ir_rules(self, cr, uid, query, mode='read', context=None):
        """Add what's missing in ``query`` to implement all appropriate ir.rules
          (using the ``model_name``'s rules or the current model's rules if ``model_name`` is None)

           :param query: the current query object
        """
        def apply_rule(added_clause, added_params, added_tables, parent_model=None, child_object=None):
            """ :param string parent_model: string of the parent model
                :param model child_object: model object, base of the rule application
            """
            if added_clause:
                if parent_model and child_object:
                    # as inherited rules are being applied, we need to add the missing JOIN
                    # to reach the parent table (if it was not JOINed yet in the query)
                    parent_alias = child_object._inherits_join_add(child_object, parent_model, query)
                    # inherited rules are applied on the external table -> need to get the alias and replace
                    parent_table = self.pool[parent_model]._table
                    added_clause = [clause.replace('"%s"' % parent_table, '"%s"' % parent_alias) for clause in added_clause]
                    # change references to parent_table to parent_alias, because we now use the alias to refer to the table
                    new_tables = []
                    for table in added_tables:
                        # table is just a table name -> switch to the full alias
                        if table == '"%s"' % parent_table:
                            new_tables.append('"%s" as "%s"' % (parent_table, parent_alias))
                        # table is already a full statement -> replace reference to the table to its alias, is correct with the way aliases are generated
                        else:
                            new_tables.append(table.replace('"%s"' % parent_table, '"%s"' % parent_alias))
                    added_tables = new_tables
                query.where_clause += added_clause
                query.where_clause_params += added_params
                for table in added_tables:
                    if table not in query.tables:
                        query.tables.append(table)
                return True
            return False

        # apply main rules on the object
        rule_obj = self.pool.get('ir.rule')
        rule_where_clause, rule_where_clause_params, rule_tables = rule_obj.domain_get(cr, uid, self._name, mode, context=context)
        apply_rule(rule_where_clause, rule_where_clause_params, rule_tables)

        # apply ir.rules from the parents (through _inherits)
        for inherited_model in self._inherits:
            rule_where_clause, rule_where_clause_params, rule_tables = rule_obj.domain_get(cr, uid, inherited_model, mode, context=context)
            apply_rule(rule_where_clause, rule_where_clause_params, rule_tables,
                        parent_model=inherited_model, child_object=self)

    def _generate_m2o_order_by(self, order_field, query):
        """
        Add possibly missing JOIN to ``query`` and generate the ORDER BY clause for m2o fields,
        either native m2o fields or function/related fields that are stored, including
        intermediate JOINs for inheritance if required.

        :return: the qualified field name to use in an ORDER BY clause to sort by ``order_field``
        """
        if order_field not in self._columns and order_field in self._inherit_fields:
            # also add missing joins for reaching the table containing the m2o field
            qualified_field = self._inherits_join_calc(order_field, query)
            order_field_column = self._inherit_fields[order_field][2]
        else:
            qualified_field = '"%s"."%s"' % (self._table, order_field)
            order_field_column = self._columns[order_field]

        assert order_field_column._type == 'many2one', 'Invalid field passed to _generate_m2o_order_by()'
        if not order_field_column._classic_write and not getattr(order_field_column, 'store', False):
            _logger.debug("Many2one function/related fields must be stored " \
                "to be used as ordering fields! Ignoring sorting for %s.%s",
                self._name, order_field)
            return

        # figure out the applicable order_by for the m2o
        dest_model = self.pool[order_field_column._obj]
        m2o_order = dest_model._order
        if not regex_order.match(m2o_order):
            # _order is complex, can't use it here, so we default to _rec_name
            m2o_order = dest_model._rec_name
        else:
            # extract the field names, to be able to qualify them and add desc/asc
            m2o_order_list = []
            for order_part in m2o_order.split(","):
                m2o_order_list.append(order_part.strip().split(" ", 1)[0].strip())
            m2o_order = m2o_order_list

        # Join the dest m2o table if it's not joined yet. We use [LEFT] OUTER join here
        # as we don't want to exclude results that have NULL values for the m2o
        src_table, src_field = qualified_field.replace('"', '').split('.', 1)
        dst_alias, dst_alias_statement = query.add_join((src_table, dest_model._table, src_field, 'id', src_field), implicit=False, outer=True)
        qualify = lambda field: '"%s"."%s"' % (dst_alias, field)
        return map(qualify, m2o_order) if isinstance(m2o_order, list) else qualify(m2o_order)

    def _generate_order_by(self, order_spec, query):
        """
        Attempt to consruct an appropriate ORDER BY clause based on order_spec, which must be
        a comma-separated list of valid field names, optionally followed by an ASC or DESC direction.

        :raise" except_orm in case order_spec is malformed
        """
        order_by_clause = ''
        order_spec = order_spec or self._order
        if order_spec:
            order_by_elements = []
            self._check_qorder(order_spec)
            for order_part in order_spec.split(','):
                order_split = order_part.strip().split(' ')
                order_field = order_split[0].strip()
                order_direction = order_split[1].strip() if len(order_split) == 2 else ''
                inner_clause = None
                if order_field == 'id':
                    order_by_elements.append('"%s"."%s" %s' % (self._table, order_field, order_direction))
                elif order_field in self._columns:
                    order_column = self._columns[order_field]
                    if order_column._classic_read:
                        inner_clause = '"%s"."%s"' % (self._table, order_field)
                    elif order_column._type == 'many2one':
                        inner_clause = self._generate_m2o_order_by(order_field, query)
                    else:
                        continue  # ignore non-readable or "non-joinable" fields
                elif order_field in self._inherit_fields:
                    parent_obj = self.pool[self._inherit_fields[order_field][3]]
                    order_column = parent_obj._columns[order_field]
                    if order_column._classic_read:
                        inner_clause = self._inherits_join_calc(order_field, query)
                    elif order_column._type == 'many2one':
                        inner_clause = self._generate_m2o_order_by(order_field, query)
                    else:
                        continue  # ignore non-readable or "non-joinable" fields
                else:
                    raise ValueError( _("Sorting field %s not found on model %s") %( order_field, self._name))
                if inner_clause:
                    if isinstance(inner_clause, list):
                        for clause in inner_clause:
                            order_by_elements.append("%s %s" % (clause, order_direction))
                    else:
                        order_by_elements.append("%s %s" % (inner_clause, order_direction))
            if order_by_elements:
                order_by_clause = ",".join(order_by_elements)

        return order_by_clause and (' ORDER BY %s ' % order_by_clause) or ''

    def _search(self, cr, user, args, offset=0, limit=None, order=None, context=None, count=False, access_rights_uid=None):
        """
        Private implementation of search() method, allowing specifying the uid to use for the access right check.
        This is useful for example when filling in the selection list for a drop-down and avoiding access rights errors,
        by specifying ``access_rights_uid=1`` to bypass access rights check, but not ir.rules!
        This is ok at the security level because this method is private and not callable through XML-RPC.

        :param access_rights_uid: optional user ID to use when checking access rights
                                  (not for ir.rules, this is only for ir.model.access)
        """
        if context is None:
            context = {}
        self.check_access_rights(cr, access_rights_uid or user, 'read')

        # For transient models, restrict acces to the current user, except for the super-user
        if self.is_transient() and self._log_access and user != SUPERUSER_ID:
            args = expression.AND(([('create_uid', '=', user)], args or []))

        query = self._where_calc(cr, user, args, context=context)
        self._apply_ir_rules(cr, user, query, 'read', context=context)
        order_by = self._generate_order_by(order, query)
        from_clause, where_clause, where_clause_params = query.get_sql()

        limit_str = limit and ' limit %d' % limit or ''
        offset_str = offset and ' offset %d' % offset or ''
        where_str = where_clause and (" WHERE %s" % where_clause) or ''
        query_str = 'SELECT "%s".id FROM ' % self._table + from_clause + where_str + order_by + limit_str + offset_str

        if count:
            # /!\ the main query must be executed as a subquery, otherwise
            # offset and limit apply to the result of count()!
            cr.execute('SELECT count(*) FROM (%s) AS count' % query_str, where_clause_params)
            res = cr.fetchone()
            return res[0]

        cr.execute(query_str, where_clause_params)
        res = cr.fetchall()

        # TDE note: with auto_join, we could have several lines about the same result
        # i.e. a lead with several unread messages; we uniquify the result using
        # a fast way to do it while preserving order (http://www.peterbe.com/plog/uniqifiers-benchmark)
        def _uniquify_list(seq):
            seen = set()
            return [x for x in seq if x not in seen and not seen.add(x)]

        return _uniquify_list([x[0] for x in res])

    # returns the different values ever entered for one field
    # this is used, for example, in the client when the user hits enter on
    # a char field
    def distinct_field_get(self, cr, uid, field, value, args=None, offset=0, limit=None):
        if not args:
            args = []
        if field in self._inherit_fields:
            return self.pool[self._inherit_fields[field][0]].distinct_field_get(cr, uid, field, value, args, offset, limit)
        else:
            return self._columns[field].search(cr, self, args, field, value, offset, limit, uid)

    def copy_data(self, cr, uid, id, default=None, context=None):
        """
        Copy given record's data with all its fields values

        :param cr: database cursor
        :param uid: current user id
        :param id: id of the record to copy
        :param default: field values to override in the original values of the copied record
        :type default: dictionary
        :param context: context arguments, like lang, time zone
        :type context: dictionary
        :return: dictionary containing all the field values
        """

        if context is None:
            context = {}

        # avoid recursion through already copied records in case of circular relationship
        seen_map = context.setdefault('__copy_data_seen',{})
        if id in seen_map.setdefault(self._name,[]):
            return
        seen_map[self._name].append(id)

        if default is None:
            default = {}
        if 'state' not in default:
            if 'state' in self._defaults:
                if callable(self._defaults['state']):
                    default['state'] = self._defaults['state'](self, cr, uid, context)
                else:
                    default['state'] = self._defaults['state']

        context_wo_lang = context.copy()
        if 'lang' in context:
            del context_wo_lang['lang']
        data = self.read(cr, uid, [id,], context=context_wo_lang)
        if data:
            data = data[0]
        else:
            raise IndexError( _("Record #%d of %s not found, cannot copy!") %( id, self._name))

        # build a black list of fields that should not be copied
        blacklist = set(MAGIC_COLUMNS + ['parent_left', 'parent_right'])
        def blacklist_given_fields(obj):
            # blacklist the fields that are given by inheritance
            for other, field_to_other in obj._inherits.items():
                blacklist.add(field_to_other)
                if field_to_other in default:
                    # all the fields of 'other' are given by the record: default[field_to_other],
                    # except the ones redefined in self
                    blacklist.update(set(self.pool[other]._all_columns) - set(self._columns))
                else:
                    blacklist_given_fields(self.pool[other])
        blacklist_given_fields(self)

        res = dict(default)
        for f, colinfo in self._all_columns.items():
            field = colinfo.column
            if f in default:
                pass
            elif f in blacklist:
                pass
            elif isinstance(field, fields.function):
                pass
            elif field._type == 'many2one':
                res[f] = data[f] and data[f][0]
            elif field._type == 'one2many':
                other = self.pool[field._obj]
                # duplicate following the order of the ids because we'll rely on
                # it later for copying translations in copy_translation()!
                lines = [other.copy_data(cr, uid, line_id, context=context) for line_id in sorted(data[f])]
                # the lines are duplicated using the wrong (old) parent, but then
                # are reassigned to the correct one thanks to the (0, 0, ...)
                res[f] = [(0, 0, line) for line in lines if line]
            elif field._type == 'many2many':
                res[f] = [(6, 0, data[f])]
            else:
                res[f] = data[f]

        return res

    def copy_translations(self, cr, uid, old_id, new_id, context=None):
        if context is None:
            context = {}

        # avoid recursion through already copied records in case of circular relationship
        seen_map = context.setdefault('__copy_translations_seen',{})
        if old_id in seen_map.setdefault(self._name,[]):
            return
        seen_map[self._name].append(old_id)

        trans_obj = self.pool.get('ir.translation')
        # TODO it seems fields_get can be replaced by _all_columns (no need for translation)
        fields = self.fields_get(cr, uid, context=context)

        translation_records = []
        for field_name, field_def in fields.items():
            # we must recursively copy the translations for o2o and o2m
            if field_def['type'] == 'one2many':
                target_obj = self.pool[field_def['relation']]
                old_record, new_record = self.read(cr, uid, [old_id, new_id], [field_name], context=context)
                # here we rely on the order of the ids to match the translations
                # as foreseen in copy_data()
                old_children = sorted(old_record[field_name])
                new_children = sorted(new_record[field_name])
                for (old_child, new_child) in zip(old_children, new_children):
                    target_obj.copy_translations(cr, uid, old_child, new_child, context=context)
            # and for translatable fields we keep them for copy
            elif field_def.get('translate'):
                trans_name = ''
                if field_name in self._columns:
                    trans_name = self._name + "," + field_name
                elif field_name in self._inherit_fields:
                    trans_name = self._inherit_fields[field_name][0] + "," + field_name
                if trans_name:
                    trans_ids = trans_obj.search(cr, uid, [
                            ('name', '=', trans_name),
                            ('res_id', '=', old_id)
                    ])
                    translation_records.extend(trans_obj.read(cr, uid, trans_ids, context=context))

        for record in translation_records:
            del record['id']
            record['res_id'] = new_id
            trans_obj.create(cr, uid, record, context=context)

    @api.returns('self', lambda self, value: value.id)
    def copy(self, cr, uid, id, default=None, context=None):
        """
        Duplicate record with given id updating it with default values

        :param cr: database cursor
        :param uid: current user id
        :param id: id of the record to copy
        :param default: dictionary of field values to override in the original values of the copied record, e.g: ``{'field_name': overriden_value, ...}``
        :type default: dictionary
        :param context: context arguments, like lang, time zone
        :type context: dictionary
        :return: id of the newly created record

        """
        if context is None:
            context = {}
        context = context.copy()
        data = self.copy_data(cr, uid, id, default, context)
        new_id = self.create(cr, uid, data, context)
        self.copy_translations(cr, uid, id, new_id, context)
        return new_id

    @api.returns('self')
    def exists(self, cr, uid, ids, context=None):
        """Checks whether the given id or ids exist in this model,
           and return the list of ids that do. This is simple to use for
           a truth test on a Record::

               if record.exists():
                   pass

           :param ids: id or list of ids to check for existence
           :type ids: int or [int]
           :return: the list of ids that currently exist, out of
                    the given `ids`
        """
        if type(ids) in (int, long):
            ids = [ids]
        if not ids:
            return []
        query = 'SELECT id FROM "%s"' % self._table
        cr.execute(query + "WHERE ID IN %s", (tuple(ids),))
        return [x[0] for x in cr.fetchall()]

    def check_recursion(self, cr, uid, ids, context=None, parent=None):
        _logger.warning("You are using deprecated %s.check_recursion(). Please use the '_check_recursion()' instead!" % \
                        self._name)
        assert parent is None or parent in self._columns or parent in self._inherit_fields,\
                    "The 'parent' parameter passed to check_recursion() must be None or a valid field name"
        return self._check_recursion(cr, uid, ids, context, parent)

    def _check_recursion(self, cr, uid, ids, context=None, parent=None):
        """
        Verifies that there is no loop in a hierarchical structure of records,
        by following the parent relationship using the **parent** field until a loop
        is detected or until a top-level record is found.

        :param cr: database cursor
        :param uid: current user id
        :param ids: list of ids of records to check
        :param parent: optional parent field name (default: ``self._parent_name = parent_id``)
        :return: **True** if the operation can proceed safely, or **False** if an infinite loop is detected.
        """
        if not parent:
            parent = self._parent_name

        # must ignore 'active' flag, ir.rules, etc. => direct SQL query
        query = 'SELECT "%s" FROM "%s" WHERE id = %%s' % (parent, self._table)
        for id in ids:
            current_id = id
            while current_id is not None:
                cr.execute(query, (current_id,))
                result = cr.fetchone()
                current_id = result[0] if result else None
                if current_id == id:
                    return False
        return True

    def _check_m2m_recursion(self, cr, uid, ids, field_name):
        """
        Verifies that there is no loop in a hierarchical structure of records,
        by following the parent relationship using the **parent** field until a loop
        is detected or until a top-level record is found.

        :param cr: database cursor
        :param uid: current user id
        :param ids: list of ids of records to check
        :param field_name: field to check
        :return: **True** if the operation can proceed safely, or **False** if an infinite loop is detected.
        """

        field = self._all_columns.get(field_name)
        field = field.column if field else None
        if not field or field._type != 'many2many' or field._obj != self._name:
            # field must be a many2many on itself
            raise ValueError('invalid field_name: %r' % (field_name,))

        query = 'SELECT distinct "%s" FROM "%s" WHERE "%s" IN %%s' % (field._id2, field._rel, field._id1)
        ids_parent = ids[:]
        while ids_parent:
            ids_parent2 = []
            for i in range(0, len(ids_parent), cr.IN_MAX):
                j = i + cr.IN_MAX
                sub_ids_parent = ids_parent[i:j]
                cr.execute(query, (tuple(sub_ids_parent),))
                ids_parent2.extend(filter(None, map(lambda x: x[0], cr.fetchall())))
            ids_parent = ids_parent2
            for i in ids_parent:
                if i in ids:
                    return False
        return True

    def _get_external_ids(self, cr, uid, ids, *args, **kwargs):
        """Retrieve the External ID(s) of any database record.

        **Synopsis**: ``_get_xml_ids(cr, uid, ids) -> { 'id': ['module.xml_id'] }``

        :return: map of ids to the list of their fully qualified External IDs
                 in the form ``module.key``, or an empty list when there's no External
                 ID for a record, e.g.::

                     { 'id': ['module.ext_id', 'module.ext_id_bis'],
                       'id2': [] }
        """
        ir_model_data = self.pool.get('ir.model.data')
        data_ids = ir_model_data.search(cr, uid, [('model', '=', self._name), ('res_id', 'in', ids)])
        data_results = ir_model_data.read(cr, uid, data_ids, ['module', 'name', 'res_id'])
        result = {}
        for id in ids:
            # can't use dict.fromkeys() as the list would be shared!
            result[id] = []
        for record in data_results:
            result[record['res_id']].append('%(module)s.%(name)s' % record)
        return result

    def get_external_id(self, cr, uid, ids, *args, **kwargs):
        """Retrieve the External ID of any database record, if there
        is one. This method works as a possible implementation
        for a function field, to be able to add it to any
        model object easily, referencing it as ``Model.get_external_id``.

        When multiple External IDs exist for a record, only one
        of them is returned (randomly).

        :return: map of ids to their fully qualified XML ID,
                 defaulting to an empty string when there's none
                 (to be usable as a function field),
                 e.g.::

                     { 'id': 'module.ext_id',
                       'id2': '' }
        """
        results = self._get_xml_ids(cr, uid, ids)
        for k, v in results.iteritems():
            if results[k]:
                results[k] = v[0]
            else:
                results[k] = ''
        return results

    # backwards compatibility
    get_xml_id = get_external_id
    _get_xml_ids = _get_external_ids

    def print_report(self, cr, uid, ids, name, data, context=None):
        """
        Render the report `name` for the given IDs. The report must be defined
        for this model, not another.
        """
        report = self.pool['ir.actions.report.xml']._lookup_report(cr, name)
        assert self._name == report.table
        return report.create(cr, uid, ids, data, context)

    # Transience
    def is_transient(self):
        """ Return whether the model is transient.

        See :class:`TransientModel`.

        """
        return self._transient

    def _transient_clean_rows_older_than(self, cr, seconds):
        assert self._transient, "Model %s is not transient, it cannot be vacuumed!" % self._name
        # Never delete rows used in last 5 minutes
        seconds = max(seconds, 300)
        query = ("SELECT id FROM " + self._table + " WHERE"
            " COALESCE(write_date, create_date, (now() at time zone 'UTC'))::timestamp"
            " < ((now() at time zone 'UTC') - interval %s)")
        cr.execute(query, ("%s seconds" % seconds,))
        ids = [x[0] for x in cr.fetchall()]
        self.unlink(cr, SUPERUSER_ID, ids)

    def _transient_clean_old_rows(self, cr, max_count):
        # Check how many rows we have in the table
        cr.execute("SELECT count(*) AS row_count FROM " + self._table)
        res = cr.fetchall()
        if res[0][0] <= max_count:
            return  # max not reached, nothing to do
        self._transient_clean_rows_older_than(cr, 300)

    def _transient_vacuum(self, cr, uid, force=False):
        """Clean the transient records.

        This unlinks old records from the transient model tables whenever the
        "_transient_max_count" or "_max_age" conditions (if any) are reached.
        Actual cleaning will happen only once every "_transient_check_time" calls.
        This means this method can be called frequently called (e.g. whenever
        a new record is created).
        Example with both max_hours and max_count active:
        Suppose max_hours = 0.2 (e.g. 12 minutes), max_count = 20, there are 55 rows in the
        table, 10 created/changed in the last 5 minutes, an additional 12 created/changed between
        5 and 10 minutes ago, the rest created/changed more then 12 minutes ago.
        - age based vacuum will leave the 22 rows created/changed in the last 12 minutes
        - count based vacuum will wipe out another 12 rows. Not just 2, otherwise each addition
          would immediately cause the maximum to be reached again.
        - the 10 rows that have been created/changed the last 5 minutes will NOT be deleted
        """
        assert self._transient, "Model %s is not transient, it cannot be vacuumed!" % self._name
        _transient_check_time = 20          # arbitrary limit on vacuum executions
        self._transient_check_count += 1
        if not force and (self._transient_check_count < _transient_check_time):
            return True  # no vacuum cleaning this time
        self._transient_check_count = 0

        # Age-based expiration
        if self._transient_max_hours:
            self._transient_clean_rows_older_than(cr, self._transient_max_hours * 60 * 60)

        # Count-based expiration
        if self._transient_max_count:
            self._transient_clean_old_rows(cr, self._transient_max_count)

        return True

    def resolve_2many_commands(self, cr, uid, field_name, commands, fields=None, context=None):
        """ Serializes one2many and many2many commands into record dictionaries
            (as if all the records came from the database via a read()).  This
            method is aimed at onchange methods on one2many and many2many fields.

            Because commands might be creation commands, not all record dicts
            will contain an ``id`` field.  Commands matching an existing record
            will have an ``id``.

            :param field_name: name of the one2many or many2many field matching the commands
            :type field_name: str
            :param commands: one2many or many2many commands to execute on ``field_name``
            :type commands: list((int|False, int|False, dict|False))
            :param fields: list of fields to read from the database, when applicable
            :type fields: list(str)
            :returns: records in a shape similar to that returned by ``read()``
                (except records may be missing the ``id`` field if they don't exist in db)
            :rtype: list(dict)
        """
        result = []             # result (list of dict)
        record_ids = []         # ids of records to read
        updates = {}            # {id: dict} of updates on particular records

        for command in commands:
            if not isinstance(command, (list, tuple)):
                record_ids.append(command)
            elif command[0] == 0:
                result.append(command[2])
            elif command[0] == 1:
                record_ids.append(command[1])
                updates.setdefault(command[1], {}).update(command[2])
            elif command[0] in (2, 3):
                record_ids = [id for id in record_ids if id != command[1]]
            elif command[0] == 4:
                record_ids.append(command[1])
            elif command[0] == 5:
                result, record_ids = [], []
            elif command[0] == 6:
                result, record_ids = [], list(command[2])

        # read the records and apply the updates
        other_model = self.pool[self._all_columns[field_name].column._obj]
        for record in other_model.read(cr, uid, record_ids, fields=fields, context=context):
            record.update(updates.get(record['id'], {}))
            result.append(record)

        return result

    # for backward compatibility
    resolve_o2m_commands_to_record_dicts = resolve_2many_commands

    def search_read(self, cr, uid, domain=None, fields=None, offset=0, limit=None, order=None, context=None):
        """
        Performs a ``search()`` followed by a ``read()``.

        :param cr: database cursor
        :param user: current user id
        :param domain: Search domain, see ``args`` parameter in ``search()``. Defaults to an empty domain that will match all records.
        :param fields: List of fields to read, see ``fields`` parameter in ``read()``. Defaults to all fields.
        :param offset: Number of records to skip, see ``offset`` parameter in ``search()``. Defaults to 0.
        :param limit: Maximum number of records to return, see ``limit`` parameter in ``search()``. Defaults to no limit.
        :param order: Columns to sort result, see ``order`` parameter in ``search()``. Defaults to no sort.
        :param context: context arguments.
        :return: List of dictionaries containing the asked fields.
        :rtype: List of dictionaries.

        """
        record_ids = self.search(cr, uid, domain or [], offset, limit or False, order or False, context or {})
        if not record_ids:
            return []
        result = self.read(cr, uid, record_ids, fields or [], context or {})
        # reorder read
        if len(result) >= 1:
            index = {}
            for r in result:
                index[r['id']] = r
            result = [index[x] for x in record_ids if x in index]
        return result

    def _register_hook(self, cr):
        """ stuff to do right after the registry is built """
        pass

    def _patch_method(self, name, method):
        """ Monkey-patch a method for all instances of this model. This replaces
            the method called `name` by `method` in `self`'s class.
            The original method is then accessible via ``method.origin``, and it
            can be restored with :meth:`~._revert_method`.

            Example::

                @api.multi
                def do_write(self, values):
                    # do stuff, and call the original method
                    return do_write.origin(self, values)

                # patch method write of model
                model._patch_method('write', do_write)

                # this will call do_write
                records = model.search([...])
                records.write(...)

                # restore the original method
                model._revert_method('write')
        """
        cls = type(self)
        origin = getattr(cls, name)
        method.origin = origin
        # propagate @returns from origin to method, and apply api decorator
        wrapped = api.guess(api.returns(origin)(method))
        wrapped.origin = origin
        setattr(cls, name, wrapped)

    def _revert_method(self, name):
        """ Revert the original method of `self` called `name`.
            See :meth:`~._patch_method`.
        """
        cls = type(self)
        method = getattr(cls, name)
        setattr(cls, name, method.origin)

    #
    # Instance creation
    #
    # An instance represents an ordered collection of records in a given scope.
    # The instance object refers to the scope, and the records themselves are
    # represented by their cache dictionary. The 'id' of each record is found in
    # its corresponding cache dictionary.
    #
    # This design has the following advantages:
    #  - cache access is direct and thus fast;
    #  - one can consider records without an 'id' (see new records);
    #  - the global cache is only an index to "resolve" a record 'id'.
    #

    @classmethod
    def _instance(cls, scope, caches):
        """ Create an instance attached to `scope`; `caches` is a tuple with the
            cache dictionaries of the records in the instance.
        """
        records = object.__new__(cls)
        records._scope = scope
        records._caches = caches
        return records

    @classmethod
    @api.model
    def browse(cls, arg=None):
        """ Return an instance corresponding to `arg` and attached to the
            current scope. The parameter `arg` is either a record id, or a
            collection of record ids.
        """
        if isinstance(arg, Iterable) and not isinstance(arg, basestring):
            ids = tuple(arg)
        elif arg:
            ids = (arg,)
        else:
            ids = ()
        scope = scope_proxy.current
        model_cache = scope.cache[cls._name]
        return cls._instance(scope, tuple(model_cache[id] for id in ids))

    #
    # Internal properties, for manipulating the instance's implementation
    #

    @property
    def _id(self):
        """ Return the 'id' of record `self` or ``False``. """
        return bool(self._caches) and self._caches[0].id

    @property
    def _ids(self):
        """ Return the 'id' of all records in `self`. """
        return (cache.id for cache in self._caches)

    @property
    def _refs(self):
        """ Return a set of record identifiers for `self`. This is aimed at
            comparing instances. The result is similar to `_ids`, but uses other
            values for identifying new records, since they do not have an 'id'.
        """
        return set(cache.id or (id(cache),) for cache in self._caches)

    @tools.lazy_property
    def _model_cache(self):
        """ Return the cache of the corresponding model. """
        # Note: The value of this property is evaluated only once and memoized.
        # It is correct to do so, because the scope's cache never drops the
        # cache of models, even when all caches are invalidated.
        return self._scope.cache[self._name]

    @tools.lazy_property
    def _record_cache(self):
        """ Return the cache of the first record in `self`. """
        return self._caches[0]

    #
    # Conversion methods
    #

    def one(self):
        """ Return `self` if it is a singleton instance, otherwise raise an
            exception.
        """
        if len(self) == 1:
            return self
        raise except_orm("ValueError", "Expected singleton: %s" % self)

    def scoped(self, scope=None):
        """ Return an instance equivalent to `self` attached to `scope` or the
            current scope.
        """
        scope = scope or scope_proxy.current
        if self._scope is scope:
            return self
        ids = list(self._ids)
        if all(ids):
            with scope:
                return self.browse(ids)
        raise except_orm("ValueError", "Cannot scope %s" % self)

    def unbrowse(self):
        """ Return the list of record ids of this instance. """
        return filter(None, self._ids)

    def _convert_to_write(self, values):
        """ Convert the `values` dictionary in the format of :meth:`write`. """
        return dict(
            (name, self._fields[name].convert_to_write(value))
            for name, value in values.iteritems()
        )

    #
    # Record/cache updates
    #

    def _update_cache(self, values):
        """ Update the cache of record `self[0]` with `values`. Only the cache
            is be updated, no side effect happens.
        """
        for name, value in values.iteritems():
            self._record_cache.set_busy(name)
            self[name] = value

    def _prepare_cache(self, names):
        """ Prepare records in `self` to update field `names` in cache only. """
        for cache in self._caches:
            for name in names:
                cache.set_busy(name)

    def update(self, values):
        """ Update record `self[0]` with `values`. """
        for name, value in values.iteritems():
            self[name] = value

    #
    # Draft records - records on which the field setters only affect the cache
    #

    @property
    def draft(self):
        """ Return whether ``self[0]`` is a draft record. """
        return self and self._record_cache.draft

    @draft.setter
    def draft(self, value):
        """ Set whether ``self[0]`` is a draft record. """
        self._record_cache.draft = bool(value)

    def get_draft_values(self):
        """ Return the draft values of `self` as a dictionary mapping field
            names to values.
        """
        if self._id:
            _logger.warning("%s.get_draft_values() non optimal", self[0])
        return dict(item
            for item in self._record_cache.iteritems()
            if item[0] not in MAGIC_COLUMNS
        )

    #
    # New records - represent records that do not exist in the database yet;
    # they are used to compute default values.
    #

    def new(self, values={}):
        """ Return a new record instance attached to the current scope, and
            initialized with the `values` dictionary. Such a record does not
            exist in the database. The returned instance is marked as draft.
        """
        assert 'id' not in values, "New records do not have an 'id'."
        scope = scope_proxy.current
        record_cache = scope.cache[self._name][False]
        record = self._instance(scope, (record_cache,))
        record._update_cache(values)
        record.draft = True
        return record

    #
    # "Dunder" methods
    #

    def __nonzero__(self):
        """ Test whether `self` is nonempty. """
        return bool(self._caches)

    def __len__(self):
        """ Return the size of `self`. """
        return len(self._caches)

    def __iter__(self):
        """ Return an iterator over `self`. """
        for cache in self._caches:
            yield self._instance(self._scope, (cache,))

    def __contains__(self, item):
        """ Test whether `item` is a subset of `self` or a field name. """
        if isinstance(item, BaseModel):
            if self._name == item._name:
                return item._refs <= self._refs
            raise except_orm("ValueError", "Mixing apples and oranges: %s in %s" % (item, self))
        if isinstance(item, basestring):
            return item in self._fields
        return item in self.unbrowse()

    def __add__(self, other):
        """ Return the concatenation of two instances. """
        if not isinstance(other, BaseModel) or self._name != other._name:
            raise except_orm("ValueError", "Mixing apples and oranges: %s + %s" % (self, other))
        scope = scope_proxy.current
        self, other = self.scoped(scope), other.scoped(scope)
        return self._instance(scope, self._caches + other._caches)

    def __sub__(self, other):
        """ Return the difference between two instances (order-preserving). """
        if not isinstance(other, BaseModel) or self._name != other._name:
            raise except_orm("ValueError", "Mixing apples and oranges: %s - %s" % (self, other))
        scope = scope_proxy.current
        self, other = self.scoped(scope), other.scoped(scope)
        caches = tuple(cache for cache in self._caches if cache not in other._caches)
        return self._instance(scope, caches)

    def __and__(self, other):
        """ Return the intersection of two instances. """
        if not isinstance(other, BaseModel) or self._name != other._name:
            raise except_orm("ValueError", "Mixing apples and oranges: %s & %s" % (self, other))
        scope = scope_proxy.current
        self, other = self.scoped(scope), other.scoped(scope)
        caches = tuple(cache for cache in self._caches if cache in other._caches)
        return self._instance(scope, caches)

    def __or__(self, other):
        """ Return the union of two instances. """
        if not isinstance(other, BaseModel) or self._name != other._name:
            raise except_orm("ValueError", "Mixing apples and oranges: %s | %s" % (self, other))
        scope = scope_proxy.current
        self, other = self.scoped(scope), other.scoped(scope)
        # index all cache dicts by their id in order to "merge" duplicates
        index = dict((id(cache), cache) for cache in self._caches + other._caches)
        return self._instance(scope, tuple(index.itervalues()))

    def __eq__(self, other):
        """ Test whether two instances are equivalent (as sets). """
        if not isinstance(other, BaseModel):
            if other:
                _logger.warning("Comparing apples and oranges: %s == %s", self, other)
            return False
        return self._name == other._name and self._refs == other._refs

    def __ne__(self, other):
        return not self == other

    def __lt__(self, other):
        if not isinstance(other, BaseModel) or self._name != other._name:
            raise except_orm("ValueError", "Mixing apples and oranges: %s < %s" % (self, other))
        return self._refs < other._refs

    def __le__(self, other):
        if not isinstance(other, BaseModel) or self._name != other._name:
            raise except_orm("ValueError", "Mixing apples and oranges: %s <= %s" % (self, other))
        return self._refs <= other._refs

    def __gt__(self, other):
        if not isinstance(other, BaseModel) or self._name != other._name:
            raise except_orm("ValueError", "Mixing apples and oranges: %s > %s" % (self, other))
        return self._refs > other._refs

    def __ge__(self, other):
        if not isinstance(other, BaseModel) or self._name != other._name:
            raise except_orm("ValueError", "Mixing apples and oranges: %s >= %s" % (self, other))
        return self._refs >= other._refs

    def __int__(self):
        return self._id

    def __str__(self):
        model_name = self._name.replace('.', '_')
        return "%s%s" % (model_name, tuple(self._ids))

    def __unicode__(self):
        return unicode(str(self))

    __repr__ = __str__

    def __hash__(self):
        ids = list(self._ids)
        if all(ids):
            return hash((self._name, frozenset(ids)))
        raise except_orm("ValueError", "Cannot hash %s" % self)

    def __getitem__(self, key):
        """ If `key` is an integer or a slice, return the corresponding record
            selection as an instance (attached to the same scope as `self`).
            Otherwise read the field `key` of the first record in `self`.

            Examples::

                inst = model.search(dom)    # inst is a recordset
                r4 = inst[3]                # fourth record in inst
                rs = inst[10:20]            # subset of inst
                nm = rs['name']             # name of first record in inst
        """
        if isinstance(key, basestring):
            # important: one must call the field's getter
            return self._fields[key].__get__(self, type(self))
        elif isinstance(key, slice):
            return self._instance(self._scope, self._caches[key])
        else:
            return self._instance(self._scope, (self._caches[key],))

    def __setitem__(self, key, value):
        """ Assign the field `key` to `value` in record `self`. """
        # important: one must call the field's setter
        return self._fields[key].__set__(self, value)

    def __getattr__(self, name):
        if name.startswith('signal_'):
            # self.signal_XXX() sends signal XXX to the record's workflow
            signal_name = name[len('signal_'):]
            assert signal_name
            return (lambda *args, **kwargs:
                    self.signal_workflow(*args, signal=signal_name, **kwargs))

        get = getattr(super(BaseModel, self), '__getattr__', None)
        if get is not None:
            return get(name)
        else:
            raise AttributeError("%r object has no attribute %r" % (type(self).__name__, name))

    #
    # Cache and recomputation management
    #

    def refresh(self):
        """ Clear the records cache.

            .. deprecated:: 8.0
                The record cache is automatically invalidated.
        """
        scope_proxy.invalidate_all()

    def invalidate_cache(self, fnames=None, ids=None):
        """ Invalidate the record caches after some records have been modified.

            :param fnames: the list of modified fields, or ``None`` for all fields
            :param ids: the list of modified record ids, or ``None`` for all
        """
        if fnames is None:
            if ids is None:
                return scope_proxy.invalidate_all()
            fnames = self._fields.keys()

        for fname in fnames:
            scope_proxy.invalidate(self._name, fname, ids)
            # invalidate inverse fields, too
            inv = self._fields[fname].inverse_field
            if inv:
                scope_proxy.invalidate(inv.model_name, inv.name, None)

    @api.multi
    def modified(self, fnames):
        """ Notify that fields have been modified on `self`. This invalidates
            the cache, and prepares the recomputation of stored function fields
            (new-style fields only).

            :param fnames: iterable of field names that have been modified on
                records `self`
        """
        # each field knows what to invalidate and recompute
        for fname in fnames:
            self._fields[fname].modified(self)

        # HACK: invalidate all non-stored fields.function
        for mname, fnames in self.pool._pure_function_fields.iteritems():
            for fname in fnames:
                scope_proxy.invalidate(mname, fname, None)

    def recompute(self):
        """ Recompute stored function fields. The fields and records to
            recompute have been determined by method :meth:`modified`.
        """
        with scope_proxy.recomputation as recomputation:
            while recomputation:
                field, recs = next(iter(recomputation))
                # To recompute the field, simply evaluate it on the records; the
                # method _get_field() does the right thing, including removing
                # it from the recomputation manager.
                failed = recs.browse()
                for rec in recs:
                    try:
                        rec[field.name]
                    except Exception:
                        failed += rec
                # check whether recomputation failed for some existing records
                failed = failed.exists()
                if failed:
                    raise except_orm("Error",
                        "Recomputation of %s failed for %s" % (field, failed))

    #
    # Generic onchange method
    #

    @api.multi
    def onchange(self, field_name, values):
        # create a new record with the values, except field_name
        record = self.new(values)
        record_values = record._record_cache.dump()
        record._record_cache.pop(field_name)

        # check for a field-specific onchange method
        method = getattr(record, 'onchange_' + field_name, None)
        if method is None:
            # apply the change on the record
            record[field_name] = values[field_name]
        else:
            # invoke specific onchange method, which may return a result
            result = method(values[field_name])
            if result is not None:
                return result

        # determine result, and return it
        changed = self._convert_to_write(dict(
            (k, record[k])
            for k, v in record_values.iteritems()
            if record[k] != v
        ))
        return {'value': changed}


# extra definitions for backward compatibility
browse_record_list = BaseModel

class browse_record(object):
    """ Pseudo-class for testing record instances """
    class __metaclass__(type):
        def __instancecheck__(self, inst):
            return isinstance(inst, BaseModel) and len(inst) <= 1

class browse_null(object):
    """ Pseudo-class for testing null instances """
    class __metaclass__(type):
        def __instancecheck__(self, inst):
            return isinstance(inst, BaseModel) and not inst


class Model(BaseModel):
    """Main super-class for regular database-persisted OpenERP models.

    OpenERP models are created by inheriting from this class::

        class user(Model):
            ...

    The system will later instantiate the class once per database (on
    which the class' module is installed).
    """
    _auto = True
    _register = False # not visible in ORM registry, meant to be python-inherited only
    _transient = False # True in a TransientModel

class TransientModel(BaseModel):
    """Model super-class for transient records, meant to be temporarily
       persisted, and regularly vaccuum-cleaned.

       A TransientModel has a simplified access rights management,
       all users can create new records, and may only access the
       records they created. The super-user has unrestricted access
       to all TransientModel records.
    """
    _auto = True
    _register = False # not visible in ORM registry, meant to be python-inherited only
    _transient = True

class AbstractModel(BaseModel):
    """Abstract Model super-class for creating an abstract class meant to be
       inherited by regular models (Models or TransientModels) but not meant to
       be usable on its own, or persisted.

       Technical note: we don't want to make AbstractModel the super-class of
       Model or BaseModel because it would not make sense to put the main
       definition of persistence methods such as create() in it, and still we
       should be able to override them within an AbstractModel.
       """
    _auto = False # don't create any database backend for AbstractModels
    _register = False # not visible in ORM registry, meant to be python-inherited only
    _transient = False

def itemgetter_tuple(items):
    """ Fixes itemgetter inconsistency (useful in some cases) of not returning
    a tuple if len(items) == 1: always returns an n-tuple where n = len(items)
    """
    if len(items) == 0:
        return lambda a: ()
    if len(items) == 1:
        return lambda gettable: (gettable[items[0]],)
    return operator.itemgetter(*items)
class ImportWarning(Warning):
    """ Used to send warnings upwards the stack during the import process
    """
    pass


def convert_pgerror_23502(model, fields, info, e):
    m = re.match(r'^null value in column "(?P<field>\w+)" violates '
                 r'not-null constraint\n',
                 str(e))
    field_name = m.group('field')
    if not m or field_name not in fields:
        return {'message': unicode(e)}
    message = _(u"Missing required value for the field '%s'.") % field_name
    field = fields.get(field_name)
    if field:
        message = _(u"Missing required value for the field '%s' (%s)") % (field['string'], field_name)
    return {
        'message': message,
        'field': field_name,
    }
def convert_pgerror_23505(model, fields, info, e):
    m = re.match(r'^duplicate key (?P<field>\w+) violates unique constraint',
                 str(e))
    field_name = m.group('field')
    if not m or field_name not in fields:
        return {'message': unicode(e)}
    message = _(u"The value for the field '%s' already exists.") % field_name
    field = fields.get(field_name)
    if field:
        message = _(u"%s This might be '%s' in the current model, or a field "
                    u"of the same name in an o2m.") % (message, field['string'])
    return {
        'message': message,
        'field': field_name,
    }

PGERROR_TO_OE = defaultdict(
    # shape of mapped converters
    lambda: (lambda model, fvg, info, pgerror: {'message': unicode(pgerror)}), {
    # not_null_violation
    '23502': convert_pgerror_23502,
    # unique constraint error
    '23505': convert_pgerror_23505,
})


# keep those imports here to avoid dependency cycle errors
import expression
import fields2
from fields2 import Field

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
