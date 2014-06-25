# -*- encoding: utf-8 -*-
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
from datetime import datetime
from dateutil.relativedelta import relativedelta

from openerp.osv import fields, osv
import openerp.addons.decimal_precision as dp
from openerp.tools.translate import _
import openerp

class account_asset_category(osv.osv):
    _name = 'account.asset.category'
    _description = 'Asset category'

    _columns = {
        'name': fields.char('Name', required=True, select=1),
        'note': fields.text('Note'),
        'account_analytic_id': fields.many2one('account.analytic.account', 'Analytic Account'),
        'account_asset_id': fields.many2one('account.account', 'Asset Account', required=True, domain=[('type','=','other')]),
        'account_income_recognition_id': fields.many2one('account.account', 'Recognition Income Account', domain=[('type','=','other')]),
        'account_depreciation_id': fields.many2one('account.account', 'Depreciation Account', required=True, domain=[('type','=','other')]),
        'account_expense_depreciation_id': fields.many2one('account.account', 'Depr. Expense Account', domain=[('type','=','other')]),
        'journal_id': fields.many2one('account.journal', 'Journal', required=True),
        'company_id': fields.many2one('res.company', 'Company', required=True),
        'method': fields.selection([('linear','Linear: Computed on basis of Gross Value / Number of Depreciations'),('degressive','Degressive: Computed on basis of Residual Value * Degressive Factor')], 'Computation Method', required=True, help="Choose the method to use to compute the amount of depreciation lines.\n"\
            "  * Linear: Calculated on basis of: Gross Value / Number of Depreciations\n" \
            "  * Degressive: Calculated on basis of: Residual Value * Degressive Factor"),
        'method_number': fields.integer('Number of Depreciations', help="The number of depreciations needed to depreciate your asset"),
        'method_period': fields.integer('Period Length', help="State here the time between 2 depreciations, in months", required=True),
        'method_progress_factor': fields.float('Degressive Factor'),
        'method_time': fields.selection([('number','Number of Depreciations'),('end','Ending Date')], 'Time Method', required=True,
                                  help="Choose the method to use to compute the dates and number of depreciation lines.\n"\
                                       "  * Number of Depreciations: Fix the number of depreciation lines and the time between 2 depreciations.\n" \
                                       "  * Ending Date: Choose the time between 2 depreciations and the date the depreciations won't go beyond."),
        'method_end': fields.date('Ending date'),
        'prorata':fields.boolean('Prorata Temporis', help='Indicates that the first depreciation entry for this asset have to be done from the purchase date instead of the first January'),
        'open_asset': fields.boolean('Skip Draft State', help="Check this if you want to automatically confirm the assets of this category when created by invoices."),
        'type': fields.selection([('sales','Sale: Revenue Recognition'),('purchase','Purchase: Asset')], 'Type', required=True, select=True),
    }

    _defaults = {
        'company_id': lambda self, cr, uid, context: self.pool.get('res.company')._company_default_get(cr, uid, 'account.asset.category', context=context),
        'method': 'linear',
        'method_number': 5,
        'method_time': 'number',
        'method_progress_factor': 0.3,
        'type': 'sales',
        'method_period': 1,
    }

    def onchange_account_asset(self, cr, uid, ids, account_asset_id, context=None):
        res = {'value':{}}
        if account_asset_id:
           res['value'] = {'account_depreciation_id': account_asset_id}
        return res
        
    def onchange_journal_id(self, cr, uid, ids, journal_id, type, context=None):
        res = {'value':{}}
        journal = self.pool['account.journal'].browse(cr, uid, journal_id, context=context)
        if journal:
            if type == 'sales':
                res['value'] = {'account_income_recognition_id': journal.default_credit_account_id.id}
            else:
                res['value'] = {'account_expense_depreciation_id': journal.default_debit_account_id.id}
        return res

    def onchange_type(self, cr, uid, ids, type, context=None):
        res = {'value':{'method_period': 12}}
        if type == 'sales':
            res['value'] = {'prorata': True,'method_period': 1}
        return res

class account_asset_asset(osv.osv):
    _name = 'account.asset.asset'
    _description = 'Asset/Recognition'
    _inherit = ['mail.thread', 'ir.needaction_mixin']

    def _get_category_type(self, cr, uid, ids, context=None):
        "Returns a dictionary of name and type for given asset ids."
        type = self.browse(cr, uid, ids, context=context)[0].category_id.type
        res = {'name': _('Installment'), 'type': _('Recognition')} if type == 'sales' else {'name': _('Depreciation'), 'type': _('Asset')}
        return res

    def unlink(self, cr, uid, ids, context=None):
        record = self.browse(cr, uid, ids, context=context)[0]
        res = self._get_category_type(cr, uid, ids, context=context)
        if record.state in ['open', 'close']:
            raise osv.except_osv(_('Error!'), _('You cannot delete an %s which is in %s state.') % (res.get('type'), record.state))
        if record.account_move_line_ids:
            raise osv.except_osv(_('Error!'), _('You cannot delete an %s that contains posted %s lines.') % (res.get('type'), res.get('name')))
        return super(account_asset_asset, self).unlink(cr, uid, ids, context=context)

    def _get_period(self, cr, uid, context=None):
        periods = self.pool.get('account.period').find(cr, uid, context=context)
        if periods:
            return periods[0]
        else:
            return False

    def _get_last_depreciation_date(self, cr, uid, ids, context=None):
        """
        @param id: ids of a account.asset.asset objects
        @return: Returns a dictionary of the effective dates of the last depreciation entry made for given asset ids. If there isn't any, return the purchase date of this asset
        """
        cr.execute("""
            SELECT a.id as id, COALESCE(MAX(l.date),a.date) AS date
            FROM account_asset_asset a
            LEFT JOIN account_move_line l ON (l.asset_id = a.id)
            WHERE a.id IN %s
            GROUP BY a.id, a.date """, (tuple(ids),))
        return dict(cr.fetchall())

    def _compute_board_amount(self, cr, uid, asset, i, residual_amount, amount_to_depr, undone_dotation_number, posted_depreciation_line_ids, total_days, depreciation_date, context=None):
        #by default amount = 0
        amount = 0
        if i == undone_dotation_number:
            amount = residual_amount
        else:
            if asset.method == 'linear':
                amount = amount_to_depr / (undone_dotation_number - len(posted_depreciation_line_ids))
                if asset.prorata and asset.category_id.type == 'purchase':
                    amount = amount_to_depr / asset.method_number
                    days = total_days - float(depreciation_date.strftime('%j'))
                    if i == 1:
                        amount = (amount_to_depr / asset.method_number) / total_days * days
                    elif i == undone_dotation_number:
                        amount = (amount_to_depr / asset.method_number) / total_days * (total_days - days)
            elif asset.method == 'degressive':
                amount = residual_amount * asset.method_progress_factor
                if asset.prorata:
                    days = total_days - float(depreciation_date.strftime('%j'))
                    if i == 1:
                        amount = (residual_amount * asset.method_progress_factor) / total_days * days
                    elif i == undone_dotation_number:
                        amount = (residual_amount * asset.method_progress_factor) / total_days * (total_days - days)
        return amount

    def _compute_board_undone_dotation_nb(self, cr, uid, asset, depreciation_date, total_days, context=None):
        undone_dotation_number = asset.method_number
        if asset.method_time == 'end':
            end_date = datetime.strptime(asset.method_end, '%Y-%m-%d')
            undone_dotation_number = 0
            while depreciation_date <= end_date:
                depreciation_date = (datetime(depreciation_date.year, depreciation_date.month, depreciation_date.day) + relativedelta(months=+asset.method_period))
                undone_dotation_number += 1
        if asset.prorata and asset.category_id.type == 'purchase':
            undone_dotation_number += 1
        return undone_dotation_number

    def compute_depreciation_board(self, cr, uid, ids, context=None):
        depreciation_lin_obj = self.pool.get('account.asset.depreciation.line')
        currency_obj = self.pool['res.currency']
        fiscal_year_obj = self.pool.get('account.fiscalyear')
        for asset in self.browse(cr, uid, ids, context=context):
            if asset.value_residual == 0.0:
                continue
            posted_depreciation_line_ids = depreciation_lin_obj.search(cr, uid, [('asset_id', '=', asset.id), ('move_check', '=', True)],order='depreciation_date desc')
            old_depreciation_line_ids = depreciation_lin_obj.search(cr, uid, [('asset_id', '=', asset.id), ('move_id', '=', False)])
            if old_depreciation_line_ids:
                depreciation_lin_obj.unlink(cr, uid, old_depreciation_line_ids, context=context)

            amount_to_depr = residual_amount = asset.value_residual
            if asset.prorata:
                depreciation_date = datetime.strptime(self._get_last_depreciation_date(cr, uid, [asset.id], context)[asset.id], '%Y-%m-%d')
            else:
                # Asset Purchase date & year
                date = datetime.strptime(asset.date, '%Y-%m-%d')
                #if we already have some previous validated entries, starting date isn't 1st January but last entry + method period
                if (len(posted_depreciation_line_ids)>0):
                    last_depreciation_date = datetime.strptime(depreciation_lin_obj.browse(cr,uid,posted_depreciation_line_ids[0],context=context).depreciation_date, '%Y-%m-%d')
                    depreciation_date = (last_depreciation_date+relativedelta(months=+asset.method_period))
                else:
                    # Fiscal year based on depreciation date of Asset
                    fiscal_year = fiscal_year_obj.search_read(cr, uid,
                                                              [('date_start', '<=', time.strftime('%Y-%m-%d')),
                                                               ('date_stop', '>=', time.strftime('%Y-%m-%d'))],
                                                              ['date_start'], context=context)
                    # Fiscal year should be there related to purchase date otherwise the journal items have wrong periods and date
                    if not fiscal_year:
                        action_id = self.pool['ir.model.data'].xmlid_to_res_id(cr, uid, 'account.action_account_fiscalyear')
                        msg = _('There is no period defined for this date: %s.\nPlease go to Configuration/Periods and configure a fiscal year.') % asset.date
                        raise openerp.exceptions.RedirectWarning(msg, action_id, _('Go to the configuration panel'))
                    fiscal_date = datetime.strptime(fiscal_year[0]['date_start'], '%Y-%m-%d')
                    depreciation_date = fiscal_date.replace(year=date.year)
            day = depreciation_date.day
            month = depreciation_date.month
            year = depreciation_date.year
            total_days = (year % 4) and 365 or 366

            undone_dotation_number = self._compute_board_undone_dotation_nb(cr, uid, asset, depreciation_date, total_days, context=context)
            dep_sequence = 0
            for dep_lines in depreciation_lin_obj.browse(cr, uid, sorted(posted_depreciation_line_ids, key=int), context=context):
                dep_sequence += 1
                depreciation_lin_obj.write(cr, uid, dep_lines.id, {'sequence': dep_sequence}, context=context)
            i = 1
            if posted_depreciation_line_ids:
               i+= len(posted_depreciation_line_ids)
            for x in range(len(posted_depreciation_line_ids), undone_dotation_number):
                amount = self._compute_board_amount(cr, uid, asset, i, residual_amount, amount_to_depr, undone_dotation_number, posted_depreciation_line_ids, total_days, depreciation_date, context=context)
                company_currency = asset.company_id.currency_id.id
                current_currency = asset.currency_id.id
                amount = currency_obj.round(cr, uid, asset.currency_id, amount)
                residual_amount -= amount
                vals = {
                     'amount': amount,
                     'asset_id': asset.id,
                     'sequence': i,
                     'name': (asset.code or str(asset.id)) +'/' + str(i),
                     'remaining_value': residual_amount,
                     'depreciated_value': (asset.value - asset.salvage_value) - (residual_amount + amount),
                     'depreciation_date': depreciation_date.strftime('%Y-%m-%d'),
                }
                depreciation_lin_obj.create(cr, uid, vals, context=context)
                # Considering Depr. Period as months
                depreciation_date = (datetime(year, month, day) + relativedelta(months=+asset.method_period))
                day = depreciation_date.day
                month = depreciation_date.month
                year = depreciation_date.year
                i += 1
        return True

    def validate(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        type = self._get_category_type(cr, uid, ids, context=context).get('type')
        self.message_post(cr, uid, ids, body=_("%s confirmed.") % type, context=context)
        return self.write(cr, uid, ids, {'state':'open'}, context=context)

    def set_to_close(self, cr, uid, ids, context=None):
        dep_line_obj = self.pool['account.asset.depreciation.line']
        res = self._get_category_type(cr, uid, ids, context=context)
        unposted_dep_line_ids = dep_line_obj.search(cr, uid,
                                                    [('asset_id', 'in', ids),
                                                     ('move_check', '=', False)],
                                                    order='depreciation_date desc',
                                                    context=context)
        if unposted_dep_line_ids:
            raise osv.except_osv(_('Error !'),
                                 _('You cannot close an %s which has unposted %s lines.')
                                 % (res.get('type'), res.get('name')))
        self.message_post(cr, uid, ids, body=_("%s closed.") % res.get('type'), context=context)
        return self.write(cr, uid, ids, {'state': 'close'}, context=context)

    def set_to_draft(self, cr, uid, ids, context=None):
        return self.write(cr, uid, ids, {'state': 'draft'}, context=context)

    def _amount_residual(self, cr, uid, ids, name, args, context=None):
        res = {}
        for asset in self.browse(cr, uid, ids, context):
            total_amount = sum(line.amount for line in asset.depreciation_line_ids if line.move_check)
            res[asset.id] = asset.value - total_amount - asset.salvage_value
        for id in ids:
            res.setdefault(id, 0.0)
        return res

    def onchange_company_id(self, cr, uid, ids, company_id=False, context=None):
        val = {}
        if company_id:
            company = self.pool.get('res.company').browse(cr, uid, company_id, context=context)
            if company.currency_id.company_id and company.currency_id.company_id.id != company_id:
                val['currency_id'] = False
            else:
                val['currency_id'] = company.currency_id.id
        return {'value': val}
    
    def onchange_purchase_salvage_value(self, cr, uid, ids, value, salvage_value, context=None):
        val = {}
        for asset in self.browse(cr, uid, ids, context=context):
            if value:
                val['value_residual'] = value - salvage_value
            if salvage_value:
                val['value_residual'] = value - salvage_value
        return {'value': val}    
    def _entry_count(self, cr, uid, ids, field_name, arg, context=None):
        MoveLine = self.pool('account.move.line')
        return {
            asset_id: MoveLine.search_count(cr, uid, [('asset_id', '=', asset_id)], context=context)
            for asset_id in ids
        }
    _columns = {
        'account_move_line_ids': fields.one2many('account.move.line', 'asset_id', 'Entries', readonly=True, states={'draft':[('readonly',False)]}),
        'entry_count': fields.function(_entry_count, string='# Asset Entries', type='integer'),
        'name': fields.char('Asset Name', required=True, readonly=True, states={'draft':[('readonly',False)]}),
        'code': fields.char('Reference', size=32, readonly=True, states={'draft':[('readonly',False)]}),
        'value': fields.float('Gross Value', required=True, readonly=True, digits_compute=dp.get_precision('Account'), states={'draft':[('readonly',False)]}),
        'currency_id': fields.many2one('res.currency','Currency',required=True, readonly=True, states={'draft':[('readonly',False)]}),
        'company_id': fields.many2one('res.company', 'Company', required=True, readonly=True, states={'draft':[('readonly',False)]}),
        'note': fields.text('Note'),
        'category_id': fields.many2one('account.asset.category', 'Category', required=True, change_default=True, readonly=True, states={'draft':[('readonly',False)]}),
        'parent_id': fields.many2one('account.asset.asset', 'Parent Asset', readonly=True, states={'draft':[('readonly',False)]}),
        'child_ids': fields.one2many('account.asset.asset', 'parent_id', 'Children Assets', copy=True),
        'date': fields.date('Date', required=True, readonly=True, states={'draft':[('readonly',False)]}),
        'state': fields.selection([('draft','Draft'),('open','Running'),('close','Close')], 'Status', required=True, copy=False,
                                  help="When an asset is created, the status is 'Draft'.\n" \
                                       "If the asset is confirmed, the status goes in 'Running' and the depreciation lines can be posted in the accounting.\n" \
                                       "You can manually close an asset when the depreciation is over. If the last line of depreciation is posted, the asset automatically goes in that status."),
        'active': fields.boolean('Active'),
        'partner_id': fields.many2one('res.partner', 'Partner', readonly=True, states={'draft':[('readonly',False)]}),
        'method': fields.selection([('linear','Linear: Computed on basis of Gross Value / Number of Depreciations'),('degressive','Degressive: Computed on basis of Residual Value * Degressive Factor')], 'Computation Method', required=True, readonly=True, states={'draft':[('readonly',False)]}, help="Choose the method to use to compute the amount of depreciation lines.\n"\
            "  * Linear: Calculated on basis of: Gross Value / Number of Depreciations\n" \
            "  * Degressive: Calculated on basis of: Residual Value * Degressive Factor"),
        'method_number': fields.integer('Number of Depreciations', readonly=True, states={'draft':[('readonly',False)]}, help="The number of depreciations needed to depreciate your asset"),
        'method_period': fields.integer('Number of Months in a Period', required=True, readonly=True, states={'draft':[('readonly',False)]}, help="The amount of time between two depreciations, in months"),
        'method_end': fields.date('Ending Date', readonly=True, states={'draft':[('readonly',False)]}),
        'method_progress_factor': fields.float('Degressive Factor', readonly=True, states={'draft':[('readonly',False)]}),
        'value_residual': fields.function(_amount_residual, method=True, digits_compute=dp.get_precision('Account'), string='Residual Value'),
        'method_time': fields.selection([('number','Number of Depreciations'),('end','Ending Date')], 'Time Method', required=True, readonly=True, states={'draft':[('readonly',False)]},
                                  help="Choose the method to use to compute the dates and number of depreciation lines.\n"\
                                       "  * Number of Depreciations: Fix the number of depreciation lines and the time between 2 depreciations.\n" \
                                       "  * Ending Date: Choose the time between 2 depreciations and the date the depreciations won't go beyond."),
        'prorata':fields.boolean('Prorata Temporis', readonly=True, states={'draft':[('readonly',False)]}, help='Indicates that the first depreciation entry for this asset have to be done from the purchase date instead of the first January / Start date of fiscal year'),
        'history_ids': fields.one2many('account.asset.history', 'asset_id', 'History', readonly=True),
        'depreciation_line_ids': fields.one2many('account.asset.depreciation.line', 'asset_id', 'Depreciation Lines', readonly=True, states={'draft':[('readonly',False)],'open':[('readonly',False)]}),
        'salvage_value': fields.float('Salvage Value', digits_compute=dp.get_precision('Account'), help="It is the amount you plan to have that you cannot depreciate.", readonly=True, states={'draft':[('readonly',False)]}),
        'invoice_id': fields.many2one('account.invoice','Invoice', states={'draft':[('readonly',False)]}, copy=False),
    }
    _defaults = {
        'code': lambda obj, cr, uid, context: obj.pool.get('ir.sequence').get(cr, uid, 'account.asset.code'),
        'date': lambda obj, cr, uid, context: time.strftime('%Y-%m-%d'),
        'active': True,
        'state': 'draft',
        'method': 'linear',
        'method_number': 5,
        'method_time': 'number',
        'method_period': 12,
        'method_progress_factor': 0.3,
        'currency_id': lambda self,cr,uid,c: self.pool.get('res.users').browse(cr, uid, uid, c).company_id.currency_id.id,
        'company_id': lambda self, cr, uid, context: self.pool.get('res.company')._company_default_get(cr, uid, 'account.asset.asset',context=context),
    }

    def _check_recursion(self, cr, uid, ids, context=None, parent=None):
        return super(account_asset_asset, self)._check_recursion(cr, uid, ids, context=context, parent=parent)
	
    def _check_recursion_msg(self, cr, uid, ids, context=None, parent=None):
        type = self._get_category_type(cr, uid, ids, context=context).get('type')
        return ' \n\n Error ! \n You cannot create recursive %s.' % type

    def _check_prorata(self, cr, uid, ids, context=None):
        for asset in self.browse(cr, uid, ids, context=context):
            if asset.prorata and asset.method_time != 'number':
                return False
        return True

    _constraints = [
        (_check_recursion, lambda self, *a, **kw: self._check_recursion_msg(*a, **kw), ['parent_id']),
        (_check_prorata, 'Prorata temporis can be applied only for time method "number of depreciations".', ['prorata']),
    ]

    def onchange_category_id(self, cr, uid, ids, category_id, context=None):
        res = {'value':{}}
        asset_categ_obj = self.pool.get('account.asset.category')
        if category_id:
            category_obj = asset_categ_obj.browse(cr, uid, category_id, context=context)
            res['value'] = {
                            'method': category_obj.method,
                            'method_number': category_obj.method_number,
                            'method_time': category_obj.method_time,
                            'method_period': category_obj.method_period,
                            'method_progress_factor': category_obj.method_progress_factor,
                            'method_end': category_obj.method_end,
                            'prorata': category_obj.prorata,
            }
        return res

    def onchange_method_time(self, cr, uid, ids, method_time='number', context=None):
        res = {'value': {}}
        if method_time != 'number':
            res['value'] = {'prorata': False}
        return res

    def copy(self, cr, uid, id, default=None, context=None):
        if default is None:
            default = {}
        asset = self.browse(cr, uid, id, context=context)
        default['name'] = asset.name+ _(' (copy)')
        return super(account_asset_asset, self).copy(cr, uid, id, default, context=context)

    def _compute_entries(self, cr, uid, ids, period_id, context=None):
        result = []
        period_obj = self.pool.get('account.period')
        depreciation_obj = self.pool.get('account.asset.depreciation.line')
        period = period_obj.browse(cr, uid, period_id, context=context)
        depreciation_ids = depreciation_obj.search(cr, uid, [('asset_id', 'in', ids), ('depreciation_date', '<=', period.date_stop), ('depreciation_date', '>=', period.date_start), ('move_check', '=', False)], context=context)
        context = dict(context or {}, depreciation_date=period.date_stop)
        return depreciation_obj.create_move(cr, uid, depreciation_ids, context=context)

    def create(self, cr, uid, vals, context=None):
        if context:
            context.update({'mail_create_nolog': True})
        asset_id = super(account_asset_asset, self).create(cr, uid, vals, context=context)
        self.compute_depreciation_board(cr, uid, [asset_id], context=context)
        type = self._get_category_type(cr, uid, [asset_id], context=context).get('type')
        self.message_post(cr, uid, [asset_id], body=_("%s created.") % type, context=context)
        return asset_id
    
    def write(self, cr, uid, ids, vals, context=None):
        res = super(account_asset_asset, self).write(cr, uid, ids, vals, context=context)
        # We need to compute the depreciation line if any changes is there in asset
        self.compute_depreciation_board(cr, uid, ids, context=context)
        return res
    
    def open_entries(self, cr, uid, ids, context=None):
        context = dict(context or {}, search_default_asset_id=ids, default_asset_id=ids)
        return {
            'name': _('Journal Items'),
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'account.move.line',
            'view_id': False,
            'type': 'ir.actions.act_window',
            'context': context,
        }


class account_asset_depreciation_line(osv.osv):
    _name = 'account.asset.depreciation.line'
    _description = 'Asset depreciation line'

    def _get_move_check(self, cr, uid, ids, name, args, context=None):
        res = {}
        for line in self.browse(cr, uid, ids, context=context):
            res[line.id] = bool(line.move_id)
        return res

    _columns = {
        'name': fields.char('Depreciation Name', required=True, select=1),
        'sequence': fields.integer('Sequence', required=True),
        'asset_id': fields.many2one('account.asset.asset', 'Asset', required=True, ondelete='cascade'),
        'parent_state': fields.related('asset_id', 'state', type='char', string='State of Asset'),
        'amount': fields.float('Current Depreciation', digits_compute=dp.get_precision('Account'), required=True),
        'remaining_value': fields.float('Next Period Depreciation', digits_compute=dp.get_precision('Account'),required=True),
        'depreciated_value': fields.float('Amount Already Depreciated', required=True),
        'depreciation_date': fields.date('Depreciation Date', select=1),
        'move_id': fields.many2one('account.move', 'Depreciation Entry'),
        'move_check': fields.function(_get_move_check, method=True, type='boolean', string='Posted', store=True, track_visibility='always')
    }

    def create_move(self, cr, uid, ids, context=None):
        context = dict(context or {})
        can_close = False
        asset_obj = self.pool.get('account.asset.asset')
        period_obj = self.pool.get('account.period')
        move_obj = self.pool.get('account.move')
        move_line_obj = self.pool.get('account.move.line')
        currency_obj = self.pool.get('res.currency')
        obj_sequence = self.pool.get('ir.sequence')
        created_move_ids = []
        asset_ids = []
        for line in self.browse(cr, uid, ids, context=context):
            depreciation_date = context.get('depreciation_date') or line.depreciation_date or time.strftime('%Y-%m-%d')
            period_ids = period_obj.find(cr, uid, depreciation_date, context=context)
            context.update({'date': depreciation_date})
            company_currency = line.asset_id.company_id.currency_id.id
            current_currency = line.asset_id.currency_id.id
            amount = currency_obj.compute(cr, uid, current_currency, company_currency, line.amount, context=context)
            sign = (line.asset_id.category_id.journal_id.type == 'purchase' or line.asset_id.category_id.journal_id.type == 'sale' and 1) or -1
            asset_name = line.asset_id.name
            reference = line.name
            seq_num = obj_sequence.next_by_id(cr, uid, line.asset_id.category_id.journal_id.sequence_id.id, context)
            move_vals = {
                'name': asset_name,
                'date': depreciation_date,
                'ref': reference,
                'period_id': period_ids and period_ids[0] or False,
                'journal_id': line.asset_id.category_id.journal_id.id,
                }
            move_id = move_obj.create(cr, uid, move_vals, context=context)
            journal_id = line.asset_id.category_id.journal_id.id
            partner_id = line.asset_id.partner_id.id
            categ_type = line.asset_id.category_id.type
            if categ_type == 'purchase': 
                debit_account = line.asset_id.category_id.account_expense_depreciation_id.id
                credit_acount = line.asset_id.category_id.account_depreciation_id.id
            else:
                debit_account = line.asset_id.category_id.account_asset_id.id
                credit_acount = line.asset_id.category_id.account_income_recognition_id.id
            move_line_obj.create(cr, uid, {
                'name': asset_name or reference,
                'ref': reference,
                'move_id': move_id,
                'account_id': credit_acount,
                'debit': 0.0,
                'credit': amount,
                'period_id': period_ids and period_ids[0] or False,
                'journal_id': journal_id,
                'partner_id': partner_id,
                'currency_id': company_currency != current_currency and  current_currency or False,
                'amount_currency': company_currency != current_currency and - sign * line.amount or 0.0,
                'analytic_account_id': line.asset_id.category_id.account_analytic_id.id if categ_type == 'sales' else False,
                'date': depreciation_date,
                'asset_id': line.asset_id.id if categ_type == 'sales' else False,
            })
            move_line_obj.create(cr, uid, {
                'name': asset_name or reference,
                'ref': reference,
                'move_id': move_id,
                'account_id': debit_account,
                'credit': 0.0,
                'debit': amount,
                'period_id': period_ids and period_ids[0] or False,
                'journal_id': journal_id,
                'partner_id': partner_id,
                'currency_id': company_currency != current_currency and  current_currency or False,
                'amount_currency': company_currency != current_currency and sign * line.amount or 0.0,
                'analytic_account_id': line.asset_id.category_id.account_analytic_id.id if categ_type == 'purchase' else False,
                'date': depreciation_date,
                'asset_id': line.asset_id.id if categ_type == 'purchase' else False
            })
            self.write(cr, uid, line.id, {'move_id': move_id}, context=context)
            created_move_ids.append(move_id)
            asset_ids.append(line.asset_id.id)
            partner_name = line.asset_id.partner_id.name
            currency_name = line.asset_id.currency_id.name
            msg_data = ['Depreciation','Supplier'] if categ_type == 'purchase' else ['Installment','Customer']
            msg=_("%s line posted. <br/> <b>&nbsp;&nbsp;&nbsp;&bull; Currency:</b> %s <br/> <b>&nbsp;&nbsp;&nbsp;&bull; Posted Amount:</b> %s <br/> <b>&nbsp;&nbsp;&nbsp;"
                "&bull; %s:</b> %s") % (msg_data[0], currency_name, line.amount, msg_data[1], partner_name)
            asset_obj.message_post(cr, uid, line.asset_id.id, body=msg, context=context)
        # we re-evaluate the assets to determine whether we can close them    
        for asset in asset_obj.browse(cr, uid, list(set(asset_ids)), context=context):
            if currency_obj.is_zero(cr, uid, asset.currency_id, asset.value_residual):
                name = 'Asset' if categ_type == 'purchase' else 'Recognition'
                asset_obj.message_post(cr, uid, asset.id, body=_("%s closed.") % name, context=context)
                asset.write({'state': 'close'})
                asset_obj.compute_depreciation_board(cr, uid, [], context=context)
        return created_move_ids

    def unlink(self, cr, uid, ids, context=None):
        for record in self.browse(cr, uid, ids, context=context):
            name = 'depreciation' if record.asset_id.category_id.type == 'purchase' else 'installment'
            if record.move_check:
                raise osv.except_osv(_('Error!'), _("You cannot delete posted %s lines.") % name)
        return super(account_asset_depreciation_line, self).unlink(cr, uid, ids, context=context)


class account_move_line(osv.osv):
    _inherit = 'account.move.line'
    _columns = {
        'asset_id': fields.many2one('account.asset.asset', 'Asset', ondelete="restrict"),
    }

class account_asset_history(osv.osv):
    _name = 'account.asset.history'
    _description = 'Asset history'
    _columns = {
        'name': fields.char('History name', select=1),
        'user_id': fields.many2one('res.users', 'User', required=True),
        'date': fields.date('Date', required=True),
        'asset_id': fields.many2one('account.asset.asset', 'Asset', required=True),
        'method_time': fields.selection([('number','Number of Depreciations'),('end','Ending Date')], 'Time Method', required=True,
                                  help="The method to use to compute the dates and number of depreciation lines.\n"\
                                       "Number of Depreciations: Fix the number of depreciation lines and the time between 2 depreciations.\n" \
                                       "Ending Date: Choose the time between 2 depreciations and the date the depreciations won't go beyond."),
        'method_number': fields.integer('Number of Depreciations', help="The number of depreciations needed to depreciate your asset"),
        'method_period': fields.integer('Period Length', help="Time in month between two depreciations"),
        'method_end': fields.date('Ending date'),
        'note': fields.text('Note'),
    }
    _order = 'date desc'
    _defaults = {
        'date': lambda *args: time.strftime('%Y-%m-%d'),
        'user_id': lambda self, cr, uid, ctx: uid
    }

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
