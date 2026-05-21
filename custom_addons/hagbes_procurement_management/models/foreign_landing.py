from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)

class ForeignLanding(models.Model):
    _name = 'foreign.landing'
    _description = 'Foreign Landing Process'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'arrival_date desc, id desc'
    _rec_name = 'name'

    # Basic Information
    name = fields.Char(
        string='Landing Number',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New')
    )
    
    arrival_date = fields.Date(
        string='Arrival Date',
        required=True,
        default=fields.Date.context_today,
        tracking=True
    )
    
    # Relations
    shipment_id = fields.Many2one(
        'foreign.shipment',
        string='Shipment',
        required=True,
        tracking=True
    )
    
    purchase_order_id = fields.Many2one(
        'purchase.order',
        string='Purchase Order',
        domain=[('order_type', '=', 'foreign')],
        required=True,
        tracking=True
    )
    
    supplier_id = fields.Many2one(
        'res.partner',
        string='Supplier',
        required=True,
        tracking=True
    )
    
    # Customs Information
    customs_agent_id = fields.Many2one(
        'res.partner',
        string='Customs Agent',
        domain=[('is_company', '=', True)],
        tracking=True
    )
    
    clearing_agent_id = fields.Many2one(
        'res.partner',
        string='Clearing Agent',
        domain=[('is_company', '=', True)],
        tracking=True
    )
    
    port_of_entry = fields.Char(
        string='Port of Entry',
        tracking=True
    )
    
    # Document Information
    bl_awb_number = fields.Char(string='BL/AWB Number', tracking=True)
    bl_awb_date = fields.Date(string='BL/AWB Date', tracking=True)
    customs_declaration_number = fields.Char(string='Customs Declaration Number', tracking=True)
    customs_declaration_date = fields.Date(string='Customs Declaration Date', tracking=True)
    
    # Timeline Dates
    documents_submitted_date = fields.Date(string='Documents Submitted Date', tracking=True)
    duty_payment_date = fields.Date(string='Duty Payment Date', tracking=True)
    customs_clearance_date = fields.Date(string='Customs Clearance Date', tracking=True)
    cargo_release_date = fields.Date(string='Cargo Release Date', tracking=True)
    
    # Duties and Taxes
    customs_duty = fields.Monetary(
        string='Customs Duty',
        currency_field='currency_id',
        tracking=True
    )
    
    vat_amount = fields.Monetary(
        string='VAT Amount',
        currency_field='currency_id',
        tracking=True
    )
    
    excise_duty = fields.Monetary(
        string='Excise Duty',
        currency_field='currency_id',
        tracking=True
    )
    
    other_taxes = fields.Monetary(
        string='Other Taxes',
        currency_field='currency_id',
        tracking=True
    )
    
    # Clearing Charges
    clearing_charges = fields.Monetary(
        string='Clearing Charges',
        currency_field='currency_id',
        tracking=True
    )
    
    port_charges = fields.Monetary(
        string='Port Charges',
        currency_field='currency_id',
        tracking=True
    )
    
    storage_charges = fields.Monetary(
        string='Storage Charges',
        currency_field='currency_id',
        tracking=True
    )
    
    examination_charges = fields.Monetary(
        string='Examination Charges',
        currency_field='currency_id',
        tracking=True
    )
    
    other_charges = fields.Monetary(
        string='Other Charges',
        currency_field='currency_id',
        tracking=True
    )
    
    # Totals
    total_duties_taxes = fields.Monetary(
        string='Total Duties & Taxes',
        currency_field='currency_id',
        compute='_compute_total_duties_taxes',
        store=True,
        tracking=True
    )
    
    total_clearing_charges = fields.Monetary(
        string='Total Clearing Charges',
        currency_field='currency_id',
        compute='_compute_total_clearing_charges',
        store=True,
        tracking=True
    )
    
    total_landing_cost = fields.Monetary(
        string='Total Landing Cost',
        currency_field='currency_id',
        compute='_compute_total_landing_cost',
        store=True,
        tracking=True
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id,
        required=True
    )
    
    # State
    state = fields.Selection([
        ('draft', 'Draft'),
        ('documents_submitted', 'Documents Submitted'),
        ('customs_processing', 'Customs Processing'),
        ('duty_assessment', 'Duty Assessment'),
        ('payment_pending', 'Payment Pending'),
        ('payment_made', 'Payment Made'),
        ('examination', 'Physical Examination'),
        ('cleared', 'Customs Cleared'),
        ('released', 'Cargo Released'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True, required=True)
    
    # Additional Information
    special_instructions = fields.Text(string='Special Instructions')
    notes = fields.Text(string='Notes')
    
    # Relations
    document_ids = fields.One2many(
        'foreign.document',
        'landing_id',
        string='Documents'
    )
    
    # Computed Fields
    document_count = fields.Integer(
        string='Document Count',
        compute='_compute_document_count'
    )
    
    days_in_customs = fields.Integer(
        string='Days in Customs',
        compute='_compute_days_in_customs'
    )
    
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True
    )

    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('foreign.landing') or _('New')
        return super().create(vals)

    @api.depends('customs_duty', 'vat_amount', 'excise_duty', 'other_taxes')
    def _compute_total_duties_taxes(self):
        for record in self:
            record.total_duties_taxes = (
                record.customs_duty + 
                record.vat_amount + 
                record.excise_duty + 
                record.other_taxes
            )

    @api.depends('clearing_charges', 'port_charges', 'storage_charges', 'examination_charges', 'other_charges')
    def _compute_total_clearing_charges(self):
        for record in self:
            record.total_clearing_charges = (
                record.clearing_charges +
                record.port_charges +
                record.storage_charges +
                record.examination_charges +
                record.other_charges
            )

    @api.depends('total_duties_taxes', 'total_clearing_charges')
    def _compute_total_landing_cost(self):
        for record in self:
            record.total_landing_cost = (
                record.total_duties_taxes + 
                record.total_clearing_charges
            )

    @api.depends('document_ids')
    def _compute_document_count(self):
        for record in self:
            record.document_count = len(record.document_ids)

    @api.depends('arrival_date', 'customs_clearance_date', 'state')
    def _compute_days_in_customs(self):
        today = fields.Date.context_today(self)
        for record in self:
            if record.state in ['cleared', 'released', 'completed', 'cancelled']:
                if record.customs_clearance_date:
                    record.days_in_customs = (record.customs_clearance_date - record.arrival_date).days
                else:
                    record.days_in_customs = 0
            elif record.state in ['documents_submitted', 'customs_processing', 'duty_assessment', 'payment_pending', 'payment_made', 'examination']:
                record.days_in_customs = (today - record.arrival_date).days
            else:
                record.days_in_customs = 0

    # State Transition Methods
    def action_submit_documents(self):
        self.write({
            'state': 'documents_submitted',
            'documents_submitted_date': fields.Date.context_today(self)
        })
        self.message_post(body=_('Documents submitted for customs processing.'))

    def action_customs_processing(self):
        self.state = 'customs_processing'
        self.message_post(body=_('Customs processing initiated.'))

    def actihagbes_onduty_management_assessment(self):
        self.state = 'duty_assessment'
        self.message_post(body=_('Duty assessment in progress.'))

    def action_payment_pending(self):
        self.state = 'payment_pending'
        self.message_post(body=_('Payment pending for customs clearance.'))

    def action_payment_made(self):
        self.write({
            'state': 'payment_made',
            'duty_payment_date': fields.Date.context_today(self)
        })
        self.message_post(body=_('Payment made for customs clearance.'))

    def action_examination(self):
        self.state = 'examination'
        self.message_post(body=_('Physical examination in progress.'))

    def action_customs_cleared(self):
        self.write({
            'state': 'cleared',
            'customs_clearance_date': fields.Date.context_today(self)
        })
        self.message_post(body=_('Customs clearance completed.'))

    def action_cargo_released(self):
        self.write({
            'state': 'released',
            'cargo_release_date': fields.Date.context_today(self)
        })
        self.message_post(body=_('Cargo released from customs.'))

    def action_complete(self):
        self.state = 'completed'
        self.message_post(body=_('Landing process completed.'))

    def action_cancel(self):
        self.state = 'cancelled'
        self.message_post(body=_('Landing process cancelled.'))

    def action_view_documents(self):
        return {
            'name': _('Documents'),
            'type': 'ir.actions.act_window',
            'res_model': 'foreign.document',
            'view_mode': 'list,form',
            'domain': [('landing_id', '=', self.id)],
            'context': {'default_landing_id': self.id}
        }

    @api.constrains('arrival_date', 'customs_clearance_date', 'cargo_release_date')
    def _check_dates(self):
        for record in self:
            if record.customs_clearance_date and record.arrival_date > record.customs_clearance_date:
                raise ValidationError(_('Clearance date cannot be before arrival date.'))
            if record.cargo_release_date and record.customs_clearance_date and record.customs_clearance_date > record.cargo_release_date:
                raise ValidationError(_('Release date cannot be before clearance date.'))