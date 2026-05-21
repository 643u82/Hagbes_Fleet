from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)

class ForeignDocument(models.Model):
    _name = 'foreign.document'
    _description = 'Foreign Document'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'document_date desc, id desc'
    _rec_name = 'name'

    # Basic Information
    name = fields.Char(
        string='Document Name',
        required=True,
        tracking=True
    )
    
    document_type = fields.Selection([
        ('invoice', 'Commercial Invoice'),
        ('packing_list', 'Packing List'),
        ('bill_of_lading', 'Bill of Lading'),
        ('certificate_origin', 'Certificate of Origin'),
        ('insurance', 'Insurance Certificate'),
        ('inspection', 'Inspection Certificate'),
        ('lc_copy', 'LC Copy'),
        ('bank_certificate', 'Bank Certificate'),
        ('customs', 'Customs Document'),
        ('other', 'Other'),
    ], string='Document Type', required=True, tracking=True)
    
    document_date = fields.Date(
        string='Document Date',
        required=True,
        default=fields.Date.context_today,
        tracking=True
    )
    
    expiry_date = fields.Date(
        string='Expiry Date',
        tracking=True
    )
    
    # Computed fields
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
    
    # Relations
    purchase_order_id = fields.Many2one(
        'purchase.order',
        string='Purchase Order',
        domain=[('order_type', '=', 'foreign')],
        tracking=True
    )
    
    payment_request_id = fields.Many2one(
        'foreign.payment.request',
        string='Payment Request',
        tracking=True
    )
    
    lc_id = fields.Many2one(
        'foreign.lc',
        string='Letter of Credit',
        tracking=True
    )
    
    bank_process_id = fields.Many2one(
        'foreign.bank.process',
        string='Bank Process',
        tracking=True
    )
    
    shipment_id = fields.Many2one(
        'foreign.shipment',
        string='Shipment',
        tracking=True
    )
    
    landing_id = fields.Many2one(
        'foreign.landing',
        string='Landing Process',
        tracking=True
    )
    
    # Document Details
    document_number = fields.Char(string='Document Number', tracking=True)
    issued_by = fields.Char(string='Issued By', tracking=True)
    
    # Verification fields
    verified_by = fields.Many2one(
        'res.users',
        string='Verified By',
        readonly=True
    )
    
    verified_date = fields.Date(
        string='Verified Date',
        readonly=True
    )
    
    # File Attachment
    document_file = fields.Binary(
        string='Document File',
        attachment=True
    )
    
    document_filename = fields.Char(
        string='Document Filename'
    )
    
    attachment_ids = fields.Many2many(
        'ir.attachment',
        string='Attachments'
    )
    
    # Status
    status = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('verified', 'Verified'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('expired', 'Expired'),
    ], string='Status', default='draft', tracking=True, required=True)
    
    # Additional Information
    description = fields.Text(string='Description')
    notes = fields.Text(string='Notes')
    
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True
    )

    @api.depends('expiry_date')
    def _compute_days_to_expiry(self):
        today = fields.Date.context_today(self)
        for record in self:
            if record.expiry_date:
                delta = (record.expiry_date - today).days
                record.days_to_expiry = delta
                record.is_expired = delta < 0
                
                # Automatically mark as expired if past expiry date
                if delta < 0 and record.status != 'expired':
                    record.status = 'expired'
            else:
                record.days_to_expiry = 0
                record.is_expired = False

    def action_verify(self):
        self.write({
            'status': 'verified',
            'verified_by': self.env.user.id,
            'verified_date': fields.Date.context_today(self)
        })
        self.message_post(body=_('Document verified by %s') % self.env.user.name)

    def action_approve(self):
        self.status = 'approved'
        self.message_post(body=_('Document approved by %s') % self.env.user.name)

    def action_reject(self):
        self.status = 'rejected'
        self.message_post(body=_('Document rejected by %s') % self.env.user.name)

    def action_reset_to_draft(self):
        self.status = 'draft'
        self.message_post(body=_('Document reset to draft'))

    def action_submit(self):
        self.status = 'submitted'
        self.message_post(body=_('Document submitted'))

    @api.constrains('document_file')
    def _check_document_file(self):
        for record in self:
            if record.document_type != 'other' and not record.document_file:
                raise ValidationError(_('Please upload the document file.'))

    @api.constrains('expiry_date', 'document_date')
    def _check_dates(self):
        for record in self:
            if record.expiry_date and record.document_date and record.expiry_date < record.document_date:
                raise ValidationError(_('Expiry date cannot be before document date.'))