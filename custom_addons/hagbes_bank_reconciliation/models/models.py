from odoo import models, fields, api
from odoo.exceptions import UserError
from datetime import datetime, timedelta

class AgressoLedger(models.Model):
    _name = "bank_reco.ledger"
    _description = "Agresso Ledger"
    _order = "voucher_date desc, id desc"

    agrtid = fields.Char(string="AGRTID", required=True, copy=False)
    account_id = fields.Char(string="Account")  # free text
    voucher_no = fields.Char(string="Voucher No")
    reference = fields.Char(string="Reference")
    voucher_date = fields.Date(string="Voucher Date")
    voucher_type = fields.Char(string="Voucher Type")
    period = fields.Char(string="Period")  # e.g. "2025-02"
    currency_id = fields.Many2one(
        'res.currency',
        string="Currency",
        default=lambda self: self.env.company.currency_id.id
    )
    amount = fields.Monetary(string="Amount", currency_field="currency_id")
    debit = fields.Monetary(
        string="Debit",
        currency_field="currency_id",
        compute="_compute_debit_credit",
        store=True
    )
    credit = fields.Monetary(
        string="Credit",
        currency_field="currency_id",
        compute="_compute_debit_credit",
        store=True
    )
    company_id = fields.Many2one(
        'res.company',
        default=lambda self: self.env.company,
        string="Company"
    )

    _sql_constraints = [
        ("unique_agrid", "unique(agrtid)", "This AGRTID already exists."),
    ]

    @api.depends('amount')
    def _compute_debit_credit(self):
        for rec in self:
            if rec.amount >= 0:
                rec.debit = rec.amount
                rec.credit = 0.0
            else:
                rec.debit = 0.0
                rec.credit = abs(rec.amount)


class BankReco(models.Model):
    _name = "bank_reco.header"
    _description = "Bank Reconciliation"
    _order = "statement_date desc,id desc"

    name = fields.Char(string="Name", readonly=True, copy=False)  # auto-set
    statement_date = fields.Date(string="Statement Date", required=True, default=fields.Date.today())
    period = fields.Char(string="Period", required=True)  # e.g. "202502"
    account_id = fields.Char(string="Account", required=True)
    opening_balance = fields.Monetary(string="Opening Balance", currency_field="currency_id")
    beginning_balance = fields.Float(
        string="Ledger Beginning Balance",
        compute="_compute_beginning_balance",
        store=True
    )
    bank_statement_balance = fields.Float(string="Bank Statement Balance")
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        required=True,
        default=lambda self: self.env.company.currency_id
    )

    # Totals (keep exact names)
    matched_total = fields.Float(string="Cleared Transactions", compute="_compute_balances", store=True)
    deposit_in_transit_total = fields.Float(string="Deposit in Transit", compute="_compute_balances", store=True)
    outstanding_cheque_total = fields.Float(string="Outstanding Cheque", compute="_compute_balances", store=True)
    ledger_balance = fields.Float(string="Ledger Ending Balance", compute="_compute_balances", store=True)
    ending_balance = fields.Float(string="Statement Ending Balance", compute="_compute_balances", store=True)
    difference = fields.Float(string="Unreconciled Difference", compute="_compute_balances", store=True)
    reconciliation_rate = fields.Float(string="Reconciliation %", compute="_compute_balances", store=True)
    bank_debit = fields.Float(string="Bank Debit", compute="_compute_balances", store=True)
    bank_credit = fields.Float(string="Bank Credit", compute="_compute_balances", store=True)
    detail_ids = fields.One2many("bank_reco.detail", "header_id", string="Details")

    state = fields.Selection([('draft', 'Draft'), ('done', 'Reconciled')], default='draft')

    _sql_constraints = [
        ('uniq_period_account', 'unique(period, account_id)',
         'A reconciliation already exists for this period/account!')
    ]

    @api.model
    def create(self, vals):
        if vals.get("account_id") and vals.get("period"):
            vals["name"] = f"{vals['account_id']}-{vals['period']}"
        if not vals.get("beginning_balance") and vals.get("account_id") and vals.get("period"):
            prev = self.search([
                ('account_id', '=', vals['account_id']),
                ('period', '<', vals['period'])
            ], order="period desc", limit=1)
            if prev:
                vals['beginning_balance'] = prev.ending_balance
        return super().create(vals)

    def action_fetch_ledger_transactions(self):
        self.ensure_one()
        if self.state != "draft":
            raise UserError("You cannot fetch transactions once reconciliation is done.")

        Ledger = self.env['bank_reco.ledger']
        existing_agrtids = self.detail_ids.mapped('agrtid')

        # Get ledger entries for the current period and account
        ledger_entries = Ledger.search([
            ('account_id', '=', self.account_id),
            ('period', '=', self.period)
        ])

        for l in ledger_entries:
            # Check if a detail with same agrtid already exists
            existing = self.detail_ids.filtered(lambda d: d.agrtid == l.agrtid)
            if existing:
                # Replace existing line if agrtid matches
                existing.write({
                    'ledger_id': l.id,
                    'bank_date': fields.Date.today(),
                    'original_period': self.period,
                })
            else:
                # Add new detail line if agrtid does not exist
                self.detail_ids = [(0, 0, {
                    'ledger_id': l.id,
                    'bank_date': fields.Date.today(),
                    'original_period': self.period,
                    'agrtid': l.agrtid
                })]

    @api.depends('detail_ids.amount', 'detail_ids.status', 'beginning_balance', 'bank_statement_balance')
    def _compute_balances(self):
        Ledger = self.env['bank_reco.ledger']
        for rec in self:
            matched = sum(line.amount for line in rec.detail_ids if line.status == 'matched')
            deposits = sum(line.amount for line in rec.detail_ids if line.status == 'deposit_in_transit')
            cheques = sum(line.amount for line in rec.detail_ids if line.status == 'outstanding_cheque')
            bank_credit = sum(line.amount for line in rec.detail_ids if line.status == 'matched' and line.amount > 0)
            bank_debit = sum(abs(line.amount) for line in rec.detail_ids if line.status == 'matched' and line.amount < 0)
            rec.bank_debit = bank_debit
            rec.bank_credit = bank_credit
            rec.matched_total = matched
            rec.deposit_in_transit_total = deposits
            rec.outstanding_cheque_total = cheques
            ledger_entries = Ledger.search([
                ('account_id', '=', rec.account_id),
                ('period', '=', rec.period),
            ])
            ledger_sum = sum(ledger_entries.mapped('amount'))
            rec.ledger_balance = rec.beginning_balance + ledger_sum
            rec.ending_balance = rec.ledger_balance - rec.outstanding_cheque_total + rec.deposit_in_transit_total
            rec.difference = rec.bank_statement_balance - rec.ending_balance
            total_items = len(rec.detail_ids)
            rec.reconciliation_rate = (len([l for l in rec.detail_ids if l.status == 'matched']) / total_items * 100) if total_items else 0.0

    def action_mark_done(self):
        for rec in self:
            rec.state = "done"

    @api.depends('account_id', 'period','opening_balance')
    def _compute_beginning_balance(self):
        Ledger = self.env['bank_reco.ledger']
        for rec in self:
            rec.beginning_balance = 0.0
            if not rec.period or not rec.account_id:
                continue
            try:
                period_start = datetime.strptime(rec.period + "01", "%Y%m%d").date()
            except ValueError:
                continue
            previous_entries = Ledger.search([
                ('account_id', '=', rec.account_id),
                ('voucher_date', '<', period_start)
            ])
            opening_entries = Ledger.search([
                ('account_id', '=', rec.account_id),
                ('period', '=', '202500')
            ])
            rec.beginning_balance = sum(x.amount or 0.0 for x in (previous_entries | opening_entries)) + (rec.opening_balance or 0.0)

    @staticmethod
    def _next_period(period_str):
        """Return next period in YYYYMM format without using relativedelta"""
        year = int(period_str[:4])
        month = int(period_str[4:6])
        month += 1
        if month > 12:
            month = 1
            year += 1
        return f"{year:04d}{month:02d}"

    def action_forward(self):
        """Forward eligible lines to the next period and auto-load them into the target header ."""
        LedgerDetail = self.env['bank_reco.detail']
        for header in self:
            for line in header.detail_ids:
                # Skip lines that are matched or already forwarded or without a forward period
                if line.matched or line.forwarded or not line.forward_to_period:
                    continue

                # Find or create target header
                target_header = self.env['bank_reco.header'].search([
                    ('period', '=', line.forward_to_period),
                    ('account_id', '=', header.account_id)
                ], limit=1)
                if not target_header:
                    target_header = self.env['bank_reco.header'].create({
                        'name': f"{header.account_id}-{line.forward_to_period}",
                        'statement_date': fields.Date.today(),
                        'period': line.forward_to_period,
                        'account_id': header.account_id,
                        'beginning_balance': header.ending_balance,
                    })

                # Check if the line is already loaded in target (avoid duplicates)
                existing = target_header.detail_ids.filtered(lambda d: d.ledger_id == line.ledger_id)
                if not existing:
                    # Create new line in target header
                    LedgerDetail.with_context(no_forward=True).create({
                        'header_id': target_header.id,
                        'ledger_id': line.ledger_id.id,
                        'bank_date': fields.Date.today(),
                        'matched': False,
                        'original_period': header.period,
                        'forwarded': False,  # target line is new, can be forwarded further
                        'remarks': line.remarks or f"Forwarded from {header.period}"
                    })
                target_header.action_fetch_ledger_transactions()
                # Mark original line as forwarded so it won't forward again
                line.forwarded = True

    def action_reset_draft(self):
        """Reset header and all forwarded lines to draft"""
        for rec in self:
            # Reset current header
            rec.state = 'draft'
            # Reset forwarded headers for next periods
            forwarded_headers = self.env['bank_reco.header'].search([
                ('account_id', '=', rec.account_id),
                ('period', '>', rec.period)
            ])
            for f_header in forwarded_headers:
                f_header.state = 'draft'
                for line in f_header.detail_ids:
                    if line.original_period == rec.period:
                        line.unlink()  # remove forwarded copies

class BankRecoDetail(models.Model):
    _name = "bank_reco.detail"
    _description = "Bank Reconciliation Detail"
    _order = "voucher_date desc, voucher_no asc, credit desc, debit desc"
    header_id = fields.Many2one("bank_reco.header", string="Header", ondelete="cascade")
    ledger_id = fields.Many2one("bank_reco.ledger", string="Ledger Entry")
    agrtid = fields.Char(string="AGRTID", related="ledger_id.agrtid", store=True, readonly=True)
    account_id = fields.Char(string="Account", related="ledger_id.account_id", store=True)
    voucher_no = fields.Char(string="Voucher No", related="ledger_id.voucher_no", store=True)
    reference = fields.Char(string="Reference", related="ledger_id.reference", store=True)
    voucher_type = fields.Char(string="Voucher Type", related="ledger_id.voucher_type", store=True)
    voucher_date = fields.Date(string="Voucher Date", related="ledger_id.voucher_date", store=True)
    period = fields.Char(string="Period", related="ledger_id.period", store=True)
    forwarded = fields.Boolean(string="Forwarded", default=False)
    bank_date = fields.Date(string="Bank Date", default=lambda self: fields.Date.today())
    currency_id = fields.Many2one('res.currency', string="Currency", related="ledger_id.currency_id", readonly=True)
    debit = fields.Monetary(string="Debit", related="ledger_id.debit", currency_field="currency_id", readonly=True,
                            store=True)
    credit = fields.Monetary(string="Credit", related="ledger_id.credit", currency_field="currency_id", readonly=True,
                             store=True)

    amount = fields.Monetary(string="Amount", related="ledger_id.amount", currency_field="currency_id", readonly=True,store=True)

    matched = fields.Boolean(string="Matched", default=False)
    status = fields.Selection([
        ('matched', 'Matched'),
        ('deposit_in_transit', 'Deposit in Transit'),
        ('outstanding_cheque', 'Outstanding Cheque'),
    ], string="Status", compute="_compute_status", store=True)
    difference = fields.Float(string="Difference", compute="_compute_difference", store=True)
    matched_by = fields.Many2one("res.users", string="Matched By", readonly=True)
    matched_date = fields.Datetime(string="Matched Date", readonly=True)
    forward_to_period = fields.Char(string="Forward To Period")
    original_period = fields.Char(string="From Period", readonly=True)
    remarks = fields.Text(string="Remarks")

    @api.depends('matched', 'amount')
    def _compute_status(self):
        for rec in self:
            if rec.matched:
                rec.status = 'matched'
            elif rec.amount < 0:
                rec.status = 'outstanding_cheque'
            elif rec.amount > 0:
                rec.status = 'deposit_in_transit'
            else:
                rec.status = False

    @api.depends('matched', 'amount', 'status')
    def _compute_difference(self):
        for rec in self:
            rec.difference = 0.0 if rec.matched or rec.status == 'outstanding_cheque' else rec.amount

    def create(self, vals):
        record = super().create(vals)
        # Only forward if not in no_forward context and not already forwarded
        if not self.env.context.get('no_forward') and record.forward_to_period and not record.forwarded:
            record.header_id.action_forward()
        return record

    def write(self, vals):
        # Prevent recursion
        if self.env.context.get('no_forward'):
            return super().write(vals)

        res = super().write(vals)

        for rec in self:
            # Forward only if forward_to_period is set, not matched, and not already forwarded
            if rec.forward_to_period and not rec.matched and not rec.forwarded:
                rec.header_id.action_forward()

        return res



