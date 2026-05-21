from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)

class ForeignLC(models.Model):
    _name = 'foreign.lc'
    _description = 'Letter of Credit'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'lc_date desc, id desc'
    _rec_name = 'name'

    # Basic Information
    name = fields.Char(
        string='LC Number',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New')
    )
    
    lc_date = fields.Date(
        string='LC Date',
        required=True,
        default=fields.Date.context_today,
        tracking=True
    )
    
    expiry_date = fields.Date(
        string='Expiry Date',
        required=True,
        tracking=True
    )
    
    # Relations
    purchase_order_id = fields.Many2one(
        'purchase.order',
        string='Purchase Order',
        required=True,
        domain=[('order_type', '=', 'foreign')],
        tracking=True
    )
    
    supplier_id = fields.Many2one(
        'res.partner',
        string='Supplier',
        required=True,
        tracking=True
    )
    
    issuing_bank_id = fields.Many2one(
        'res.partner',
        string='Issuing Bank',
        required=True,
        tracking=True
    )
    
    advising_bank_id = fields.Many2one(
        'res.partner',
        string='Advising Bank',
        tracking=True
    )
    
    # LC Details
    lc_type = fields.Selection([
        ('sight', 'Sight LC'),
        ('usance', 'Usance LC'),
        ('revolving', 'Revolving LC'),
        ('transferable', 'Transferable LC'),
        ('standby', 'Standby LC'),
    ], string='LC Type', required=True, default='sight', tracking=True)
    
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        required=True,
        tracking=True
    )
    
    lc_amount = fields.Monetary(
        string='LC Amount',
        currency_field='currency_id',
        required=True,
        tracking=True
    )
    
    lc_charges = fields.Monetary(
        string='LC Charges',
        currency_field='currency_id',
        tracking=True
    )
    
    amendment_charges = fields.Monetary(
        string='Amendment Charges',
        currency_field='currency_id',
        tracking=True
    )
    
    company_currency_id = fields.Many2one(
        'res.currency',
        string='Company Currency',
        compute='_compute_company_currency'
    )
    
    # State
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted to Bank'),
        ('issued', 'Issued'),
        ('documents_received', 'Documents Received'),
        ('payment_made', 'Payment Made'),
        ('closed', 'Closed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True, required=True)
    
    # Terms and Conditions
    payment_terms = fields.Text(string='Payment Terms')
    partial_shipment = fields.Boolean(string='Partial Shipment Allowed')
    transhipment = fields.Boolean(string='Transhipment Allowed')
    port_of_loading = fields.Char(string='Port of Loading')
    port_of_discharge = fields.Char(string='Port of Discharge')
    document_requirements = fields.Text(string='Document Requirements')
    special_instructions = fields.Text(string='Special Instructions')
    notes = fields.Text(string='Notes')
    
    # Amendment fields
    amendment_ids = fields.One2many(
        'foreign.lc.amendment',
        'lc_id',
        string='Amendments'
    )
    
    amendment_count = fields.Integer(
        string='Amendment Count',
        compute='_compute_amendment_count'
    )
    
    # Computed Fields
    days_to_expiry = fields.Integer(
        string='Days to Expiry',
        compute='_compute_days_to_expiry',
        store=True 
    )
    
    is_expired = fields.Boolean(
        string='Is Expired',
        compute='_compute_days_to_expiry',
        store=True
    )
    
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True
    )

    @api.depends('company_id')
    def _compute_company_currency(self):
        for record in self:
            record.company_currency_id = record.company_id.currency_id

    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('foreign.lc') or _('New')
        return super().create(vals)

    @api.depends('amendment_ids')
    def _compute_amendment_count(self):
        for record in self:
            record.amendment_count = len(record.amendment_ids)

    @api.depends('expiry_date')
    def _compute_days_to_expiry(self):
        today = fields.Date.context_today(self)
        for record in self:
            if record.expiry_date:
                delta = record.expiry_date - today
                record.days_to_expiry = delta.days
                record.is_expired = delta.days < 0
            else:
                record.days_to_expiry = 0
                record.is_expired = False

    # Action methods for buttons
    def action_submit_to_bank(self):
        for record in self:
            if record.state != 'draft':
                raise UserError(_('Only draft LCs can be submitted to bank.'))
            record.state = 'submitted'
            record.message_post(body=_('LC submitted to bank.'))
        return True

    def action_mark_issued(self):
        for record in self:
            if record.state != 'submitted':
                raise UserError(_('Only submitted LCs can be marked as issued.'))
            record.state = 'issued'
            record.message_post(body=_('LC marked as issued.'))
        return True

    def action_documents_received(self):
        for record in self:
            if record.state != 'issued':
                raise UserError(_('Only issued LCs can have documents received.'))
            record.state = 'documents_received'
            record.message_post(body=_('Documents received for LC.'))
        return True

    def action_payment_made(self):
        for record in self:
            if record.state != 'documents_received':
                raise UserError(_('Only LCs with documents received can have payment made.'))
            record.state = 'payment_made'
            record.message_post(body=_('Payment made for LC.'))
        return True

    def action_close(self):
        for record in self:
            if record.state != 'payment_made':
                raise UserError(_('Only LCs with payment made can be closed.'))
            record.state = 'closed'
            record.message_post(body=_('LC closed.'))
        return True

    def action_cancel(self):
        for record in self:
            if record.state in ['closed', 'cancelled']:
                raise UserError(_('Cannot cancel already closed or cancelled LC.'))
            record.state = 'cancelled'
            record.message_post(body=_('LC cancelled.'))
        return True

    def action_create_amendment(self):
        self.ensure_one()
        return {
            'name': _('Create Amendment'),
            'type': 'ir.actions.act_window',
            'res_model': 'foreign.lc.amendment',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_lc_id': self.id,
            }
        }

    def action_view_amendments(self):
        self.ensure_one()
        return {
            'name': _('Amendments'),
            'type': 'ir.actions.act_window',
            'res_model': 'foreign.lc.amendment',
            'view_mode': 'tree,form',
            'domain': [('lc_id', '=', self.id)],
            'context': {'default_lc_id': self.id}
        }

    def action_view_documents(self):
        return {
            'name': _('Documents'),
            'type': 'ir.actions.act_window',
            'res_model': 'foreign.document',
            'view_mode': 'list,form',
            'domain': [('lc_id', '=', self.id)],
            'context': {'default_lc_id': self.id}
        }

    @api.constrains('expiry_date', 'lc_date')
    def _check_dates(self):
        for record in self:
            if record.expiry_date <= record.lc_date:
                raise ValidationError(_('Expiry date must be after LC date.'))

    @api.constrains('lc_amount')
    def _check_amount(self):
        for record in self:
            if record.lc_amount <= 0:
                raise ValidationError(_('LC amount must be greater than zero.'))


class ForeignLCAmendment(models.Model):
    _name = 'foreign.lc.amendment'
    _description = 'Letter of Credit Amendment'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'amendment_date desc, id desc'

    name = fields.Char(
        string='Amendment Reference', 
        required=True,
        copy=False,
        default=lambda self: _('New Amendment')
    )
    
    lc_id = fields.Many2one(
        'foreign.lc', 
        string='Letter of Credit', 
        required=True, 
        ondelete='cascade'
    )
    
    amendment_date = fields.Date(
        string='Amendment Date', 
        default=fields.Date.context_today,
        required=True,
        tracking=True
    )
    
    amendment_type = fields.Selection([
        ('increase_amount', 'Increase Amount'),
        ('decrease_amount', 'Decrease Amount'),
        ('extend_expiry', 'Extend Expiry Date'),
        ('change_terms', 'Change Terms'),
        ('other', 'Other'),
    ], string='Amendment Type', required=True, tracking=True)
    
    old_amount = fields.Monetary(
        string='Old Amount',
        currency_field='currency_id',
        readonly=True
    )
    
    new_amount = fields.Monetary(
        string='New Amount',
        currency_field='currency_id'
    )
    
    old_expiry_date = fields.Date(
        string='Old Expiry Date',
        readonly=True
    )
    
    new_expiry_date = fields.Date(
        string='New Expiry Date'
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        related='lc_id.currency_id',
        store=True
    )
    
    amendment_charges = fields.Monetary(
        string='Amendment Charges',
        currency_field='currency_id'
    )
    
    reason = fields.Text(string='Reason for Amendment')
    notes = fields.Text(string='Notes')
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True)
    
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        related='lc_id.company_id',
        store=True
    )

    @api.model
    def create(self, vals):
        if vals.get('name', _('New Amendment')) == _('New Amendment'):
            vals['name'] = self.env['ir.sequence'].next_by_code('foreign.lc.amendment') or _('New Amendment')
        return super().create(vals)

    def action_submit(self):
        self.state = 'submitted'
        self.message_post(body=_('Amendment submitted for approval.'))

    def action_confirm(self):
        self.state = 'confirmed'
        # Update the main LC with amendment details
        if self.amendment_type == 'increase_amount' and self.new_amount:
            self.lc_id.lc_amount = self.new_amount
        elif self.amendment_type == 'extend_expiry' and self.new_expiry_date:
            self.lc_id.expiry_date = self.new_expiry_date
        self.message_post(body=_('Amendment confirmed and applied to LC.'))

    def action_cancel(self):
        self.state = 'cancelled'
        self.message_post(body=_('Amendment cancelled.'))

    @api.onchange('lc_id', 'amendment_type')
    def _onchange_lc_amendment_type(self):
        if self.lc_id:
            if self.amendment_type in ['increase_amount', 'decrease_amount']:
                self.old_amount = self.lc_id.lc_amount
            elif self.amendment_type == 'extend_expiry':
                self.old_expiry_date = self.lc_id.expiry_date
