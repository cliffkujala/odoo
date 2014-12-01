# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
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

import time

from openerp import models, fields, api, _
from openerp.exceptions import except_orm, Warning

import openerp.addons.decimal_precision as dp

@api.model
def _employee_get(self):
    employee = self.env['hr.employee'].search([('user_id', '=', self._uid)])
    if employee:
        return employee.id
    return False
    
class hr_expense_expense(models.Model):

    @api.multi
    @api.depends('line_ids.unit_amount','line_ids.unit_quantity')
    def _amount(self):
        for expense in self.line_ids:
            self.amount += expense.unit_amount * expense.unit_quantity

    @api.model
    def _get_currency(self):
        return self.env.user.company_id.currency_id.id

    _name = "hr.expense.expense"
    _inherit = ['mail.thread', 'ir.needaction_mixin']
    _description = "Expense"
    _order = "id desc"
    _track = {
        'state': {
            'hr_expense.mt_expense_approved': lambda self, cr, uid, obj, ctx=None: obj.state == 'accepted',
            'hr_expense.mt_expense_refused': lambda self, cr, uid, obj, ctx=None: obj.state == 'cancelled',
            'hr_expense.mt_expense_confirmed': lambda self, cr, uid, obj, ctx=None: obj.state == 'confirm',
        },
    }

    name = fields.Char(string='Description', readonly=True, states={'draft':[('readonly',False)], 'confirm':[('readonly',False)]})
    #id = fields.Integer(string='Sheet ID', readonly=True)
    date = fields.Date(string='Date', select=True, readonly=True, states={'draft':[('readonly',False)], 'confirm':[('readonly',False)]}, default=fields.Date.context_today)
    journal_id = fields.Many2one('account.journal', string='Force Journal', help = "The journal used when the expense is done.")
    employee_payable_account_id = fields.Many2one('account.account', string='Employee Account', help="Employee payable account")
    employee_id = fields.Many2one('hr.employee', string="Employee", required=True, readonly=True, states={'draft':[('readonly',False)], 'confirm':[('readonly',False)]}, default=_employee_get)
    user_id = fields.Many2one('res.users', string='User', required=True, default=lambda self: self.env.user)
    date_confirm = fields.Date(string='Confirmation Date', select=True, copy=False,
                                help="Date of the confirmation of the sheet expense. It's filled when the button Confirm is pressed.")
    date_valid = fields.Date(string='Validation Date', select=True, copy=False,
                              help="Date of the acceptation of the sheet expense. It's filled when the button Accept is pressed.")
    user_valid = fields.Many2one('res.users', string='Validation By', readonly=True, copy=False,
                                  states={'draft':[('readonly',False)], 'confirm':[('readonly',False)]})
    account_move_id = fields.Many2one('account.move', string='Ledger Posting', copy=False, track_visibility="onchange")
    line_ids = fields.One2many('hr.expense.line', 'expense_id', string='Expense Lines', copy=True,
                                readonly=True, states={'draft':[('readonly',False)]} )
    note = fields.Text('Note')
    amount = fields.Float(compute='_amount', string='Total Amount', digits=dp.get_precision('Account'), store=True)
    currency_id = fields.Many2one('res.currency', string='Currency', required=True, readonly=True, states={'draft':[('readonly',False)], 'confirm':[('readonly',False)]}, default=_get_currency)
    department_id = fields.Many2one('hr.department', string='Department', readonly=True, states={'draft':[('readonly',False)], 'confirm':[('readonly',False)]})
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.user.company_id)
    state = fields.Selection([
        ('draft', 'New'),
        ('cancelled', 'Refused'),
        ('confirm', 'Waiting Approval'),
        ('accepted', 'Approved'),
        ('done', 'Waiting Payment'),
        ('paid', 'Paid'),
        ],
        string='Status', readonly=True, track_visibility='onchange', copy=False, default='draft',
        help='When the expense request is created the status is \'Draft\'.\n It is confirmed by the user and request is sent to admin, the status is \'Waiting Confirmation\'.\
        \nIf the admin accepts it, the status is \'Accepted\'.\n If the accounting entries are made for the expense request, the status is \'Waiting Payment\'.')

    @api.multi
    def unlink(self):
        if self.state != 'draft':
            raise Warning(_('You can only delete draft expenses!'))
        return super(hr_expense_expense, self).unlink()

    @api.multi
    def onchange_currency_id(self, currency_id=False, company_id=False):
        res =  {'value': {'journal_id': False}}
        account_journal = self.env['account.journal'].search([('type','=','purchase'), ('currency','=',currency_id), ('company_id', '=', company_id)])
        if account_journal:
            res['value']['journal_id'] = account_journal.id
        return res

    @api.multi
    def onchange_employee_id(self, employee_id):
        emp_obj = self.env['hr.employee']
        department_id = False
        employee_payable_account_id = False
        company_id = False
        if employee_id:
            employee = emp_obj.browse(employee_id)
            department_id = employee.department_id.id
            company_id = employee.company_id.id
            if employee.address_home_id and employee.address_home_id.property_account_payable:
                employee_payable_account_id = employee.address_home_id.property_account_payable.id
        return {'value': {'department_id': department_id, 'company_id': company_id, 'employee_payable_account_id': employee_payable_account_id}}

    @api.multi
    def expense_confirm(self):
        if not self.line_ids:
            raise except_orm(_('Error!'), _('You cannot submit expense which has no expense line.'))
        if self.employee_id and self.employee_id.parent_id.user_id:
            self.message_subscribe_users(user_ids=self.employee_id.parent_id.user_id.ids)
        return self.write({'state': 'confirm', 'date_confirm': time.strftime('%Y-%m-%d')})

    @api.multi
    def expense_accept(self):
        return self.write({'state': 'accepted', 'date_valid': time.strftime('%Y-%m-%d'), 'user_valid': self._uid})

    @api.multi
    def expense_canceled(self):
        return self.write({'state': 'cancelled'})

    @api.multi
    def account_move_get(self):
        '''
        This method prepare the creation of the account move related to the given expense.

        :param expense_id: Id of expense for which we are creating account_move.
        :return: mapping between fieldname and value of account move to create
        :rtype: dict
        '''
        journal_id = False
        if self.journal_id:
            journal_id = self.journal_id.id
        else:
            journal_id = self.env['account.journal'].search([('type', '=', 'purchase'), ('company_id', '=', self.company_id.id)], limit=1)
            if not journal_id:
                raise except_orm(_('Error!'), _("No expense journal found. Please make sure you have a journal with type 'purchase' configured."))
            journal_id = journal_id.id
        return self.env['account.move'].account_move_prepare(journal_id, date=self.date_confirm, ref=self.name, company_id=self.company_id.id)

    @api.model
    def line_get_convert(self, x, part, date):
        partner_id  = self.env['res.partner']._find_accounting_partner(part).id
        return {
            'date_maturity': x.get('date_maturity', False),
            'partner_id': partner_id,
            'name': x['name'][:64],
            'date': date,
            'debit': x['price']>0 and x['price'],
            'credit': x['price']<0 and -x['price'],
            'account_id': x['account_id'],
            'analytic_lines': x.get('analytic_lines', False),
            'amount_currency': x['price']>0 and abs(x.get('amount_currency', False)) or -abs(x.get('amount_currency', False)),
            'currency_id': x.get('currency_id', False),
            'tax_code_id': x.get('tax_code_id', False),
            'tax_amount': x.get('tax_amount', False),
            'ref': x.get('ref', False),
            'quantity': x.get('quantity',1.00),
            'product_id': x.get('product_id', False),
            'product_uom_id': x.get('uos_id', False),
            'analytic_account_id': x.get('account_analytic_id', False),
        }

    @api.model
    def compute_expense_totals(self, company_currency, ref, account_move_lines):
        '''
        internal method used for computation of total amount of an expense in the company currency and
        in the expense currency, given the account_move_lines that will be created. It also do some small
        transformations at these account_move_lines (for multi-currency purposes)
        
        :param account_move_lines: list of dict
        :rtype: tuple of 3 elements (a, b ,c)
            a: total in company currency
            b: total in hr.expense currency
            c: account_move_lines potentially modified
        '''
        context = dict(date=self.date_confirm or time.strftime('%Y-%m-%d'))
        total = 0.0
        total_currency = 0.0
        for i in account_move_lines:
            if self.currency_id.id != company_currency:
                i['currency_id'] = self.currency_id.id
                i['amount_currency'] = i['price']
                i['price'] = self.currency_id.with_context(context).compute(company_currency, i['price'])
            else:
                i['amount_currency'] = False
                i['currency_id'] = False
            total -= i['price']
            total_currency -= i['amount_currency'] or i['price']
        return total, total_currency, account_move_lines
    
    @api.multi
    def action_move_create(self):
        '''
        main function that is called when trying to create the accounting entries related to an expense
        '''
        if not self.employee_payable_account_id:
            raise except_orm(_('Error!'), _('No employee account payable found for the expense '))

        company_currency = self.company_id.currency_id.id
        diff_currency_p = self.currency_id.id != company_currency

        #create the move that will contain the accounting entries
        move = self.env['account.move'].create(self.account_move_get())
        
        #one account.move.line per expense line (+taxes..)
        eml = self.move_line_get()

        #create one more move line, a counterline for the total on payable account
        total, total_currency, eml = self.compute_expense_totals(company_currency, self.name, eml)

        acc = self.employee_payable_account_id.id or False
        eml.append({
                'type': 'dest',
                'name': '/',
                'price': total,
                'account_id': acc,
                'date_maturity': self.date_confirm,
                'amount_currency': diff_currency_p and total_currency or False,
                'currency_id': diff_currency_p and self.currency_id.id or False, 
                'ref': self.name
                })

        #convert eml into an osv-valid format
        lines = map(lambda x:(0,0,self.line_get_convert(x, self.employee_id.company_id.partner_id, self.date_confirm)), eml)
        journal_id = move.journal_id
        # post the journal entry if 'Skip 'Draft' State for Manual Entries' is checked
        if journal_id.entry_posted:
            move.button_validate()
        move.write({'line_id': lines})
        self.write({'account_move_id': move.id, 'state': 'done'})
        return True

    @api.multi
    def move_line_get(self):
        res = []
        tax_obj = self.env['account.tax']
        for line in self.line_ids:
            mres = self.move_line_get_item(line)
            if not mres:
                continue
            res.append(mres)
            #Taken from product_id_onchange in account.invoice
            if line.product_id:
                fpos_obj = self.env['account.fiscal.position']
            tax_l = []
            base_tax_amount = line.total_amount
            #Calculating tax on the line and creating move?
            for tax in tax_obj.compute_all(line.unit_amount, line.unit_quantity, line.product_id, self.user_id.partner_id)['taxes']:
                tax_code_id = tax['base_code_id']
                if not tax_code_id:
                    continue
                res[-1]['tax_code_id'] = tax_code_id
                ## 
                is_price_include = tax_obj.read(tax['id'],['price_include'])['price_include']
                if is_price_include:
                    ## We need to deduce the price for the tax
                    res[-1]['price'] = res[-1]['price']  - (tax['amount'] * tax['base_sign'] or 0.0)
                    # tax amount countains base amount without the tax
                    base_tax_amount = (base_tax_amount - tax['amount']) * tax['base_sign']
                else:
                    base_tax_amount = base_tax_amount * tax['base_sign']

                assoc_tax = {
                             'type':'tax',
                             'name':tax['name'],
                             'price_unit': tax['price_unit'],
                             'quantity': 1,
                             'price':  tax['amount'] * tax['base_sign'] or 0.0,
                             'account_id': tax['account_collected_id'] or mres['account_id'],
                             'tax_code_id': tax['tax_code_id'],
                             'tax_amount': tax['amount'] * tax['base_sign'],
                             }
                tax_l.append(assoc_tax)
            res[-1]['tax_amount'] = self.currency_id.compute(base_tax_amount, self.company_id.currency_id)
            res += tax_l
        return res

    @api.multi
    def move_line_get_item(self,line):
        company = line.expense_id.company_id
        if line.product_id:
            acc = line.product_id.property_account_expense
            if not acc:
                acc = line.product_id.categ_id.property_account_expense_categ
            if not acc:
                raise except_orm(_('Error!'), _('No purchase account found for the product %s (or for his category), please configure one.') % (line.product_id.name))
        else:
            acc = self.env['ir.property'].get(cr, uid, 'property_account_expense_categ', 'product.category', context={'force_company': company.id})
            if not acc:
                raise except_orm(_('Error!'), _('Please configure Default Expense account for Product purchase: `property_account_expense_categ`.'))
        return {
            'type':'src',
            'name': line.name.split('\n')[0][:64],
            'price_unit':line.unit_amount,
            'quantity':line.unit_quantity,
            'price':line.total_amount,
            'account_id':acc.id,
            'product_id':line.product_id.id,
            'uos_id':line.uom_id.id,
            'account_analytic_id':line.analytic_account.id,
        }

    @api.multi
    def action_view_move(self):
        '''
        This function returns an action that display existing account.move of given expense ids.
        '''
        assert len(self._ids) == 1, 'This option should only be used for a single id at a time'
        assert self.account_move_id
        try:
            view_id = self.env['ir.model.data'].xmlid_to_res_id('account.view_move_form')
        except ValueError, e:
            view_id = False
        result = {
            'name': _('Expense Account Move'),
            'view_type': 'form',
            'view_mode': 'form',
            'view_id': view_id,
            'res_model': 'account.move',
            'type': 'ir.actions.act_window',
            'nodestroy': True,
            'target': 'current',
            'res_id': self.account_move_id.id,
        }
        return result


class product_template(models.Model):
    _inherit = "product.template"
    
    hr_expense_ok = fields.Boolean(string='Can be Expensed', help="Specify if the product can be selected in an HR expense line.")
    

class hr_expense_line(models.Model):
    _name = "hr.expense.line"
    _description = "Expense Line"
    _inherit = ['mail.thread', 'ir.needaction_mixin']

    @api.one
    @api.depends('unit_quantity','unit_amount')
    def _amount(self):
        if not self.ids:
            return {}
        self._cr.execute("SELECT l.id,COALESCE(SUM(l.unit_amount*l.unit_quantity),0) AS amount FROM hr_expense_line l WHERE id IN %s GROUP BY l.id ",(tuple(self.ids),))
        for id, amount in self._cr.fetchall():
            self.total_amount = amount

    @api.model
    def _get_uom_id(self):
        return self.env['ir.model.data'].xmlid_to_res_id('product.product_uom_unit')

    name = fields.Char(string='Expense Note', required=True)
    date = fields.Date(string='Date', required=True, default=fields.Date.context_today)
    expense_id = fields.Many2one('hr.expense.expense', string='Expense', ondelete='cascade', select=True)
    total_amount = fields.Float(string='Total', store=True, compute='_amount', digits=dp.get_precision('Account'))
    unit_amount = fields.Float(string='Unit Price', digits=dp.get_precision('Product Price'))
    unit_quantity = fields.Float(string='Quantity', digits= dp.get_precision('Product Unit of Measure'), default=1)
    product_id = fields.Many2one('product.product', string='Product', domain=[('hr_expense_ok','=',True)])
    uom_id = fields.Many2one('product.uom', string='Unit of Measure', required=True, default=_get_uom_id)
    description = fields.Text(string='Description')
    analytic_account = fields.Many2one('account.analytic.account', string='Analytic account')
    ref = fields.Char(string='Reference')
    sequence = fields.Integer(string='Sequence', select=True, help="Gives the sequence order when displaying a list of expense lines.")
    employee_id = fields.Many2one('hr.employee', string="Employee", required=True)
    state = fields.Selection([
        ('draft', 'New'),
        ('confirm', 'Submitted'),
        ('accepted', 'Approved'),
        ('cancel', 'Cancelled'),
        ],
        string='Status', readonly=True, track_visibility='onchange', copy=False, default='draft')
    expense_line_tax_id = fields.Many2many('account.tax','expense_line_tax', 'expense_line_id', 'tax_id',string='Taxes')

    _order = "sequence, date"

    @api.multi
    def onchange_product_id(self, product_id):
        res = {}
        if product_id:
            product = self.env['product.product'].browse(product_id)
            res['name'] = product.name
            amount_unit = product.price_get('standard_price')[product.id]
            res['unit_amount'] = amount_unit
            res['uom_id'] = product.uom_id.id
        return {'value': res}

    @api.multi
    def onchange_uom(self, product_id, uom_id):
        res = {'value':{}}
        if not uom_id or not product_id:
            return res
        product = self.env['product.product'].browse(product_id)
        uom = self.env['product.uom'].browse(uom_id)
        if uom.category_id.id != product.uom_id.category_id.id:
            res['warning'] = {'title': _('Warning'), 'message': _('Selected Unit of Measure does not belong to the same category as the product Unit of Measure')}
            res['value'].update({'uom_id': product.uom_id.id})
        return res

    @api.multi
    def expense_line_new_to_confirm_status(self):
        hr_expense_expense = self.env['hr.expense.expense']
        hr_expense_ids = hr_expense_expense.search([('state','in', ['draft','confirm'])])
        if not hr_expense_ids :
            self.write({'expense_id': hr_expense_expense.create({}).id, 'state':'confirm'})
        else :
            self.write({'expense_id':hr_expense_ids.id, 'state':'confirm'})

    @api.multi
    def expense_line_submit_to_approved_status(self):
        return self.write({'state':'accepted'})

    @api.multi
    def expense_line_submit_to_canceled_status(self):
        return self.write({'state':'cancel'})


class account_move_line(models.Model):
    _inherit = "account.move.line"

    @api.multi
    def reconcile(self, type='auto', writeoff_acc_id=False, writeoff_period_id=False, writeoff_journal_id=False):
        res = super(account_move_line, self).reconcile(type=type, writeoff_acc_id=writeoff_acc_id, writeoff_period_id=writeoff_period_id, writeoff_journal_id=writeoff_journal_id)
        #when making a full reconciliation of account move lines 'ids', we may need to recompute the state of some hr.expense
        if self.move_id.ids:
            expense = self.env['hr.expense.expense'].search([('account_move_id', 'in', self.move_id.ids)])
            if expense.state == 'done':
                #making the postulate it has to be set paid, then trying to invalidate it
                new_status_is_paid = True
                for aml in expense.account_move_id.line_id:
                    if aml.account_id.type == 'payable' and not expense.company_id.currency_id.is_zero(aml.amount_residual):
                        new_status_is_paid = False
                if new_status_is_paid:
                    expense.write({'state': 'paid'})
        return res

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
