from odoo import models, fields
class Entry(models.Model):
    _name = 'account.journal.entry'
    _description = 'Entry'
    name = fields.Char(string='Name')
    date = fields.Date(string='Date')
    amount = fields.Float(string='Amount')


class Item(models.Model):
    _name = 'account.journal.item'
    _description = 'Item'
    name = fields.Char(string='Name')
    entry_id = fields.Many2one(string='Entry_id', comodel_name='account.journal.entry')
    amount = fields.Float(string='Amount')


class Asset(models.Model):
    _name = 'account.asset'
    _description = 'Asset'
    name = fields.Char(string='Name')
    value = fields.Float(string='Value')
    depreciation_value = fields.Float(string='Depreciation_value')


class Loan(models.Model):
    _name = 'account.loan'
    _description = 'Loan'
    name = fields.Char(string='Name')
    amount = fields.Float(string='Amount')
    interest_rate = fields.Float(string='Interest_rate')


class Reconcile(models.Model):
    _name = 'account.reconcile'
    _description = 'Reconcile'
    name = fields.Char(string='Name')
    date = fields.Date(string='Date')


class Date(models.Model):
    _name = 'account.lock.date'
    _description = 'Date'
    name = fields.Char(string='Name')
    lock_date = fields.Date(string='Lock_date')


class Return(models.Model):
    _name = 'account.tax.return'
    _description = 'Return'
    name = fields.Char(string='Name')
    period = fields.Char(string='Period')
    amount = fields.Float(string='Amount')