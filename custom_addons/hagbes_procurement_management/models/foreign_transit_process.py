print(">>> foreign_transit_process_improved.py loaded <<<")

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime, timedelta
import requests
import websocket
import json
import logging
import threading


_logger = logging.getLogger(__name__)

class ForeignTransitProcess(models.Model):
    _name = 'foreign.transit.process'
    _description = 'Foreign Transit Process'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc, id desc'
    _rec_name = 'name'

    name = fields.Char(
        string='Transit Number',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New')
    )
    
    purchase_order_id = fields.Many2one(
        'purchase.order',
        string='Purchase Order',
        required=True,
        domain="[('order_type', '=', 'foreign')]",
        tracking=True
    )
    
    bank_process_id = fields.Many2one(
        'foreign.bank.process',
        string='Bank Process Reference',
        compute='_compute_bank_process_id',
        store=True,
        readonly=True,
        tracking=True,
    )
    
    shipment_id = fields.Many2one(
        'foreign.shipment',
        string='Shipment',
        tracking=True
    )
    
    supplier_id = fields.Many2one(
        'res.partner',
        string='Supplier',
        related='purchase_order_id.partner_id',
        store=True,
        readonly=True
    )
    
    branch_id = fields.Many2one(
        'account.analytic.account',
        string='Branch',
        store=True,
        tracking=True,
        readonly=True
    )
   
    state = fields.Selection([
        ('draft', 'Draft'),
        ('planned', 'Planned'),
        ('in_origin', 'At Origin'),
        ('departed_origin', 'Departed Origin'),
        ('in_transit', 'In Transit'),
        ('arrived_destination', 'Arrived at Destination'),
        ('customs_destination', 'Customs Clearance'),
        ('customs_cleared', 'Customs Cleared'),
        ('final_delivery', 'Final Delivery'),
        ('completed', 'Completed'),
        ('delayed', 'Delayed'),  # Added missing delayed state
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True, required=True)
    
    port_of_entry = fields.Selection([
        ('djibouti', 'Djibouti Port'),
        ('berbera', 'Berbera Port'),
        ('addis_ababa_airport', 'Addis Ababa Bole Airport'),
        ('dire_dawa_dry_port', 'Dire Dawa Dry Port'),
        ('modjo_dry_port', 'Modjo Dry Port'),
    ], string='Port of Entry', required=True, tracking=True)
    
    customs_office = fields.Selection([
        ('addis_ababa_main', 'Addis Ababa Main Customs'),
        ('djibouti_customs', 'Djibouti Customs Office'),
        ('dire_dawa_customs', 'Dire Dawa Customs Office'),
        ('modjo_customs', 'Modjo Customs Office'),
        ('bole_airport_customs', 'Bole Airport Customs'),
    ], string='Customs Office', required=True, tracking=True)
    
    transit_manager_id = fields.Many2one(
        'res.users',
        string='Transit Manager',
        default=lambda self: self.env.user,
        tracking=True
    )
    
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True
    )

    starting_in_ethiopian_date = fields.Date(
        string='Starting Date (Ethiopian)',
        help='Starting date in Ethiopian calendar'
    )
    
    starting_date_gregorian = fields.Date(
        string='Starting Date (Gregorian)',
        compute='_compute_ethiopian_dates',
        store=True
    )
    
    days_to_add = fields.Integer(
        string='Days to Add',
        default=30,
        help='Number of days to add to starting date'
    )
    
    estimated_last_date = fields.Date(
        string='Estimated Last Date',
        compute='_compute_ethiopian_dates',
        store=True
    )
    
    remaining_days = fields.Integer(
        string='Remaining Days',
        compute='_compute_remaining_days',
        store=True
    )

    # Bonded Warehouse
    bonded_warehouse_id = fields.Many2one(
        'foreign.transit.bonded.warehouse',
        string='Bonded Warehouse',
        tracking=True
    )
    
    bonded_entry_date = fields.Date(
        string='Bonded Entry Date',
        tracking=True
    )
    
    bonded_exit_date = fields.Date(
        string='Bonded Exit Date',
        tracking=True
    )
    
    bonded_days_remaining = fields.Integer(
        string='Days Remaining in Bonded',
        compute='_compute_bonded_days_remaining',
        store=True
    )

    # Shipping & Transport
    bill_of_lading_number = fields.Char(
        string='Bill of Lading/AWB Number',
        tracking=True
    )
    
    port_of_loading = fields.Char(
        string='Port of Loading',
        tracking=True
    )
    
    port_eta = fields.Date(
        string='Port ETA',
        tracking=True
    )
    
    port_ata = fields.Date(
        string='Port ATA',
        tracking=True
    )
    
    local_mode_of_transport = fields.Selection([
        ('sea', 'Sea Transport'),
        ('air', 'Air Transport'),
        ('road', 'Road Transport'),
        ('rail', 'Rail Transport'),
        ('multi_modal', 'Multi Modal'),
    ], string='Mode of Transport', tracking=True)
    
    shipped_by = fields.Selection([
        ('containerized', 'Containerized'),
        ('bulk', 'Bulk'),
        ('break_bulk', 'Break Bulk'),
        ('ro_ro', 'Ro-Ro'),
    ], string='Shipped By', tracking=True)
    
    gross_weight = fields.Float(
        string='Gross Weight (KG)',
        digits='Stock Weight',
        tracking=True
    )

    # --- Fields from Shipment Record ---
    vessel_name = fields.Char(
        string='Vessel Name',
        tracking=True,
        help="Name of the ship/vessel from the Shipment record"
    )
    imo_number = fields.Char(
        string='IMO Number',
        help='International Maritime Organization number from the Shipment record'
    )
    mmsi_number = fields.Char(
        string='MMSI',
        help='Maritime Mobile Service Identity from the Shipment record'
    )
    flag_state = fields.Many2one(
        'res.country',
        string='Flag State',
        help='Country where the ship is registered, from the Shipment record'
    )
    eta_date = fields.Date(
        string='ETA Date',
        related='port_eta',
        store=True,
        help="Expected Time of Arrival from the Shipment record"
    )

    # --- Fields moved from Shipment for Live Tracking ---
    current_latitude = fields.Float(
        string='Current Latitude',
        digits=(10, 6),
        help="Current latitude position from AIS data",
        tracking=True
    )
    current_longitude = fields.Float(
        string='Current Longitude',
        digits=(10, 6),
        help="Current longitude position from AIS data",
        tracking=True
    )
    current_speed = fields.Float(
        string='Current Speed (knots)',
        digits=(5, 2),
        help="Current speed of vessel in knots"
    )
    current_course = fields.Float(
        string='Current Course (degrees)',
        digits=(5, 1),
        help="Current heading/course of vessel in degrees"
    )
    last_position_update = fields.Datetime(
        string='Last Position Update',
        readonly=True,
        help="When position was last updated from AIS"
    )
    ais_stream_enabled = fields.Boolean(
        string='AIS Stream Tracking',
        default=False,
        copy=False,
        help='Enable real-time tracking via AIS Stream API for this transit'
    )
    tracking_status = fields.Selection([
        ('not_started', 'Not Started'),
        ('tracking', 'Tracking'),
        ('lost_signal', 'Signal Lost'),
        ('arrived', 'Arrived'),
        ('error', 'Error'),
    ], string='Tracking Status', default='not_started', tracking=True)

    # Re-using fields from shipment for tracking configuration
    ship_imo_number = fields.Char(
        string='IMO Number',
        related='imo_number',
        store=True,
        help='International Maritime Organization number - unique ship identifier'
    )
    ship_mmsi = fields.Char(
        string='MMSI',
        related='mmsi_number',
        store=True,
        help='Maritime Mobile Service Identity - required for AIS tracking'
    )

    # Container Information
    container_ids = fields.One2many(
        'foreign.transit.container',
        'transit_id',
        string='Containers'
    )
    
    container_count = fields.Integer(
        string='Container Count',
        compute='_compute_container_count'
    )

    # Documents
    document_ids = fields.One2many(
        'foreign.transit.document',
        'transit_id',
        string='Transit Documents'
    )

    customs_declaration_ids = fields.One2many(
        'foreign.transit.customs.declaration',
        'transit_id',
        string='Customs Declarations'
    )

    # Assessment & Clearance
    customs_assessor = fields.Char(
        string='Customs Assessor',
        tracking=True
    )
    
    expected_clearance_date = fields.Date(
        string='Expected Clearance Date',
        tracking=True
    )
    
    actual_clearance_date = fields.Date(
        string='Actual Clearance Date',
        tracking=True
    )

    # Quantities
    total_quantity = fields.Float(
        string='Total Quantity',
        digits='Product Unit of Measure',
        tracking=True
    )
    
    quantity_cleared = fields.Float(
        string='Quantity Cleared',
        digits='Product Unit of Measure',
        tracking=True
    )
    
    quantity_remaining = fields.Float(
        string='Quantity Remaining',
        compute='_compute_quantity_remaining',
        store=True,
        digits='Product Unit of Measure'
    )

    # Cost Tracking
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
    
    excise_tax = fields.Monetary(
        string='Excise Tax',
        currency_field='currency_id',
        tracking=True
    )
    
    sur_tax = fields.Monetary(
        string='Sur Tax',
        currency_field='currency_id',
        tracking=True
    )
    
    withholding_tax = fields.Monetary(
        string='Withholding Tax',
        currency_field='currency_id',
        tracking=True
    )
    
    total_tax_amount = fields.Monetary(
        string='Total Tax Amount',
        compute='_compute_total_tax_amount',
        store=True,
        currency_field='currency_id'
    )
    
    storage_charges = fields.Monetary(
        string='Storage Charges',
        currency_field='currency_id',
        tracking=True
    )
    
    handling_charges = fields.Monetary(
        string='Handling Charges',
        currency_field='currency_id',
        tracking=True
    )
    
    total_transit_cost = fields.Monetary(
        string='Total Transit Cost',
        compute='_compute_total_transit_cost',
        store=True,
        currency_field='currency_id'
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        required=True,
        default=lambda self: self.env.company.currency_id
    )

    # Performance & Risk
    delay_days = fields.Integer(
        string='Delay Days',
        compute='_compute_delay_days',
        store=True
    )
    
    risk_level = fields.Selection([
        ('low', 'Low Risk'),
        ('medium', 'Medium Risk'),
        ('high', 'High Risk'),
        ('critical', 'Critical Risk'),
    ], string='Risk Level', compute='_compute_risk_level', store=True)

    # Process Tracking
    handover_to_transiter = fields.Char(
        string='Handover To Transiter',
        tracking=True
    )
    
    acceptance_date = fields.Date(
        string='Acceptance Date',
        tracking=True
    )
    
    inspection_date = fields.Date(
        string='Inspection Date',
        tracking=True
    )
    
    release_date = fields.Date(
        string='Release Date',
        tracking=True
    )

    # Duty Status
    duty_status = fields.Selection([
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('exempted', 'Exempted'),
        ('deferred', 'Deferred'),
    ], string='Duty Status', tracking=True, default='pending')

    # Additional Information
    notes = fields.Text(string='Notes')
    
    # GRN & Interchanging Tracking
    grn_received = fields.Boolean(string='GRN Received', tracking=True)
    container_interchanged = fields.Boolean(string='Container Interchanged', tracking=True)
    
    def action_notify_missing_grn(self):
        self.ensure_one()
        # Mock logic to notify import department
        self.message_post(
            body=_('Notification: Goods Receipt Note (GRN) has not been received yet. Please follow up.'),
            subject='Missing GRN Notification',
            subtype_xmlid='mail.mt_note'
        )

    @api.depends('customs_duty', 'vat_amount', 'excise_tax', 'sur_tax', 'withholding_tax')
    def _compute_total_tax_amount(self):
        for record in self:
            record.total_tax_amount = (
                record.customs_duty + record.vat_amount + record.excise_tax + 
                record.sur_tax + record.withholding_tax
            )

    @api.depends('total_tax_amount', 'storage_charges', 'handling_charges')
    def _compute_total_transit_cost(self):
        for record in self:
            record.total_transit_cost = (
                record.total_tax_amount + record.storage_charges + record.handling_charges
            )

    @api.depends('expected_clearance_date', 'actual_clearance_date')
    def _compute_delay_days(self):
        for record in self:
            if record.expected_clearance_date and record.actual_clearance_date:
                delta = record.actual_clearance_date - record.expected_clearance_date
                record.delay_days = delta.days
            else:
                record.delay_days = 0

    @api.depends('bonded_entry_date', 'bonded_exit_date')
    def _compute_bonded_days_remaining(self):
        for record in self:
            if record.bonded_entry_date and not record.bonded_exit_date:
                today = fields.Date.context_today(record)
                delta = today - record.bonded_entry_date
                # Assuming 90 days bonded warehouse limit
                record.bonded_days_remaining = max(0, 90 - delta.days)
            else:
                record.bonded_days_remaining = 0

    @api.depends('total_quantity', 'quantity_cleared')
    def _compute_quantity_remaining(self):
        for record in self:
            record.quantity_remaining = record.total_quantity - record.quantity_cleared

    @api.depends('remaining_days', 'delay_days')
    def _compute_risk_level(self):
        for record in self:
            if record.delay_days > 10 or record.remaining_days < 0:
                record.risk_level = 'critical'
            elif record.delay_days > 5 or record.remaining_days < 5:
                record.risk_level = 'high'
            elif record.delay_days > 0 or record.remaining_days < 10:
                record.risk_level = 'medium'
            else:
                record.risk_level = 'low'

    @api.depends('estimated_last_date')
    def _compute_remaining_days(self):
        for record in self:
            if record.estimated_last_date:
                today = fields.Date.context_today(record)
                delta = record.estimated_last_date - today
                record.remaining_days = delta.days
            else:
                record.remaining_days = 0

    @api.depends('starting_in_ethiopian_date', 'days_to_add')
    def _compute_ethiopian_dates(self):
        for record in self:
            if record.starting_in_ethiopian_date:
                
                record.starting_date_gregorian = fields.Date.context_today(record)
                if record.days_to_add:
                    record.estimated_last_date = record.starting_date_gregorian + timedelta(days=record.days_to_add)

    @api.depends('container_ids')
    def _compute_container_count(self):
        for record in self:
            record.container_count = len(record.container_ids)

    @api.constrains('bonded_entry_date', 'bonded_exit_date')
    def _check_bonded_dates(self):
        for record in self:
            if record.bonded_entry_date and record.bonded_exit_date:
                if record.bonded_exit_date < record.bonded_entry_date:
                    raise ValidationError(_('Bonded exit date cannot be before entry date.'))


    @api.depends('purchase_order_id')
    def _compute_bank_process_id(self):
        for record in self:
            if record.purchase_order_id:
                bank_process = self.env['foreign.bank.process'].search([
                    ('purchase_order_id', '=', record.purchase_order_id.id)
                ], limit=1)
                record.bank_process_id = bank_process.id if bank_process else False
            else:
                record.bank_process_id = False

    @api.constrains('expected_clearance_date', 'actual_clearance_date')
    def _check_clearance_dates(self):
        for record in self:
            if record.expected_clearance_date and record.actual_clearance_date:
                if record.actual_clearance_date < record.expected_clearance_date:
                  
                    pass



    def action_plan_transit(self):
        self.ensure_one()
        if not self.purchase_order_id or not self.port_of_entry or not self.customs_office:
            raise UserError(_("Please ensure Purchase Order, Port of Entry, and Customs Office are set before planning the transit."))
        self.state = 'planned'
        self.message_post(body=_('Transit process planned.'))

    def action_at_origin(self):
        self.ensure_one()
        if not self.starting_date_gregorian:
            raise UserError(_("Please set the 'Starting Date (Ethiopian)' to establish the timeline before proceeding."))
        self.state = 'in_origin'
        self.message_post(body=_('Goods are at origin location.'))

    def action_depart_origin(self):
        self.ensure_one()
        if not self.bill_of_lading_number:
            raise UserError(_("Please provide the Bill of Lading/AWB Number before marking as departed."))
        self.state = 'departed_origin'
        self.message_post(body=_('Goods departed from origin.'))

    def action_in_transit(self):
        self.ensure_one()
       
        self.state = 'in_transit'
        self.message_post(body=_('Goods are in international transit.'))

    def action_arrive_destination(self):
        self.ensure_one()
        if not self.port_ata:
            raise UserError(_("Please set the 'Port ATA' (Actual Time of Arrival) before marking as arrived."))
        self.state = 'arrived_destination'
        self.message_post(body=_('Goods arrived at destination.'))

    def action_customs_clearance(self):
        self.ensure_one()
        if not self.customs_declaration_ids:
            raise UserError(_("Please add at least one Customs Declaration record before starting customs clearance."))
        self.state = 'customs_destination'
        self.message_post(body=_('Customs clearance process started.'))

    def action_customs_cleared(self):
        self.ensure_one()
        if not self.actual_clearance_date:
            raise UserError(_("Please set the 'Actual Clearance Date' before marking as cleared."))
        self.write({
            'state': 'customs_cleared',
        })
        self.message_post(body=_('Customs clearance completed.'))

    def action_final_delivery(self):
        self.ensure_one()
       
        self.state = 'final_delivery'
        self.message_post(body=_('Final delivery in progress.'))

    #-------------------------------------------------------

    def action_complete(self):
        self.ensure_one()
        if not self.purchase_order_id:
            raise UserError(_("A Purchase Order must be linked to complete the transit process."))

        self.state = 'completed'

        # --- Update Purchase Order state to 'transit_done' ---
        self.purchase_order_id.write({'state': 'transit_done'})
        self.purchase_order_id.message_post(body=_("State updated to 'Transit Done' by Transit Process %s.") % self.name)

        self.message_post(body=_('Transit process completed successfully.'))
       
        if self.purchase_order_id and self.purchase_order_id.landing_ids:
            # A PO can have multiple landing cost records, so we iterate through them.
            for landing in self.purchase_order_id.landing_ids:
                landing.total_landing_cost += self.total_transit_cost

        # --- Automatically create FRC
        costing_env = self.env['foreign.costing']
        existing_costing = costing_env.search([('purchase_order_id', '=', self.purchase_order_id.id)], limit=1)
        if not existing_costing:
            new_costing = costing_env.create({
                'purchase_order_id': self.purchase_order_id.id,
                # The onchange on purchase_order_id will populate other details
            })
            self.message_post(
                body=_("A new Foreign Costing record <a href='#' data-oe-model='foreign.costing' data-oe-id='%s'>%s</a> has been created.") % (new_costing.id, new_costing.reference)
            )
        else:
            self.message_post(body=_("A Foreign Costing record for PO %s already exists.") % self.purchase_order_id.name)

    
    #-------------------------------------------------------
    def action_mark_delayed(self):
        self.ensure_one()
        self.state = 'delayed'
        self.message_post(body=_('Transit process marked as delayed.'))

    def action_cancel(self):
        self.ensure_one()
        self.state = 'cancelled'
        self.message_post(body=_('Transit process cancelled.'))

    def action_mark_delayed(self):
        self.ensure_one()
        self.state = 'delayed'
        self.message_post(body=_('Transit process marked as delayed.'))

    def action_cancel(self):
        self.ensure_one()
        self.state = 'cancelled'
        self.message_post(body=_('Transit process cancelled.'))

    def action_view_containers(self):
        return {
            'name': _('Containers'),
            'type': 'ir.actions.act_window',
            'res_model': 'foreign.transit.container',
            'view_mode': 'tree,form',
            'domain': [('transit_id', '=', self.id)],
            'context': {'default_transit_id': self.id}
        }

    def action_view_bank_process(self):
        self.ensure_one()
        if not self.bank_process_id:
            raise UserError(_("No related Bank Process found."))
        return {
            'name': _('Bank Process'),
            'type': 'ir.actions.act_window',
            'res_model': 'foreign.bank.process',
            'res_id': self.bank_process_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_open_live_tracking(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': '/shipment_tracking/%s' % self.id,
            'target': 'new',
        }

    def action_start_ais_tracking(self):
        """Start AIS tracking for the vessel during transit."""
        if not self.ship_mmsi:
            raise UserError(_('MMSI number is required for AIS tracking. It should be populated from the Shipment record.'))
        
        self.ais_stream_enabled = True
        self.tracking_status = 'tracking'
        self.message_post(body=_('AIS tracking started for vessel %s') % self.vessel_name)
        
        # Initial position fetch
        self.action_update_position()

    def action_stop_ais_tracking(self):
        """Stop AIS tracking for this transit."""
        self.ais_stream_enabled = False
        self.tracking_status = 'not_started'
        self.message_post(body=_('AIS tracking stopped.'))

    def action_update_position(self):
        """Trigger an async update, don't block UI."""
        if not self.ship_mmsi or not self.ais_stream_enabled:
            return

        config_params = self.env['ir.config_parameter'].sudo()
        api_key = config_params.get_param('ais_key')
        api_url = config_params.get_param('hagbes_procurement_management.ais_stream_api_url', "wss://stream.aisstream.io/v0/stream")
        ship_mmsi = self.ship_mmsi
        transit_id = self.id

        def fetch_and_update(api_key, api_url, ship_mmsi, transit_id):
            import websocket
            import json
            from datetime import datetime
            _logger.info(f"[AIS TRACKING - {transit_id}] Starting fetch for MMSI: {ship_mmsi}")
            pos_report = None
            try:
                _logger.info(f"[AIS TRACKING - {transit_id}] Creating WebSocket connection to {api_url}")
                ws = websocket.create_connection(api_url, timeout=10)
                _logger.info(f"[AIS TRACKING - {transit_id}] Connection successful. Sending subscription.")
                subscription_message = {
                    "APIkey": api_key,
                    "BoundingBoxes": [[[-90, -180], [90, 180]]],
                    "FilterMessageTypes": ["PositionReport"],
                    "FiltersShipMMSI": [ship_mmsi]
                }
                ws.send(json.dumps(subscription_message))
                _logger.info(f"[AIS TRACKING - {transit_id}] Subscription sent. Waiting for position report...")
                start_time = datetime.now()
                while (datetime.now() - start_time).seconds < 130:
                    try:
                        ws.settimeout(10)
                        message_json = ws.recv()
                        _logger.info(f"[AIS TRACKING - {transit_id}] Received raw message: {message_json}")
                        if not message_json: continue
                        data = json.loads(message_json)
                        if data.get('MessageType') == 'PositionReport' and data['Message'].get('PositionReport'):
                            pos_report = data['Message']['PositionReport']
                            _logger.info(f"[AIS TRACKING - {transit_id}] Successfully parsed PositionReport: {pos_report}")
                            # Also capture metadata like ShipName
                            if data.get('MetaData') and data['MetaData'].get('ShipName'):
                                pos_report['ShipName'] = data['MetaData']['ShipName'].strip()
                            break # Exit loop once we have a position

                    except websocket.WebSocketTimeoutException:
                        _logger.warning(f"[AIS TRACKING - {transit_id}] WebSocket receive timed out. Still waiting...")
                        continue
                ws.close()
                _logger.info(f"[AIS TRACKING - {transit_id}] WebSocket connection closed.")
            except Exception as e:
                _logger.error(f"[AIS TRACKING - {transit_id}] An error occurred during WebSocket communication: {e}", exc_info=True)
                pos_report = None

            # Update the record in a new environment/cursor
            if pos_report:
                _logger.info(f"[AIS TRACKING - {transit_id}] Found position report. Updating Odoo record.")
                # Create a new environment for the thread
                db_name = self.env.cr.dbname
                registry = self.pool
                with registry.cursor() as cr:
                    env = api.Environment(cr, self.env.uid, {})
                    transit = env['foreign.transit.process'].browse(transit_id).sudo()
                    # Use sudo() if the cron user might not have write access
                    if transit.exists():
                        transit.write({
                            'vessel_name': pos_report.get('ShipName') or transit.vessel_name,
                            'current_latitude': pos_report.get('Latitude'),
                            'current_longitude': pos_report.get('Longitude'),
                            'current_speed': pos_report.get('Sog'),
                            'current_course': pos_report.get('Cog'),
                            'last_position_update': fields.Datetime.now(),
                            'tracking_status': 'tracking'
                        })
                        transit._check_arrival_status()
            else:
                _logger.warning(f"[AIS TRACKING - {transit_id}] No position report received within the time limit.")

        # Start background thread with only primitive data
        threading.Thread(target=fetch_and_update, args=(api_key, api_url, ship_mmsi, transit_id), daemon=True).start()

    def _simulate_position_update(self):
        """Simulate position update for demo purposes"""
        import random
        if self.current_latitude and self.current_longitude:
            lat_change, lon_change = random.uniform(-0.01, 0.01), random.uniform(-0.01, 0.01)
            self.write({
                'current_latitude': self.current_latitude + lat_change,
                'current_longitude': self.current_longitude + lon_change,
                'current_speed': random.uniform(10, 15),
                'current_course': random.uniform(0, 360),
                'last_position_update': fields.Datetime.now(),
                'tracking_status': 'tracking'
            })
            self.message_post(body=_('Position updated (simulated): Lat %s, Lon %s') % (self.current_latitude, self.current_longitude))

    def _check_arrival_status(self):
        """Check if vessel has arrived at destination port based on speed."""
        if not (self.current_latitude and self.current_longitude and self.port_of_entry):
            return
        if self.current_speed and self.current_speed < 1.0:
            if self.tracking_status != 'arrived':
                self.tracking_status = 'arrived'
                if self.state == 'in_transit':
                    self.action_arrive_destination()

    @api.model
    def create(self, vals):
        if not vals.get('name') or vals.get('name') == 'New':
            branch_code = '00'
            if vals.get('purchase_order_id'):
                po = self.env['purchase.order'].browse(vals['purchase_order_id'])
                branch_code = po.branch_id.code if po.branch_id else '00'
            year = datetime.now().year
            seq = self.env['ir.sequence'].next_by_code('foreign.transit.process') or '00000'
            vals['name'] = f"TR{branch_code}{year}{seq[-5:]}"
        return super(ForeignTransitProcess, self).create(vals)

    @api.onchange('purchase_order_id')
    def _onchange_purchase_order_id(self):
        """
        Auto-populate data from the related Bank Process when a PO is selected.
        This includes container details, BL number, and gross weight.
        """
        if not self.purchase_order_id:
            return

      
        bank_process = self.env['foreign.bank.process'].search([
            ('purchase_order_id', '=', self.purchase_order_id.id)
        ], limit=1)

        if not bank_process:
            self.container_ids = [(5, 0, 0)]  
            return

      
        self.bill_of_lading_number = bank_process.bl_awb_dhl_no
        self.gross_weight = bank_process.gross_weight
        self.branch_id = self.purchase_order_id.branch_id.id

        
        self.container_ids = [(5, 0, 0)]
        
        container_vals_list = []
        for bank_container in bank_process.container_ids:
            container_vals_list.append((0, 0, {
                'container_number': bank_container.container_number,
                'container_type': bank_container.container_type,
                'container_size': bank_container.container_size,
                'seal_number': bank_container.seal_number,
                'weight_gross': bank_container.gross_weight,
                'weight_net': bank_container.net_weight,
            }))
        
        if container_vals_list:
            self.container_ids = container_vals_list

    @api.onchange('shipment_id')
    def _onchange_shipment_id(self):
        """
        Auto-populate data from the related Shipment record.
        """
        if self.shipment_id:
            self.vessel_name = self.shipment_id.vessel_name
            self.imo_number = self.shipment_id.ship_imo_number
            self.mmsi_number = self.shipment_id.ship_mmsi
            self.flag_state = self.shipment_id.ship_flag.id
            self.port_of_loading = self.shipment_id.port_of_loading
            self.port_eta = self.shipment_id.expected_arrival_date
        else:
            self.vessel_name = self.imo_number = self.mmsi_number = self.flag_state = self.port_of_loading = self.port_eta = False

    @api.model
    def cron_update_all_tracking_transits(self):
        """Cron job to update positions for all active transits."""
        tracking_transits = self.search([
            ('ais_stream_enabled', '=', True),
            ('tracking_status', '=', 'tracking'),
            ('state', 'in', ['in_transit', 'departed_origin'])
        ])
        
        for transit in tracking_transits:
            try:
                transit.action_update_position()
            except Exception as e:
                _logger.error(f"Failed to update position for transit {transit.name}: {str(e)}")

    @api.model
    def cron_check_for_delayed_transits(self):
        """
        Scheduled action to automatically mark transit processes as delayed
        if the current date is past the estimated last date.
        """
        _logger.info("Running cron job to check for delayed transits...")
        today = fields.Date.context_today(self)
        # Find transits that are not yet completed/cancelled and have an estimated date in the past
        delayed_transits = self.search([
            ('state', 'not in', ['completed', 'cancelled', 'delayed']),
            ('estimated_last_date', '<', today)
        ])
        for transit in delayed_transits:
            transit.state = 'delayed'
            transit.message_post(body=_("Process automatically marked as delayed because the current date has passed the 'Estimated Last Date'."))
        _logger.info(f"Cron job finished. Marked {len(delayed_transits)} transits as delayed.")

class ForeignTransitCustomsDeclaration(models.Model):
    _name = 'foreign.transit.customs.declaration'
    _description = 'Foreign Transit Customs Declaration'
    _order = 'declaration_date desc'

    transit_id = fields.Many2one(
        'foreign.transit.process',
        string='Transit Process',
        required=True,
        ondelete='cascade'
    )

    declaration_number = fields.Char(
        string='Declaration Number',
        required=True,
        tracking=True
    )

    declaration_type = fields.Selection([
        ('s_type', 'S-Type (Storage)'),
        ('c_type', 'C-Type (Clearance)'),
        ('t_type', 'T-Type (Transit)'),
    ], string='Declaration Type', required=True, tracking=True)
    
    hs_code = fields.Char(string='HS Code', tracking=True)
    currency_id = fields.Many2one('res.currency', string='Currency', related='transit_id.currency_id')
    assessment_amount = fields.Monetary(string='Assessment Amount', currency_field='currency_id', tracking=True)
    penalties = fields.Monetary(string='Penalties', currency_field='currency_id', tracking=True)

    declaration_date = fields.Date(
        string='Declaration Date',
        required=True,
        tracking=True
    )

    quantity_declared = fields.Float(
        string='Quantity Declared',
        digits='Product Unit of Measure',
        tracking=True
    )

    quantity_cleared = fields.Float(
        string='Quantity Cleared',
        digits='Product Unit of Measure',
        tracking=True
    )

    assessor_name = fields.Char(
        string='Assessor Name',
        tracking=True
    )

    assessment_date = fields.Date(
        string='Assessment Date',
        tracking=True
    )

    status = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('under_assessment', 'Under Assessment'),
        ('assessed', 'Assessed'),
        ('cleared', 'Cleared'),
        ('rejected', 'Rejected'),
    ], string='Status', default='draft', tracking=True)

    notes = fields.Text(string='Notes')


class ForeignTransitContainer(models.Model):
    _name = 'foreign.transit.container'
    _description = 'Foreign Transit Container'
    _order = 'container_number'

    transit_id = fields.Many2one(
        'foreign.transit.process',
        string='Transit Process',
        required=True,
        ondelete='cascade'
    )
    
    container_number = fields.Char(
        string='Container Number',
        required=True
    )
    
    container_type = fields.Selection([
        ('20ft', '20ft Container'),
        ('40ft', '40ft Container'),
        ('40ft_hc', '40ft High Cube'),
        ('45ft', '45ft Container'),
    ], string='Container Type', required=True)
    
    container_size = fields.Selection([
        ('20', '20 FEET'),
        ('40', '40 FEET'),
        ('45', '45 FEET'),
    ], string='Size', tracking=True)
    
    flat_rack = fields.Boolean(string='Flat Rack')
    
    seal_number = fields.Char(string='Seal Number')
    
    weight_gross = fields.Float(
        string='Gross Weight (KG)',
        digits='Stock Weight'
    )
    
    weight_net = fields.Float(
        string='Net Weight (KG)',
        digits='Stock Weight'
    )
    
    status = fields.Selection([
        ('in_transit', 'In Transit'),
        ('arrived', 'Arrived'),
        ('customs_hold', 'Customs Hold'),
        ('released', 'Released'),
    ], string='Status', default='in_transit')
    
    
    arrival_date = fields.Date(
        string='Arrival Date',
        tracking=True
    )
    
    arrival_time = fields.Char(
        string='Arrival Time',
        help='Time in HH:MM format'
    )
    
    departure_date = fields.Date(
        string='Departure Date',
        tracking=True
    )
    
    departure_time = fields.Char(
        string='Departure Time',
        help='Time in HH:MM format'
    )
    
    return_date = fields.Date(
        string='Container Return Date',
        tracking=True
    )
    
    starting_date_border_port = fields.Date(
        string='Starting Date Border/Port',
        tracking=True
    )

   
    truck_plate_number = fields.Char(
        string='Truck Plate Number',
        tracking=True
    )
    
    trailer_plate_number = fields.Char(
        string='Trailer Plate Number',
        tracking=True
    )
    
    transporter_name = fields.Char(
        string='Transporter',
        tracking=True
    )
    
    driver_name = fields.Char(
        string='Driver Name',
        tracking=True
    )
    
    driver_mobile = fields.Char(
        string='Driver Mobile Number'
    )


class ForeignTransitBondedWarehouse(models.Model):
    _name = 'foreign.transit.bonded.warehouse'
    _description = 'Foreign Transit Bonded Warehouse'

    name = fields.Char(string='Warehouse Name', required=True)
    code = fields.Char(string='Warehouse Code', required=True)
    location = fields.Char(string='Location', required=True)
    
    capacity = fields.Float(
        string='Capacity (CBM)',
        digits='Product Unit of Measure'
    )
    
    contact_person = fields.Char(string='Contact Person')
    phone = fields.Char(string='Phone')
    email = fields.Char(string='Email')
    
    active = fields.Boolean(string='Active', default=True)
    
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company
    )


class ForeignTransitDocument(models.Model):
    _name = "foreign.transit.document"
    _description = "Foreign Transit Document"

    transit_id = fields.Many2one(
        'foreign.transit.process',
        string='Transit Process',
        required=True,
        ondelete='cascade'
    )

    document_type = fields.Selection([
        ('invoice', 'Invoice'),
        ('bill_of_lading', 'Bill of Lading'),
        ('packing_list', 'Packing List'),
        ('certificate_origin', 'Certificate of Origin'),
        ('insurance_certificate', 'Insurance Certificate'),
        ('customs_declaration', 'Customs Declaration'),
    ], string="Document Type", required=True)

    document_number = fields.Char(string="Document Number")
    document_date = fields.Date(string="Document Date")
    
    document_category = fields.Selection([
        ('insa', 'INSA'),
        ('min_agri', 'Ministry of Agriculture'),
        ('bank', 'Bank Document'),
        ('other', 'Other'),
    ], string="Document Category", default='other')
    is_first_document = fields.Boolean(string="Is First Document")
    
    is_required = fields.Boolean(string="Is Required", default=True)
    is_received = fields.Boolean(string="Is Received")
    attachment_id = fields.Many2one(
        "ir.attachment",
        string="Attachment",
        ondelete="set null"
    )
    notes = fields.Text(string="Notes")
