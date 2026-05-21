from odoo import models, fields, api, _

class ResCompany(models.Model):
    _inherit = 'res.company'

    # Foreign Procurement Configuration
    foreign_procurement_journal_id = fields.Many2one(
        'account.journal',
        string='Foreign Procurement Journal',
        domain="[('type', '=', 'general'), ('company_id', '=', id)]",
        help='Journal for foreign procurement transactions'
    )
    
    # Chart of Accounts for Foreign Procurement
    foreign_currency_payable_account_id = fields.Many2one(
        'account.account',
        string='Foreign Currency Payable Account',
        domain="[('account_type', '=', 'liability_payable'), ('company_id', '=', id)]",
        help='Account for foreign currency payables'
    )
    
    foreign_currency_receivable_account_id = fields.Many2one(
        'account.account',
        string='Foreign Currency Receivable Account',
        domain="[('account_type', '=', 'asset_receivable'), ('company_id', '=', id)]",
        help='Account for foreign currency receivables'
    )
    
    lc_margin_account_id = fields.Many2one(
        'account.account',
        string='LC Margin Account',
        domain="[('account_type', '=', 'asset_current'), ('company_id', '=', id)]",
        help='Account for LC margin deposits'
    )
    
    customs_duty_account_id = fields.Many2one(
        'account.account',
        string='Customs Duty Account',
        domain="[('account_type', '=', 'expense'), ('company_id', '=', id)]",
        help='Account for customs duties'
    )
    
    freight_charges_account_id = fields.Many2one(
        'account.account',
        string='Freight Charges Account',
        domain="[('account_type', '=', 'expense'), ('company_id', '=', id)]",
        help='Account for freight charges'
    )
    
    clearing_charges_account_id = fields.Many2one(
        'account.account',
        string='Clearing Charges Account',
        domain="[('account_type', '=', 'expense'), ('company_id', '=', id)]",
        help='Account for clearing agent charges'
    )
    
    exchange_gain_account_id = fields.Many2one(
        'account.account',
        string='Exchange Gain Account',
        domain="[('account_type', '=', 'income_other'), ('company_id', '=', id)]",
        help='Account for foreign exchange gains'
    )
    
    exchange_loss_account_id = fields.Many2one(
        'account.account',
        string='Exchange Loss Account',
        domain="[('account_type', '=', 'expense'), ('company_id', '=', id)]",
        help='Account for foreign exchange losses'
    )
