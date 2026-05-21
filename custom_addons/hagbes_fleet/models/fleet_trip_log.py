# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class HagbesFleetTripLog(models.Model):
    _name = 'hagbes.fleet.trip.log'
    _description = 'Fleet Trip Log'
    _order = 'start_time desc, id desc'

    # ─── Core Relationships ───────────────────────────────────────────────────
    allocation_id = fields.Many2one(
        'hagbes.fleet.allocation',
        string='Allocation',
        required=True,
        ondelete='cascade',
        index=True,
        help='The allocation this trip log belongs to',
    )

    # ─── Odometer Readings ────────────────────────────────────────────────────
    start_odometer = fields.Float(
        string='Start Odometer',
        digits=(10, 2),
        help='Odometer reading at trip start',
    )
    end_odometer = fields.Float(
        string='End Odometer',
        digits=(10, 2),
        help='Odometer reading at trip end',
    )
    actual_distance = fields.Float(
        string='Actual Distance (KM)',
        digits=(10, 2),
        compute='_compute_actual_distance',
        store=True,
        help='Computed as end_odometer - start_odometer',
    )

    # ─── Fuel Tracking ────────────────────────────────────────────────────────
    fuel_used = fields.Float(
        string='Fuel Used (L)',
        digits=(10, 2),
        help='Actual fuel consumed during the trip',
    )

    # ─── Time Tracking ────────────────────────────────────────────────────────
    start_time = fields.Datetime(
        string='Start Time',
        help='Trip start timestamp',
    )
    end_time = fields.Datetime(
        string='End Time',
        help='Trip end timestamp',
    )

    # ─── GPS Data ─────────────────────────────────────────────────────────────
    gps_coordinates = fields.Text(
        string='GPS Coordinates',
        help='Optional free-text summary of GPS coordinates',
    )

    # =========================================================================
    # Computed Fields
    # =========================================================================

    @api.depends('start_odometer', 'end_odometer')
    def _compute_actual_distance(self):
        """Compute actual distance as end_odometer - start_odometer."""
        for rec in self:
            if rec.end_odometer and rec.start_odometer:
                rec.actual_distance = rec.end_odometer - rec.start_odometer
            else:
                rec.actual_distance = 0.0

    # =========================================================================
    # Constraints
    # =========================================================================

    @api.constrains('end_odometer', 'start_odometer')
    def _check_odometer_values(self):
        """Ensure end_odometer >= start_odometer."""
        for rec in self:
            if rec.end_odometer and rec.start_odometer:
                if rec.end_odometer < rec.start_odometer:
                    raise ValidationError(
                        _('End odometer (%s) must be greater than or equal to start odometer (%s).')
                        % (rec.end_odometer, rec.start_odometer)
                    )

    @api.constrains('end_time', 'start_time')
    def _check_time_values(self):
        """Ensure end_time >= start_time."""
        for rec in self:
            if rec.end_time and rec.start_time:
                if rec.end_time < rec.start_time:
                    raise ValidationError(
                        _('End time must be after or equal to start time.')
                    )
