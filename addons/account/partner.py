# -*- coding: utf-8 -*-

from operator import itemgetter
import time

from openerp import models, fields, api
from openerp.tools import DEFAULT_SERVER_DATETIME_FORMAT

class account_fiscal_position(models.Model):
    _name = 'account.fiscal.position'
    _description = 'Fiscal Position'
    _order = 'sequence'

    sequence = fields.Integer(string='Sequence')
    name = fields.Char(string='Fiscal Position', required=True)
    active = fields.Boolean(string='Active', default=True,
        help="By unchecking the active field, you may hide a fiscal position without deleting it.")
    company_id = fields.Many2one('res.company', string='Company')
    account_ids = fields.One2many('account.fiscal.position.account', 'position_id', string='Account Mapping', copy=True)
    tax_ids = fields.One2many('account.fiscal.position.tax', 'position_id', string='Tax Mapping', copy=True)
    note = fields.Text('Notes')
    auto_apply = fields.Boolean(string='Automatic', help="Apply automatically this fiscal position.")
    vat_required = fields.Boolean(string='VAT required', help="Apply only if partner has a VAT number.")
    country_id = fields.Many2one('res.country', string='Countries', 
        help="Apply only if delivery or invoicing country match.")
    country_group_id = fields.Many2one('res.country.group', string='Country Group',
        help="Apply only if delivery or invocing country match the group.")

    @api.v7
    def map_tax(self, cr, uid, fposition_id, taxes, context=None):
        if not taxes:
            return []
        if not fposition_id:
            return map(lambda x: x.id, taxes)
        result = set()
        for t in taxes:
            ok = False
            for tax in fposition_id.tax_ids:
                if tax.tax_src_id.id == t.id:
                    if tax.tax_dest_id:
                        result.add(tax.tax_dest_id.id)
                    ok=True
            if not ok:
                result.add(t.id)
        return list(result)

    @api.v8     # noqa
    def map_tax(self, taxes):
        result = self.env['account.tax'].browse()
        for tax in taxes:
            for t in self.tax_ids:
                if t.tax_src_id == tax:
                    if t.tax_dest_id:
                        result |= t.tax_dest_id
                    break
            else:
                result |= tax
        return result

    @api.v7
    def map_account(self, cr, uid, fposition_id, account_id, context=None):
        if not fposition_id:
            return account_id
        for pos in fposition_id.account_ids:
            if pos.account_src_id.id == account_id:
                account_id = pos.account_dest_id.id
                break
        return account_id

    @api.v8
    def map_account(self, account):
        for pos in self.account_ids:
            if pos.account_src_id == account:
                return pos.account_dest_id
        return account

    @api.model
    def get_fiscal_position(self, company_id, partner_id, delivery_id=None):
        if not partner_id:
            return False
        # This can be easily overriden to apply more complex fiscal rules
        PartnerObj = self.env['res.partner']
        partner = PartnerObj.browse(partner_id)

        # partner manually set fiscal position always win
        if partner.property_account_position:
            return partner.property_account_position.id

        # if no delivery use invocing
        if delivery_id:
            delivery = PartnerObj.browse(delivery_id)
        else:
            delivery = partner

        domain = [
            ('auto_apply', '=', True),
            '|', ('vat_required', '=', False), ('vat_required', '=', partner.vat_subjected),
            '|', ('country_id', '=', None), ('country_id', '=', delivery.country_id.id),
            '|', ('country_group_id', '=', None), ('country_group_id.country_ids', '=', delivery.country_id.id)
        ]
        fiscal_position = self.search(domain, limit=1)
        return fiscal_position or False

class account_fiscal_position_tax(models.Model):
    _name = 'account.fiscal.position.tax'
    _description = 'Taxes Fiscal Position'
    _rec_name = 'position_id'

    position_id = fields.Many2one('account.fiscal.position', string='Fiscal Position',
        required=True, ondelete='cascade')
    tax_src_id = fields.Many2one('account.tax', string='Tax Source', required=True)
    tax_dest_id = fields.Many2one('account.tax', string='Replacement Tax')

    _sql_constraints = [
        ('tax_src_dest_uniq',
         'unique (position_id,tax_src_id,tax_dest_id)',
         'A tax fiscal position could be defined only once time on same taxes.')
    ]


class account_fiscal_position_account(models.Model):
    _name = 'account.fiscal.position.account'
    _description = 'Accounts Fiscal Position'
    _rec_name = 'position_id'


    position_id = fields.Many2one('account.fiscal.position', string='Fiscal Position',
        required=True, ondelete='cascade')
    account_src_id = fields.Many2one('account.account', string='Account Source', 
        domain=[('deprecated', '=', False)], required=True)
    account_dest_id = fields.Many2one('account.account', string='Account Destination',
        domain=[('deprecated', '=', False)], required=True)

    _sql_constraints = [
        ('account_src_dest_uniq',
         'unique (position_id,account_src_id,account_dest_id)',
         'An account fiscal position could be defined only once time on same accounts.')
    ]


class res_partner(models.Model):
    _name = 'res.partner'
    _inherit = 'res.partner'
    _description = 'Partner'

    @api.multi
    def get_type_account_ids(self, form):
        move_state = ['draft','posted']
        if form['target_move'] == 'posted':
            move_state = ['posted']
        reconcil = True
        obj_move = self.env['account.move.line']
        if form['filter'] == 'unreconciled':
            reconcil = False
        if form['result_selection'] == 'supplier':
            ACCOUNT_TYPE = ['payable']
        elif form['result_selection'] == 'customer':
            ACCOUNT_TYPE = ['receivable']
        else:
            ACCOUNT_TYPE = ['payable','receivable']
                    
        self._cr.execute(
            "SELECT a.id " \
            "FROM account_account a " \
            "LEFT JOIN account_account_type t " \
                "ON (a.user_type=t.id) " \
                'WHERE t.type IN %s' \
                "AND a.deprecated is False", (tuple(ACCOUNT_TYPE), ))
        account_ids = [a for (a,) in self._cr.fetchall()]        
        query = obj_move.with_context(form.get('used_context', {}))._query_get(obj='l')
        if reconcil:
            RECONCILE_TAG = " "
        else:
            RECONCILE_TAG = "AND l.reconcile_id IS NULL"        
        return move_state, ACCOUNT_TYPE, account_ids, query, RECONCILE_TAG

    @api.multi
    def lines(self, form):
        obj_move = self.env['account.move.line']
        move_state, ACCOUNT_TYPE, account_ids, query, RECONCILE_TAG = self.get_type_account_ids(form)
        full_account = []
        self._cr.execute(
            "SELECT l.id, l.date, j.code, acc.code as a_code, acc.name as a_name, l.ref, m.name as move_name, l.name, l.debit, l.credit, l.amount_currency,l.currency_id, c.symbol AS currency_code " \
            "FROM account_move_line l " \
            "LEFT JOIN account_journal j " \
                "ON (l.journal_id = j.id) " \
            "LEFT JOIN account_account acc " \
                "ON (l.account_id = acc.id) " \
            "LEFT JOIN res_currency c ON (l.currency_id=c.id)" \
            "LEFT JOIN account_move m ON (m.id=l.move_id)" \
            "WHERE l.partner_id = %s " \
                "AND l.account_id IN %s  " + query +" " \
                "AND m.state IN %s " \
                " " + RECONCILE_TAG + " "\
                "ORDER BY l.date",
                (self.id, tuple(account_ids), tuple(move_state)))
        res = self._cr.dictfetchall()
        sum = 0.0
        ctx2 = form.get('used_context',{}).copy()
                        
        if form['initial_balance']:
            ctx2.update({'initial_bal': True})
        init_query = obj_move.with_context(ctx2)._query_get(obj='l')        
        if form['initial_balance']:
            self._cr.execute(
                    "SELECT sum(debit), sum(credit), COALESCE(sum(debit-credit), 0.0) " \
                    "FROM account_move_line AS l, " \
                    "account_move AS m "
                    "WHERE l.partner_id = %s" \
                        "AND m.id = l.move_id " \
                        "AND m.state IN %s "
                        "AND account_id IN %s" \
                        " " + RECONCILE_TAG + " " \
                        "" + init_query + " ",
                    (self.id, tuple(move_state), tuple(account_ids)))
            contemp = self._cr.fetchone()        
            sum = contemp[2]
        for r in res:
            sum += r['debit'] - r['credit']
            r['progress'] = sum
            full_account.append(r)
        return full_account

    @api.multi
    def sum_debit_credit_partner(self, form):
        obj_move = self.env['account.move.line']
        result_tmp_debit = 0.0
        result_init_debit = 0.0
        result_tmp_credit = 0.0
        result_init_credit = 0.0  
        init_debit = 0.0
        init_credit = 0.0
        init_bal_sum = 0.0  
        res = {}
        move_state, ACCOUNT_TYPE, account_ids, query,RECONCILE_TAG = self.get_type_account_ids(form)
        ctx2 = form.get('used_context',{}).copy()
                        
        if form['initial_balance']:
            ctx2.update({'initial_bal': True})
        init_query = obj_move.with_context(ctx2)._query_get(obj='l')        

        if form['initial_balance']:
            self._cr.execute(
                    "SELECT sum(debit), sum(credit), COALESCE(sum(debit-credit), 0.0) " \
                    "FROM account_move_line AS l, " \
                    "account_move AS m "
                    "WHERE l.partner_id = %s" \
                        "AND m.id = l.move_id " \
                        "AND m.state IN %s "
                        "AND account_id IN %s" \
                        " " + RECONCILE_TAG + " " \
                        "" + init_query + " ",
                    (self.id, tuple(move_state), tuple(account_ids)))
            contemp = self._cr.fetchone()
            if contemp != None:
                init_bal_sum = contemp[2]
                init_debit = contemp[0]
                init_credit = contemp[1]
                result_init_debit = contemp[0] or 0.0
                result_init_credit = contemp[1] or 0.0
            else:
                result_init_debit = result_tmp_debit + 0.0
                result_init_credit = result_tmp_credit + 0.0

        self._cr.execute(
                "SELECT sum(debit), sum(credit) " \
                "FROM account_move_line AS l, " \
                "account_move AS m "
                "WHERE l.partner_id = %s " \
                    "AND m.id = l.move_id " \
                    "AND m.state IN %s "
                    "AND account_id IN %s" \
                    " " + RECONCILE_TAG + " " \
                    " " + query + " ",\
                (self.id, tuple(move_state), tuple(account_ids),))

        contemp = self._cr.fetchone()
        if contemp != None:
            result_tmp_debit = contemp[0] or 0.0
            result_tmp_credit = contemp[1] or 0.0
        else:
            result_tmp_debit = result_tmp_debit + 0.0
            result_tmp_credit = result_tmp_credit + 0.0
            
        res['debit'] = result_tmp_debit  + result_init_debit
        res['credit'] = result_tmp_credit  + result_init_credit
        res['init_bal_sum'] = {'init_balance': init_bal_sum, 'debit': init_debit, 'credit': init_credit}
        return res
        
        
    @api.multi
    def _credit_debit_get(self):
        ctx = dict(self._context or {})
        ctx['all_fiscalyear'] = True
        query = self.env['account.move.line'].with_context(ctx)._query_get()
        if not self.ids:
            self.debit = 0
            self.credit = 0
            return True
        self._cr.execute("""SELECT l.partner_id, act.type, SUM(l.debit-l.credit)
                      FROM account_move_line l
                      LEFT JOIN account_account a ON (l.account_id=a.id)
                      LEFT JOIN account_account_type act ON (a.user_type=act.id)
                      WHERE act.type IN ('receivable','payable')
                      AND l.partner_id IN %s
                      AND l.reconcile_id IS NULL
                      """ + query + """
                      GROUP BY l.partner_id, act.type
                      """,
                   (tuple(self.ids),))
        maps = {'receivable':'credit', 'payable':'debit' }
        for partner in self:
            partner.debit = 0
            partner.credit = 0
        for pid, type, val in self._cr.fetchall():
            if val is None: val=0
            value = {maps[type]: (type=='receivable') and val or -val}
            self.browse(pid).write(value)

    @api.multi
    def _asset_difference_search(self, type, args):
        if not args:
            return []
        having_values = tuple(map(itemgetter(2), args))
        where = ' AND '.join(
            map(lambda x: '(SUM(bal2) %(operator)s %%s)' % {
                                'operator':x[1]},args))
        query = self.env['account.move.line']._query_get()
        self._cr.execute(('SELECT pid AS partner_id, SUM(bal2) FROM ' \
                    '(SELECT CASE WHEN bal IS NOT NULL THEN bal ' \
                    'ELSE 0.0 END AS bal2, p.id as pid FROM ' \
                    '(SELECT (debit-credit) AS bal, partner_id ' \
                    'FROM account_move_line l ' \
                    'WHERE account_id IN ' \
                            '(SELECT id FROM account_account '\
                            'WHERE type=%s AND active) ' \
                    'AND reconcile_id IS NULL ' \
                    'AND '+query+') AS l ' \
                    'RIGHT JOIN res_partner p ' \
                    'ON p.id = partner_id ) AS pl ' \
                    'GROUP BY pid HAVING ' + where), 
                    (type,) + having_values)
        res = self._cr.fetchall()
        if not res:
            return [('id','=','0')]
        return [('id','in',map(itemgetter(0), res))]

    @api.multi
    def _credit_search(self, args):
        return self._asset_difference_search('receivable', args)

    @api.multi
    def _debit_search(self, args):
        return self._asset_difference_search('payable', args)

    @api.multi
    def _invoice_total(self):
        account_invoice_report = self.env['account.invoice.report']
        if not self.ids:
            self.total_invoiced = 0.0
            return True
        for partner in self:
            invoices = account_invoice_report.search([('partner_id', 'child_of', partner.id)])
            partner.total_invoiced = sum(inv.user_currency_price_total for inv in invoices)

    @api.multi
    def _journal_item_count(self):
        for partner in self:
            partner.journal_item_count = self.env['account.move.line'].search_count([('partner_id', '=', partner.id)])
            partner.contracts_count = self.env['account.analytic.account'].search_count([('partner_id', '=', partner.id)])

    @api.one
    def has_something_to_reconcile(self):
        '''
        at least a debit, a credit and a line older than the last reconciliation date of the partner
        '''
        self._cr.execute('''
            SELECT l.partner_id, SUM(l.debit) AS debit, SUM(l.credit) AS credit
            FROM account_move_line l
            RIGHT JOIN account_account a ON (a.id = l.account_id)
            RIGHT JOIN res_partner p ON (l.partner_id = p.id)
            WHERE a.reconcile IS TRUE
            AND p.id = %s
            AND l.reconcile_id IS NULL
            AND (p.last_time_entries_checked IS NULL OR l.date > p.last_time_entries_checked)
            GROUP BY l.partner_id''', (self.id,))
        res = self._cr.dictfetchone()
        if res:
            return bool(res['debit'] and res['credit'])
        return False

    @api.multi
    def mark_as_reconciled(self):
        return self.write({'last_time_entries_checked': time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)})
        
    @api.multi
    def get_move_line(self):
        moveline_obj = self.env['account.move.line']
        return self.env['account.move.line'].search(
                [('partner_id', '=', self.id),
                    ('account_id.user_type.type', 'in', ['receivable', 'payable']),
                    ('reconcile_id', '=', False)])
    @api.multi
    def get_due_mat_paid_amount(self):
        move_line_ids = self.get_move_line()
        res = {}
        res['due_amount'] = reduce(lambda x, y: x + ((y.account_id.user_type.type == 'receivable' and y.debit or 0) or (y.account_id.user_type.type == 'payable' and y.credit * -1 or 0)), move_line_ids, 0)
        res['paid_amount'] = reduce(lambda x, y: x + ((y.account_id.user_type.type == 'receivable' and y.credit or 0) or (y.account_id.user_type.type == 'payable' and y.debit * -1 or 0)),  move_line_ids, 0)
        res['mat_amount'] = reduce(lambda x, y: x + (y.debit - y.credit), filter(lambda x: x.date_maturity < time.strftime('%Y-%m-%d'), move_line_ids), 0)
        return res

    vat_subjected = fields.Boolean('VAT Legal Statement', 
        help="Check this box if the partner is subjected to the VAT. It will be used for the VAT legal statement.")
    credit = fields.Float(compute='_credit_debit_get', search=_credit_search, 
        string='Total Receivable', help="Total amount this customer owes you.")
    debit = fields.Float(compute='_credit_debit_get', search=_debit_search, string='Total Payable', 
        help="Total amount you have to pay to this supplier.")
    debit_limit = fields.Float('Payable Limit')
    total_invoiced = fields.Float(compute='_invoice_total', string="Total Invoiced",
        groups='account.group_account_invoice')

    contracts_count = fields.Integer(compute='_journal_item_count', string="Contracts", type='integer')
    journal_item_count = fields.Integer(compute='_journal_item_count', string="Journal Items", type="integer")
    property_account_payable = fields.Many2one('account.account', company_dependent=True,
        string="Account Payable",
        domain="[('type', '=', 'payable'), ('deprecated', '=', False)]",
        help="This account will be used instead of the default one as the payable account for the current partner",
        required=True)
    property_account_receivable = fields.Many2one('account.account', company_dependent=True,
        string="Account Receivable",
        domain="[('type', '=', 'receivable'), ('deprecated', '=', False)]",
        help="This account will be used instead of the default one as the receivable account for the current partner",
        required=True)
    property_account_position = fields.Many2one('account.fiscal.position', company_dependent=True, 
        string="Fiscal Position",
        help="The fiscal position will determine taxes and accounts used for the partner.")
    property_payment_term = fields.Many2one('account.payment.term', company_dependent=True, 
        string ='Customer Payment Term',
        help="This payment term will be used instead of the default one for sale orders and customer invoices")
    property_supplier_payment_term = fields.Many2one('account.payment.term', company_dependent=True, 
         string ='Supplier Payment Term',
         help="This payment term will be used instead of the default one for purchase orders and supplier invoices")
    ref_companies = fields.One2many('res.company', 'partner_id',
        string='Companies that refers to partner')
    last_time_entries_checked = fields.Datetime(oldname='last_reconciliation_date',
        string='Latest Manual Reconciliation Date', readonly=True, copy=False,
        help='Last time the manual reconciliation was performed for this partner. '
             'It is set either if there\'s not at least an unreconciled debit and an unreconciled credit '
             'or if you click the "Done" button.')
    current_date = fields.Date(string='Current Date', default=fields.Date.context_today)
    
    @api.model
    def _commercial_fields(self):
        return super(res_partner, self)._commercial_fields() + \
            ['debit_limit', 'property_account_payable', 'property_account_receivable', 'property_account_position',
             'property_payment_term', 'property_supplier_payment_term', 'last_time_entries_checked']
