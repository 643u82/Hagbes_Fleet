# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class FleetVehicle(models.Model):
    """
    CONSOLIDATED Fleet Vehicle Model - Single Source of Truth for Asset Layer
    
    Extends core fleet.vehicle with ONLY asset management functionality
    Responsibility: Vehicle status, maintenance, availability
    NO: Assignment logic, trip execution, business workflow
    """
    
    _inherit = 'fleet.vehicle'

    # ─── Operational State Management (simplified) ───────────────────────────────
    operational_state = fields.Selection([
        ('available', 'Available'),
        ('assigned', 'Assigned'),
        ('in_use', 'In Use'), 
        ('maintenance', 'Maintenance'),
        ('unavailable', 'Unavailable'),
    ], string='Operational State', default='available', tracking=True)

    # ─── Assignment Tracking (read-only, managed by trip model) ─────────────────────
    current_trip_id = fields.Many2one(
        'fleet.trip',
        string='Current Trip',
        readonly=True,
        help='Currently assigned trip'
    )
    current_driver_id = fields.Many2one(
        'hr.employee',
        string='Current Driver',
        readonly=True,
        related='current_trip_id.driver_id',
        store=True,
    )
    last_odometer = fields.Integer(
        string='Last Odometer Reading',
        readonly=True,
        help='Last recorded odometer reading'
    )

    # ─── Maintenance Integration (consolidated from fleet_maintenance.py) ─────────────
    maintenance_due = fields.Boolean(
        string='Maintenance Due',
        compute='_compute_maintenance_due',
        store=True,
    )
    last_maintenance_date = fields.Date(
        string='Last Maintenance Date',
        readonly=True,
    )
    last_maintenance_odometer = fields.Integer(
        string='Last Maintenance Odometer',
        readonly=True,
        help='Odometer reading at last maintenance'
    )
    next_maintenance_date = fields.Date(
        string='Next Maintenance Date',
        compute='_compute_next_maintenance_date',
        store=True,
    )
    maintenance_ids = fields.One2many(
        'fleet.maintenance',
        'vehicle_id',
        string='Maintenance Records',
    )

    @api.depends('odometer', 'last_maintenance_odometer')
    def _compute_maintenance_due(self):
        """Check if maintenance is due based on odometer"""
        for vehicle in self:
            if vehicle.last_maintenance_odometer:
                km_since_maintenance = vehicle.odometer - vehicle.last_maintenance_odometer
                vehicle.maintenance_due = km_since_maintenance >= 5000  # Every 5000 km
            else:
                # No maintenance recorded, due at 5000 km
                vehicle.maintenance_due = vehicle.odometer >= 5000

    @api.depends('last_maintenance_date')
    def _compute_next_maintenance_date(self):
        """Compute next maintenance date (every 6 months)"""
        for vehicle in self:
            if vehicle.last_maintenance_date:
                # Add 6 months to last maintenance date
                from datetime import timedelta, date
                next_date = vehicle.last_maintenance_date + timedelta(days=180)
                vehicle.next_maintenance_date = next_date
            else:
                vehicle.next_maintenance_date = False

    # ─── Vehicle Status Validation ───────────────────────────────────────────────
    @api.constrains('operational_state', 'current_trip_id')
    def _check_state_consistency(self):
        """Ensure state consistency with current assignment"""
        for vehicle in self:
            if vehicle.current_trip_id:
                if vehicle.operational_state not in ['assigned', 'in_use']:
                    raise ValidationError(
                        _('Vehicle with active trip must be in assigned or in_use state')
                    )
            else:
                if vehicle.operational_state in ['assigned', 'in_use']:
                    raise ValidationError(
                        _('Vehicle without active trip cannot be in assigned or in_use state')
                    )

    def write(self, vals):
        """Override write to enforce state transitions and maintenance checks"""
        # Prevent state conflicts
        if 'operational_state' in vals:
            new_state = vals['operational_state']
            current_state = self.operational_state
            
            # Cannot assign vehicle if maintenance due
            if new_state == 'assigned' and self.maintenance_due:
                raise ValidationError(_('Cannot assign vehicle. Maintenance is required.'))
            
            # Cannot make available if currently in use
            if new_state == 'available' and current_state == 'in_use':
                raise ValidationError(_('Cannot make vehicle available while in use.'))
            
            # Cannot start maintenance if vehicle is in use
            if new_state == 'maintenance' and current_state == 'in_use':
                raise ValidationError(_('Cannot put vehicle in maintenance while in use.'))
        
        return super().write(vals)

    # ─── Asset Management Methods ───────────────────────────────────────────────────
    def action_mark_available(self):
        """Mark vehicle as available"""
        self.write({
            'operational_state': 'available',
            'current_trip_id': False,
        })

    def action_schedule_maintenance(self):
        """Put vehicle in maintenance"""
        if self.operational_state == 'in_use':
            raise ValidationError(_('Cannot schedule maintenance for vehicle in use'))
        
        self.write({'operational_state': 'maintenance'})
        
        # Create maintenance record
        self.env['fleet.maintenance'].create({
            'vehicle_id': self.id,
            'maintenance_date': fields.Date.today(),
            'maintenance_type': 'scheduled',
            'description': _('Scheduled maintenance'),
        })

    def action_complete_maintenance(self):
        """Complete maintenance and make vehicle available"""
        if self.operational_state != 'maintenance':
            raise ValidationError(_('Vehicle is not in maintenance'))
        
        # Update maintenance tracking
        self.write({
            'operational_state': 'available',
            'last_maintenance_date': fields.Date.today(),
            'last_maintenance_odometer': self.odometer,
        })
        
        # Update last maintenance record
        last_maintenance = self.env['fleet.maintenance'].search([
            ('vehicle_id', '=', self.id),
            ('state', '=', 'in_progress')
        ], limit=1)
        
        if last_maintenance:
            last_maintenance.write({
                'state': 'completed',
                'completion_date': fields.Date.today(),
            })

    def action_mark_unavailable(self):
        """Mark vehicle as unavailable (for other reasons)"""
        if self.operational_state == 'in_use':
            raise ValidationError(_('Cannot make vehicle unavailable while in use'))
        
        self.write({'operational_state': 'unavailable'})

    # ─── Availability Checking ─────────────────────────────────────────────────────
    def is_available_for_trip(self, date_from, date_to):
        """Check if vehicle is available for given date range"""
        self.ensure_one()
        
        # Check operational state
        if self.operational_state != 'available':
            return False
        
        # Check maintenance due
        if self.maintenance_due:
            return False
        
        # Check for existing trips during the period
        overlapping_trips = self.env['fleet.trip'].search([
            ('vehicle_id', '=', self.id),
            ('state', 'in', ['assigned', 'active']),
            '|', '&', ('date_from', '<=', date_to), ('date_to', '>=', date_from)
        ])
        
        return not bool(overlapping_trips)

    # ─── Reporting Methods ───────────────────────────────────────────────────────
    def get_vehicle_summary(self):
        """Get vehicle summary for reporting"""
        self.ensure_one()
        return {
            'name': self.name,
            'license_plate': self.license_plate,
            'model': self.model_id.name if self.model_id else 'Unknown',
            'operational_state': self.operational_state,
            'odometer': self.odometer,
            'maintenance_due': self.maintenance_due,
            'last_maintenance_date': self.last_maintenance_date,
            'next_maintenance_date': self.next_maintenance_date,
            'current_trip': self.current_trip_id.name if self.current_trip_id else None,
            'current_driver': self.current_driver_id.name if self.current_driver_id else None,
        }

    @api.model
    def get_available_vehicles(self, date_from=None, date_to=None):
        """Get list of available vehicles for given date range"""
        domain = [('operational_state', '=', 'available')]
        
        if date_from and date_to:
            # Exclude vehicles with trips during the period
            busy_vehicles = self.env['fleet.trip'].search([
                ('state', 'in', ['assigned', 'active']),
                '|', '&', ('date_from', '<=', date_to), ('date_to', '>=', date_from)
            ]).mapped('vehicle_id')
            
            if busy_vehicles:
                domain.append(('id', 'not in', busy_vehicles.ids))
        
        return self.search(domain)

    @api.model
    def get_maintenance_due_vehicles(self):
        """Get vehicles that need maintenance"""
        return self.search([('maintenance_due', '=', True)])

    @api.model
    def get_vehicle_utilization(self, date_from, date_to):
        """Get vehicle utilization statistics for date range"""
        total_vehicles = self.search([])
        active_vehicles = self.env['fleet.trip'].search([
            ('date_from', '<=', date_to),
            ('date_to', '>=', date_from),
            ('state', '=', 'completed')
        ]).mapped('vehicle_id')
        
        utilization_rate = len(active_vehicles) / len(total_vehicles) * 100 if total_vehicles else 0
        
        return {
            'total_vehicles': len(total_vehicles),
            'active_vehicles': len(active_vehicles),
            'utilization_rate': round(utilization_rate, 2),
        }


class FleetMaintenance(models.Model):
    """
    CONSOLIDATED Maintenance Model - Single source for maintenance records
    """
    
    _name = 'fleet.maintenance'
    _description = 'Fleet Vehicle Maintenance'
    _order = 'maintenance_date desc, id desc'

    vehicle_id = fields.Many2one(
        'fleet.vehicle',
        string='Vehicle',
        required=True,
        ondelete='cascade',
    )
    maintenance_date = fields.Date(
        string='Maintenance Date',
        required=True,
        default=fields.Date.today,
    )
    maintenance_type = fields.Selection([
        ('scheduled', 'Scheduled'),
        ('unscheduled', 'Unscheduled'),
        ('emergency', 'Emergency'),
    ], string='Maintenance Type', required=True, default='scheduled')
    
    description = fields.Text(
        string='Description',
        required=True,
    )
    cost = fields.Float(
        string='Cost',
        help='Maintenance cost'
    )
    odometer = fields.Integer(
        string='Odometer at Maintenance',
        help='Vehicle odometer reading at maintenance time'
    )
    
    state = fields.Selection([
        ('planned', 'Planned'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='planned', tracking=True)
    
    completion_date = fields.Date(
        string='Completion Date',
        readonly=True,
    )
    notes = fields.Text(
        string='Notes',
        help='Additional maintenance notes'
    )
    
    @api.constrains('maintenance_date', 'completion_date')
    def _check_dates(self):
        """Validate maintenance dates"""
        for maintenance in self:
            if maintenance.completion_date and maintenance.maintenance_date:
                if maintenance.completion_date < maintenance.maintenance_date:
                    raise ValidationError(_('Completion date cannot be before maintenance date'))
    
    def action_start_maintenance(self):
        """Start maintenance work"""
        self.write({
            'state': 'in_progress',
        })
        # Update vehicle status
        self.vehicle_id.write({'operational_state': 'maintenance'})
    
    def action_complete_maintenance(self):
        """Complete maintenance"""
        if not self.completion_date:
            self.completion_date = fields.Date.today()
        
        self.write({'state': 'completed'})
        
        # Update vehicle maintenance tracking
        self.vehicle_id.write({
            'last_maintenance_date': self.completion_date,
            'last_maintenance_odometer': self.odometer or self.vehicle_id.odometer,
        })
        
        # Make vehicle available if no other maintenance planned
        other_maintenance = self.search([
            ('vehicle_id', '=', self.vehicle_id.id),
            ('state', 'in', ['planned', 'in_progress']),
            ('id', '!=', self.id)
        ])
        
        if not other_maintenance:
            self.vehicle_id.write({'operational_state': 'available'})
