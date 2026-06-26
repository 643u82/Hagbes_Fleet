# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class FleetDiscrepancy(models.Model):
    _name = 'hagbes.fleet.discrepancy'
    _description = 'Fleet Discrepancy'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    # Core fields
    request_id = fields.Many2one(
        'fleet.requisition',
        string='Requisition',
        help='Linked requisition record'
    )
    allocation_id = fields.Many2one(
        'hagbes.fleet.allocation',
        string='Allocation',
        help='Linked allocation record'
    )
    type = fields.Selection([
        ('fuel', 'Fuel'),
        ('distance', 'Distance'),
        ('time', 'Time')
    ], string='Discrepancy Type', required=True, tracking=True)
    
    expected_value = fields.Float(
        string='Expected Value',
        digits=(10, 2),
        required=True,
        help='Planned or expected value'
    )
    actual_value = fields.Float(
        string='Actual Value',
        digits=(10, 2),
        required=True,
        help='Actual recorded value'
    )
    variance_percent = fields.Float(
        string='Variance %',
        digits=(10, 2),
        compute='_compute_variance_percent',
        store=True,
        help='Percentage variance between expected and actual values'
    )
    severity = fields.Selection([
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High')
    ], string='Severity', required=True, tracking=True)

    # Display name
    name = fields.Char(
        string='Reference',
        compute='_compute_name',
        store=True
    )

    @api.depends('type', 'expected_value', 'actual_value')
    def _compute_name(self):
        """Generate a descriptive name for the discrepancy"""
        for record in self:
            if record.type:
                record.name = f"{record.type.title()} Discrepancy: {record.expected_value} → {record.actual_value}"
            else:
                record.name = "New Discrepancy"

    @api.depends('expected_value', 'actual_value')
    def _compute_variance_percent(self):
        """Compute variance percentage between expected and actual values"""
        for record in self:
            if record.expected_value == 0:
                # Avoid division by zero - set to 0.0 when expected_value is 0
                record.variance_percent = 0.0
            else:
                # Calculate percentage variance: ((actual - expected) / expected) × 100
                record.variance_percent = ((record.actual_value - record.expected_value) / record.expected_value) * 100

    @api.constrains('request_id', 'allocation_id', 'type')
    def _check_linked_record(self):
        """Ensure at least one of request_id or allocation_id is set"""
        for record in self:
            if not record.request_id and not record.allocation_id:
                raise ValidationError(_("At least one of Requisition or Allocation must be specified."))

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to post chatter notes on linked records"""
        records = super().create(vals_list)
        
        for record in records:
            # Post chatter note to linked allocation if present
            if record.allocation_id:
                message = _(
                    "Discrepancy detected: %(type)s variance of %(variance).2f%% "
                    "(Expected: %(expected).2f, Actual: %(actual).2f, Severity: %(severity)s)"
                ) % {
                    'type': record.type.title() if record.type else 'Unknown',
                    'variance': record.variance_percent,
                    'expected': record.expected_value,
                    'actual': record.actual_value,
                    'severity': record.severity.title() if record.severity else 'Unknown'
                }
                record.allocation_id.message_post(
                    body=message,
                    message_type='notification',
                    subtype_xmlid='mail.mt_note'
                )
            
            # Post chatter note to linked requisition if present
            if record.request_id:
                message = _(
                    "Discrepancy detected: %(type)s variance of %(variance).2f%% "
                    "(Expected: %(expected).2f, Actual: %(actual).2f, Severity: %(severity)s)"
                ) % {
                    'type': record.type.title() if record.type else 'Unknown',
                    'variance': record.variance_percent,
                    'expected': record.expected_value,
                    'actual': record.actual_value,
                    'severity': record.severity.title() if record.severity else 'Unknown'
                }
                record.request_id.message_post(
                    body=message,
                    message_type='notification',
                    subtype_xmlid='mail.mt_note'
                )
        
        return records