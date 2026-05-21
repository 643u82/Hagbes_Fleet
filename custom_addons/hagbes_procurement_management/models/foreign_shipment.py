from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime, timedelta
import requests
import websocket
import json
import logging

_logger = logging.getLogger(__name__)


class ForeignShipment(models.Model):
    _name = 'foreign.shipment'
    _description = 'Foreign Shipment'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'shipment_date desc, id desc'
    _rec_name = 'name'

    # Basic Information
    name = fields.Char(
        string='Shipment Number',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New')
    )
    
    shipment_date = fields.Date(
        string='Shipment Date',
        required=True,
        default=fields.Date.context_today,
        tracking=True,
        help="Date when goods were shipped from origin"
    )
    
    expected_arrival_date = fields.Date(
        string='Expected Arrival Date',
        tracking=True,
        help="Expected date of arrival at destination port"
    )
    
    actual_arrival_date = fields.Date(
        string='Actual Arrival Date',
        tracking=True,
        help="Actual date when shipment arrived"
    )
    
    # Relations
    purchase_order_id = fields.Many2one(
        'purchase.order',
        string='Purchase Order',
        required=True,
        tracking=True,
        help="Related purchase order for this shipment"
    )

    supplier_id = fields.Many2one(
        'res.partner',
        string='Supplier',
        required=False,
        tracking=True,
        compute='_compute_supplier_from_po',
        store=True,
        readonly=True,  
        help="Supplier/vendor who shipped the goods (taken from Purchase Order)"
    )

    # supplier_id = fields.Many2one(
    #     'res.partner',
    #     string='Supplier',
    #     required=True,
    #     tracking=True,
    #     help="Supplier/vendor who shipped the goods"
    # )
    
    lc_id = fields.Many2one(
        'foreign.lc',
        string='Letter of Credit',
        tracking=True,
        help="Related letter of credit if applicable"
    )
    
    # Ship Information for AIS Tracking
    ship_imo_number = fields.Char(
        string='IMO Number',
        help='International Maritime Organization number - unique ship identifier'
    )
    
    ship_mmsi = fields.Char(
        string='MMSI',
        help='Maritime Mobile Service Identity - required for AIS tracking'
    )
    
    ship_call_sign = fields.Char(
        string='Call Sign',
        help='Ship radio call sign for identification'
    )
    
    ship_flag = fields.Many2one(
        'res.country',
        string='Flag State',
        help='Country where the ship is registered'
    )
    
    ship_type = fields.Selection([
        ('cargo', 'Cargo Ship'),
        ('container', 'Container Ship'),
        ('tanker', 'Tanker'),
        ('bulk_carrier', 'Bulk Carrier'),
        ('ro_ro', 'Ro-Ro Ship'),
        ('other', 'Other'),
    ], string='Ship Type', help='Type of vessel carrying the cargo')
    
    # Vessel Details
    vessel_name = fields.Char(
        string='Vessel Name', 
        tracking=True,
        help="Name of the ship/vessel"
    )
    
    tracking_number = fields.Char(
        string='Tracking Number', 
        tracking=True,
        help="Carrier's tracking reference number"
    )
    
    container_number = fields.Char(
        string='Container Number', 
        tracking=True,
        help="Container reference number(s)"
    )
    
    # Ports
    port_of_loading = fields.Char(
        string='Port of Loading', 
        tracking=True,
        help="Port where goods were loaded"
    )
    
    port_of_discharge = fields.Char(
        string='Port of Discharge', 
        tracking=True,
        help="Destination port for discharge"
    )
    
    # State Management
    state = fields.Selection([
        ('draft', 'Draft'),
        ('booked', 'Booked'),
        ('loaded', 'Loaded'),
        ('departed', 'Departed'),
        ('in_transit', 'In Transit'),
        ('arrived', 'Arrived'),
        ('customs_clearance', 'Customs Clearance'),
        ('delivered', 'Delivered'),
        ('completed', 'Completed'),
    ], string='Status', default='draft', tracking=True, required=True)
    
    # Shipping Terms
    incoterm_id = fields.Many2one(
        'account.incoterms',
        string='Incoterm',
        tracking=True,
        help="International commercial terms"
    )
    
    # Cost Information
    freight_cost = fields.Monetary(
        string='Freight Cost',
        currency_field='currency_id',
        help="Cost of freight/shipping"
    )
    
    insurance_cost = fields.Monetary(
        string='Insurance Cost',
        currency_field='currency_id',
        help="Insurance cost for the shipment"
    )
    
    other_charges = fields.Monetary(
        string='Other Charges',
        currency_field='currency_id',
        help="Other miscellaneous charges"
    )
    
    total_shipping_cost = fields.Monetary(
        string='Total Shipping Cost',
        compute='_compute_total_shipping_cost',
        currency_field='currency_id',
        store=True,
        help="Total of all shipping related costs"
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id,
        required=True
    )
    
    # Additional Information
    notes = fields.Text(string='Notes')
    special_instructions = fields.Text(string='Special Instructions')
    
    # Relations
    document_ids = fields.One2many(
        'foreign.document',
        'shipment_id',
        string='Documents'
    )
    
    landing_ids = fields.One2many(
        'foreign.landing',
        'shipment_id',
        string='Landing Processes'
    )
    
    # Computed Fields
    document_count = fields.Integer(
        string='Document Count',
        compute='_compute_document_count'
    )
    
    days_in_transit = fields.Integer(
        string='Days in Transit',
        compute='_compute_days_in_transit',
        help="Number of days the shipment has been in transit"
    )
    
    is_delayed = fields.Boolean(
        string='Is Delayed',
        compute='_compute_is_delayed',
        help="True if shipment is delayed beyond expected arrival"
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
            vals['name'] = self.env['ir.sequence'].next_by_code('foreign.shipment') or _('New')
        return super().create(vals)

    @api.depends('freight_cost', 'insurance_cost', 'other_charges')
    def _compute_total_shipping_cost(self):
        for record in self:
            record.total_shipping_cost = record.freight_cost + record.insurance_cost + record.other_charges

    @api.depends('document_ids')
    def _compute_document_count(self):
        for record in self:
            record.document_count = len(record.document_ids)

    @api.depends('shipment_date', 'actual_arrival_date', 'state')
    def _compute_days_in_transit(self):
        today = fields.Date.context_today(self)
        for record in self:
            if record.state in ['delivered', 'completed']:
                if record.actual_arrival_date:
                    record.days_in_transit = (record.actual_arrival_date - record.shipment_date).days
                else:
                    record.days_in_transit = 0
            elif record.state in ['in_transit', 'arrived', 'customs_clearance']:
                record.days_in_transit = (today - record.shipment_date).days
            else:
                record.days_in_transit = 0

    @api.depends('expected_arrival_date', 'actual_arrival_date', 'state')
    def _compute_is_delayed(self):
        today = fields.Date.context_today(self)
        for record in self:
            if record.expected_arrival_date:
                if record.actual_arrival_date:
                    record.is_delayed = record.actual_arrival_date > record.expected_arrival_date
                elif record.state not in ['delivered', 'completed']:
                    record.is_delayed = today > record.expected_arrival_date
                else:
                    record.is_delayed = False
            else:
                record.is_delayed = False

    # State Management Methods
    def action_book_shipment(self):
        self.state = 'booked'
        self.message_post(body=_('Shipment booked.'))

    def action_mark_loaded(self):
        self.state = 'loaded'
        self.message_post(body=_('Cargo loaded on vessel.'))

    def action_mark_departed(self):
        self.state = 'departed'
        self.message_post(body=_('Vessel departed from port of loading.'))

    def action_mark_in_transit(self):
        self.state = 'in_transit'
        self.message_post(body=_('Shipment is in transit.'))

    def action_mark_arrived(self):
        self.state = 'arrived'
        self.actual_arrival_date = fields.Date.context_today(self)
        self.message_post(body=_('Shipment arrived at destination port.'))

    def action_customs_clearance(self):
        self.state = 'customs_clearance'
        self.message_post(body=_('Shipment under customs clearance.'))

    def action_mark_delivered(self):
        self.state = 'delivered'
        self.message_post(body=_('Shipment delivered to final destination.'))

    def action_complete(self):
        self.state = 'completed'
        self.message_post(body=_('Shipment process completed.'))

    # MAIN TRACKING METHOD - Opens the live tracking page
    def action_open_live_tracking(self):
        """This action is now handled by the Foreign Transit Process model."""
        transit_process = self.env['foreign.transit.process'].search([('shipment_id', '=', self.id)], limit=1)
        if transit_process:
            return transit_process.action_open_live_tracking()
        else:
            raise UserError(_("No active Transit Process found for this shipment. Tracking is managed during the transit phase."))

    def action_view_documents(self):
        return {
            'name': _('Documents'),
            'type': 'ir.actions.act_window',
            'res_model': 'foreign.document',
            'view_mode': 'tree,form',
            'domain': [('shipment_id', '=', self.id)],
            'context': {'default_shipment_id': self.id}
        }

    @api.constrains('expected_arrival_date', 'shipment_date')
    def _check_dates(self):
        for record in self:
            if record.expected_arrival_date and record.expected_arrival_date <= record.shipment_date:
                raise ValidationError(_('Expected arrival date must be after shipment date.'))
    
    @api.onchange('purchase_order_id')
    def _onchange_purchase_order_id(self):
        if self.purchase_order_id:
            self.supplier_id = self.purchase_order_id.partner_id




# @api.onchange('purchase_order_id')
# def _onchange_purchase_order_id(self):
#     if self.purchase_order_id:
#         self.supplier_id = self.purchase_order_id.partner_id




    @api.depends('purchase_order_id', 'purchase_order_id.partner_id')
    def _compute_supplier_from_po(self):
        for record in self:
            if record.purchase_order_id and record.purchase_order_id.partner_id:
                record.supplier_id = record.purchase_order_id.partner_id
            else:
                record.supplier_id = False
