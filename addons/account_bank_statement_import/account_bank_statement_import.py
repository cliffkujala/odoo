# -*- coding: utf-8 -*-

from openerp.osv import fields, osv
from openerp.tools.translate import _

import logging
_logger = logging.getLogger(__name__)

_IMPORT_FILE_TYPE = [('none', _('No Import Format Available'))]

def add_file_type(selection_value):
    global _IMPORT_FILE_TYPE
    if _IMPORT_FILE_TYPE[0][0] == 'none':
        _IMPORT_FILE_TYPE = [selection_value]
    else:
        _IMPORT_FILE_TYPE.append(selection_value)

class account_bank_statement_import(osv.TransientModel):
    _name = 'account.bank.statement.import'
    _description = 'Import Bank Statement'

    def _get_import_file_type(self, cr, uid, context=None):
        return _IMPORT_FILE_TYPE

    _columns = {
        'data_file': fields.binary('Bank Statement File', required=True, help='Get you bank statements in electronic format from your bank and select them here.'),
        'file_type': fields.selection(_get_import_file_type, 'File Type', required=True),
        'journal_id': fields.many2one('account.journal', 'Journal', required=True, help="The journal for which the bank statements will be created"),
    }

    def _get_first_file_type(self, cr, uid, context=None):
        return self._get_import_file_type(cr, uid, context=context)[0][0]

    def _get_default_journal(self, cr, uid, context=None):
        company_id = self.pool.get('res.company')._company_default_get(cr, uid, 'account.bank.statement', context=context)
        journal_ids = self.pool.get('account.journal').search(cr, uid, [('type', '=', 'bank'), ('company_id', '=', company_id)], context=context)
        return journal_ids and journal_ids[0] or False

    _defaults = {
        'file_type': _get_first_file_type,
        'journal_id': _get_default_journal,
    }

    def _detect_partner(self, cr, uid, identifying_string, identifying_field='acc_number', context=None):
        """Try to find a bank account and its related partner for the given 'identifying_string', looking on the field 'identifying_field'.

           :param identifying_string: varchar
           :param identifying_field: varchar corresponding to the name of a field of res.partner.bank
           :returns: tuple(ID of the bank account found or False, ID of the partner for the bank account found or False)
        """
        partner_id = False
        bank_account_id = False
        if identifying_string:
            ids = self.pool.get('res.partner.bank').search(cr, uid, [(identifying_field, '=', identifying_string)], context=context)
            if ids:
                bank_account_id = ids[0]
                partner_id = self.pool.get('res.partner.bank').browse(cr, uid, bank_account_id, context=context).partner_id.id
            else:
                #create the bank account, not linked to any partner. The reconciliation will link the partner manually
                #chosen at the bank statement final confirmation time.
                try:
                    type_model, type_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'base', 'bank_normal')
                    type_id = self.pool.get('res.partner.bank.type').browse(cr, uid, type_id, context=context)
                    bank_code = type_id.code
                except ValueError:
                    bank_code = 'bank'
                acc_number = identifying_field == 'acc_number' and identifying_string or _('Undefined')
                bank_account_vals = {
                    'acc_number': acc_number,
                    'state': bank_code,
                }
                bank_account_vals[identifying_field] = identifying_string
                bank_account_id = self.pool.get('res.partner.bank').create(cr, uid, bank_account_vals, context=context)
        return bank_account_id, partner_id

    def import_bank_statements(self, cr, uid, bank_statement_vals=False, context=None):
        """ Get a list of values to pass to the create() of account.bank.statement object, and returns a list of ID created using those values
            This method will also automatically reconcile transactions for which there is an unambiguous counterpart. """
        bs_obj = self.pool.get('account.bank.statement')
        bsl_obj = self.pool.get('account.bank.statement.line')
        if len(bank_statement_vals) == 0:
            raise osv.except_osv(_('Error'), _('The file doesn\'t contain any bank statement (or wasn\'t properly processed).'))
        
        # Filter out already imported transactions and create statements
        statement_ids = []
        num_ignored_statement_lines = 0
        cr.execute("SELECT unique_import_id FROM account_bank_statement_line")
        already_imported_lines = [x[0] for x in cr.fetchall()]
        for st_vals in bank_statement_vals:
            num_ignored_statement_lines += len(st_vals['line_ids'])
            st_vals['line_ids'] = [line_vals for line_vals in st_vals['line_ids'] if line_vals[2]['unique_import_id'] not in already_imported_lines]
            num_ignored_statement_lines -= len(st_vals['line_ids'])
            if len(st_vals['line_ids']) > 0:
                statement_ids.append(bs_obj.create(cr, uid, st_vals, context=context))
        if len(statement_ids) == 0:
            raise osv.except_osv(_('Error'), _('You have already imported that file.'))

        num_auto_reconciled = 0
        for statement in bs_obj.browse(cr, uid, statement_ids, context=context):
            for st_line in statement.line_ids:
                counterpart = bsl_obj.get_reconciliation_proposition(cr, uid, st_line, unambiguous=True, context=context)
                if counterpart:
                    for move_line_dict in counterpart:
                        # get_reconciliation_proposition() returns informations about move lines whereas process_reconciliation() expects informations
                        # about how to create new move lines to reconcile existing ones. So, if get_reconciliation_proposition() gives us a move line
                        # whose id is 7 and debit is 500, and we want to totally reconcile it, we need to feed process_reconciliation() with :
                        # 'counterpart_move_line_id': 7,
                        # 'credit': 500
                        # This is what the reconciliation widget does.
                        move_line_dict['counterpart_move_line_id'] = move_line_dict['id']
                        move_line_dict['debit'], move_line_dict['credit'] = move_line_dict['credit'], move_line_dict['debit']
                    bsl_obj.process_reconciliation(cr, uid, st_line.id, counterpart, context=context)
                    num_auto_reconciled += 1

        # Prepare import feedback
        notifications = []
        if num_ignored_statement_lines > 1:
            notifications += [{
                'type': 'warning', # note : can be success, info, warning or danger
                'message': _("%d transactions had already been imported and therefore were ignored. You might want to check how your bank exports statements.") % num_ignored_statement_lines
            }]
        if num_auto_reconciled > 0:
            notifications += [{
                'type': 'info',
                'message': _("%d transactions were automatically reconciled.") % num_auto_reconciled if num_auto_reconciled > 1 else _("1 transaction was automatically reconciled.")
            }]

        return statement_ids, notifications

    def process_none(self, cr, uid, data_file, journal_id=False, context=None):
        raise osv.except_osv(_('Error'), _('No available format for importing bank statement. You can install one of the file format available through the module installation.'))

    def parse_file(self, cr, uid, ids, context=None):
        """ Process the file chosen in the wizard, create bank statement(s) and go to reconciliation. """
        data = self.browse(cr, uid, ids[0], context=context)
        vals = getattr(self, "process_%s" % data.file_type)(cr, uid, data.data_file, data.journal_id.id, context=context)
        statement_ids, notifications = self.import_bank_statements(cr, uid, vals, context=context)
        model, action_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'account', 'action_bank_reconcile_bank_statements')
        action = self.pool[model].browse(cr, uid, action_id, context=context)
        return {
            'name': action.name,
            'tag': action.tag,
            'context': {
                'statement_ids': statement_ids,
                'notifications': notifications
            },
            'type': 'ir.actions.client',
        }

        return action

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
