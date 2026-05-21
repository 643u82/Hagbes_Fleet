# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, AccessError
import logging

_logger = logging.getLogger(__name__)


class FleetTrip(models.Model):
    """
    FIXED Fleet Trip Model - Corrected group references
    
    Fixes: Changed group_fleet_operator to group_fmo (actual group name)
    """
    
    _name = 'fleet.trip'
    _description = 'Fleet Trip Execution'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'allocation_date desc, id desc'

    # ─── Identification ───────────────────────────────────────────────────────
    name = fields.Char(
        string='Reference',
        readonly=True,
        copy=False,
        default='New',
        index=True,
        required=True,
    )
    requisition_id = fields.Many2one(
        'fleet.requisition',
        string='Requisition',
        help='Original requisition that created this trip'
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )

    # ─── Trip Details (from requisition) ─────────────────────────────────────
    purpose = fields.Text(
        string='Purpose',
        required=True,
        tracking=True,
    )
    destination = fields.Char(
        string='Destination',
        required=True,
        tracking=True,
    )
    date_from = fields.Datetime(
        string='Start Date',
        required=True,
        tracking=True,
    )
    date_to = fields.Datetime(
        string='End Date',
        required=True,
        tracking=True,
    )
    allocation_date = fields.Datetime(
        string='Allocation Date',
        default=fields.Datetime.now,
        tracking=True,
    )

    # ─── Assignment Details ─────────────────────────────────────────────
    vehicle_id = fields.Many2one(
        'fleet.vehicle',
        string='Vehicle',
        required=True,
        tracking=True,
        help='Vehicle assigned for this trip'
    )
    driver_id = fields.Many2one(
        'hr.employee',
        string='Driver',
        required=True,
        tracking=True,
        help='Driver assigned for this trip'
    )
    driver_name = fields.Char(
        string='Driver Name',
        compute='_compute_driver_name',
        store=True,
    )

    @api.depends('driver_id')
    def _compute_driver_name(self):
        for trip in self:
            trip.driver_name = trip.driver_id.name if trip.driver_id else ''

    # ─── State Machine ───────────────────────────────────────────────
    state = fields.Selection([
        ('planned', 'Planned'),
        ('assigned', 'Assigned'),
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='planned', tracking=True, copy=False)

    # ─── Execution Tracking ─────────────────────────────────────────────────
    odometer_start = fields.Integer(
        string='Start Odometer',
        help='Vehicle odometer at trip start'
    )
    odometer_end = fields.Integer(
        string='End Odometer',
        help='Vehicle odometer at trip end'
    )
    fuel_start = fields.Float(
        string='Start Fuel (L)',
        help='Vehicle fuel level at trip start'
    )
    fuel_end = fields.Float(
        string='End Fuel (L)',
        help='Vehicle fuel level at trip end'
    )
    
    # GPS Tracking
    gps_tracking_enabled = fields.Boolean(
        string='GPS Tracking',
        default=True,
        tracking=True,
    )
    current_latitude = fields.Float(
        string='Current Latitude',
        digits=(10, 6),
        help='Current GPS latitude'
    )
    current_longitude = fields.Float(
        string='Current Longitude', 
        digits=(10, 6),
        help='Current GPS longitude'
    )
    last_gps_update = fields.Datetime(
        string='Last GPS Update',
        readonly=True,
    )
    
    # Trip Logs
    log_ids = fields.One2many(
        'fleet.trip.log',
        'trip_id',
        string='Trip Logs'
    )
    notes = fields.Text(
        string='Trip Notes',
        help='Additional trip notes and observations'
    )

    # ─── Audit Fields ───────────────────────────────────────────────────────────
    assigned_by = fields.Many2one(
        'res.users',
        string='Assigned By',
        readonly=True,
        copy=False,
    )
    assigned_date = fields.Datetime(
        string='Assigned Date',
        readonly=True,
        copy=False,
    )
    started_by = fields.Many2one(
        'res.users',
        string='Started By',
        readonly=True,
        copy=False,
    )
    started_date = fields.Datetime(
        string='Started Date',
        readonly=True,
        copy=False,
    )
    completed_by = fields.Many2one(
        'res.users',
        string='Completed By',
        readonly=True,
        copy=False,
    )
    completed_date = fields.Datetime(
        string='Completed Date',
        readonly=True,
        copy=False,
    )

    # ─── Computed Fields ───────────────────────────────────────────────────────
    distance_traveled = fields.Integer(
        string='Distance (km)',
        compute='_compute_distance_traveled',
        store=True,
    )
    fuel_used = fields.Float(
        string='Fuel Used (L)',
        compute='_compute_fuel_used',
        store=True,
    )
    duration_hours = fields.Float(
        string='Duration (hours)',
        compute='_compute_duration',
        store=True,
    )

    @api.depends('odometer_start', 'odometer_end')
    def _compute_distance_traveled(self):
        for trip in self:
            if trip.odometer_start and trip.odometer_end:
                trip.distance_traveled = trip.odometer_end - trip.odometer_start
            else:
                trip.distance_traveled = 0

    @api.depends('fuel_start', 'fuel_end')
    def _compute_fuel_used(self):
        for trip in self:
            if trip.fuel_start and trip.fuel_end:
                trip.fuel_used = trip.fuel_start - trip.fuel_end
            else:
                trip.fuel_used = 0

    @api.depends('date_from', 'date_to')
    def _compute_duration(self):
        for trip in self:
            if trip.date_from and trip.date_to:
                duration = trip.date_to - trip.date_from
                trip.duration_hours = duration.total_seconds() / 3600
            else:
                trip.duration_hours = 0

    # ─── Default Methods ───────────────────────────────────────────────────────
    @api.model
    def create(self, vals):
        """Create trip with automatic reference and vehicle status update"""
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('fleet.trip') or 'New'
        
        trip = super().create(vals)
        
        # Update vehicle status if assigned
        if trip.vehicle_id and trip.state == 'assigned':
            trip.vehicle_id.write({'state': 'assigned'})
        
        return trip

    # ─── Constraints ─────────────────────────────────────────────────────────--
    @api.constrains('vehicle_id', 'state', 'date_from', 'date_to')
    def _check_vehicle_availability(self):
        """Prevent double booking of vehicles"""
        for trip in self:
            if trip.vehicle_id and trip.state in ['assigned', 'active']:
                overlapping = self.search([
                    ('vehicle_id', '=', trip.vehicle_id.id),
                    ('state', 'in', ['assigned', 'active']),
                    ('id', '!=', trip.id),
                    '|', '&', ('date_from', '<=', trip.date_to), ('date_to', '>=', trip.date_from)
                ])
                if overlapping:
                    raise ValidationError(
                        _('Vehicle %s is already assigned during this period') % trip.vehicle_id.name
                    )

    @api.constrains('odometer_start', 'odometer_end')
    def _check_odometer_logic(self):
        """Validate odometer readings"""
        for trip in self:
            if trip.odometer_end and trip.odometer_start:
                if trip.odometer_end < trip.odometer_start:
                    raise ValidationError(_('End odometer must be greater than start odometer'))
                
                if trip.vehicle_id and trip.odometer_start < trip.vehicle_id.odometer:
                    raise ValidationError(
                        _('Start odometer cannot be less than vehicle current odometer')
                    )

    @api.constrains('date_from', 'date_to')
    def _check_date_logic(self):
        """Validate date logic"""
        for trip in self:
            if trip.date_from and trip.date_to:
                if trip.date_from >= trip.date_to:
                    raise ValidationError(_('Start date must be before end date'))

    # ─── Business Logic Methods ─────────────────────────────────────────────────
    def action_assign_vehicle(self):
        """Assign vehicle and driver to trip"""
        self.ensure_one()
        
        # FIXED: Use correct group reference
        if not self.env.user.has_group('hagbes_fleet.group_fmo'):
            raise AccessError(_('Only Fleet Operators can assign vehicles'))
        
        # State validation
        if self.state != 'planned':
            raise ValidationError(_('Only planned trips can be assigned vehicles'))
        
        # Required fields validation
        if not self.vehicle_id:
            raise ValidationError(_('Vehicle is required for assignment'))
        
        if not self.driver_id:
            raise ValidationError(_('Driver is required for assignment'))
        
        # Vehicle availability validation
        if self.vehicle_id.state != 'available':
            raise ValidationError(_('Vehicle %s is not available') % self.vehicle_id.name)
        
        # Perform assignment
        self.write({
            'state': 'assigned',
            'assigned_by': self.env.user.id,
            'assigned_date': fields.Datetime.now(),
        })
        
        # Update vehicle status
        self.vehicle_id.write({'state': 'assigned'})
        
        # Create initial log
        self.env['fleet.trip.log'].create({
            'trip_id': self.id,
            'log_type': 'assignment',
            'message': _('Vehicle %s assigned to driver %s') % (
                self.vehicle_id.name, self.driver_id.name
            ),
        })
        
        self.message_post(body=_('Vehicle assigned successfully'))

    def action_start_trip(self):
        """Start the trip execution"""
        self.ensure_one()
        
        # FIXED: Use correct group reference
        is_driver = self.driver_id.user_id == self.env.user
        is_operator = self.env.user.has_group('hagbes_fleet.group_fmo')
        
        if not (is_driver or is_operator):
            raise AccessError(_('Only assigned driver or Fleet Operator can start trip'))
        
        # State validation
        if self.state != 'assigned':
            raise ValidationError(_('Only assigned trips can be started'))
        
        # Odometer validation
        if not self.odometer_start:
            raise ValidationError(_('Start odometer reading is required'))
        
        # Perform start
        self.write({
            'state': 'active',
            'started_by': self.env.user.id,
            'started_date': fields.Datetime.now(),
        })
        
        # Update vehicle status
        self.vehicle_id.write({'state': 'in_use'})
        
        # Create start log
        self.env['fleet.trip.log'].create({
            'trip_id': self.id,
            'log_type': 'start',
            'message': _('Trip started by %s') % self.env.user.name,
        })
        
        self.message_post(body=_('Trip started'))

    def action_complete_trip(self):
        """Complete the trip"""
        self.ensure_one()
        
        # FIXED: Use correct group reference
        is_driver = self.driver_id.user_id == self.env.user
        is_operator = self.env.user.has_group('hagbes_fleet.group_fmo')
        
        if not (is_driver or is_operator):
            raise AccessError(_('Only assigned driver or Fleet Operator can complete trip'))
        
        # State validation
        if self.state != 'active':
            raise ValidationError(_('Only active trips can be completed'))
        
        # End data validation
        if not self.odometer_end:
            raise ValidationError(_('End odometer reading is required'))
        
        # Perform completion
        self.write({
            'state': 'completed',
            'completed_by': self.env.user.id,
            'completed_date': fields.Datetime.now(),
        })
        
        # Update vehicle
        distance = self.distance_traveled
        self.vehicle_id.write({
            'state': 'available',
            'odometer': self.odometer_end,
        })
        
        # Update requisition if exists
        if self.requisition_id:
            self.requisition_id.write({'state': 'completed'})
        
        # Create completion log
        self.env['fleet.trip.log'].create({
            'trip_id': self.id,
            'log_type': 'completion',
            'message': _('Trip completed. Distance: %s km') % distance,
        })
        
        self.message_post(body=_('Trip completed successfully'))

    def action_cancel(self):
        """Cancel the trip"""
        self.ensure_one()
        
        # FIXED: Use correct group reference
        if not self.env.user.has_group('hagbes_fleet.group_fmo'):
            raise AccessError(_('Only Fleet Operators can cancel trips'))
        
        # State validation
        if self.state in ['completed']:
            raise ValidationError(_('Cannot cancel completed trips'))
        
        # Release vehicle if assigned
        if self.vehicle_id and self.state in ['assigned', 'active']:
            self.vehicle_id.write({'state': 'available'})
        
        # Perform cancellation
        self.write({'state': 'cancelled'})
        
        # Create cancellation log
        self.env['fleet.trip.log'].create({
            'trip_id': self.id,
            'log_type': 'cancellation',
            'message': _('Trip cancelled by %s') % self.env.user.name,
        })
        
        self.message_post(body=_('Trip cancelled'))

    # ─── GPS Tracking Methods ───────────────────────────────────────────────────
    def update_gps_location(self, latitude, longitude):
        """Update GPS location for active trips"""
        self.ensure_one()
        
        if self.state != 'active':
            return False
        
        if self.gps_tracking_enabled:
            self.write({
                'current_latitude': latitude,
                'current_longitude': longitude,
                'last_gps_update': fields.Datetime.now(),
            })
            
            # Create GPS log
            self.env['fleet.trip.log'].create({
                'trip_id': self.id,
                'log_type': 'gps',
                'message': _('GPS update: %s, %s') % (latitude, longitude),
            })
            
        return True

    # ─── Helper Methods ───────────────────────────────────────────────────────
    def get_trip_summary(self):
        """Get trip summary for reporting"""
        self.ensure_one()
        return {
            'name': self.name,
            'vehicle': self.vehicle_id.name if self.vehicle_id else 'Unassigned',
            'driver': self.driver_id.name if self.driver_id else 'Unassigned',
            'destination': self.destination,
            'date_from': self.date_from,
            'date_to': self.date_to,
            'state': self.state,
            'distance': self.distance_traveled,
            'fuel_used': self.fuel_used,
            'duration': self.duration_hours,
        }


class FleetTripLog(models.Model):
    """
    Trip Log Model
    """
    
    _name = 'fleet.trip.log'
    _description = 'Fleet Trip Log'
    _order = 'create_date desc, id desc'

    trip_id = fields.Many2one(
        'fleet.trip',
        string='Trip',
        required=True,
        ondelete='cascade',
    )
    log_type = fields.Selection([
        ('assignment', 'Assignment'),
        ('start', 'Start'),
        ('completion', 'Completion'),
        ('cancellation', 'Cancellation'),
        ('gps', 'GPS Update'),
        ('note', 'Note'),
        ('issue', 'Issue'),
    ], string='Log Type', required=True)
    message = fields.Text(
        string='Message',
        required=True,
    )
    create_date = fields.Datetime(
        string='Log Date',
        default=fields.Datetime.now,
        readonly=True,
    )
    create_uid = fields.Many2one(
        'res.users',
        string='Logged By',
        readonly=True,
    )
