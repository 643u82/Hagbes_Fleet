# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError


class FleetTripGPS(models.Model):
    _name = 'hagbes.fleet.trip.gps'
    _description = 'Fleet Trip GPS Point'
    _order = 'timestamp asc'

    trip_id = fields.Many2one(
        'fleet.trip',
        string='Trip',
        required=True,
        ondelete='cascade',
        help='The trip this GPS point belongs to'
    )
    latitude = fields.Float(
        string='Latitude',
        digits=(10, 6),
        help='GPS latitude coordinate'
    )
    longitude = fields.Float(
        string='Longitude',
        digits=(10, 6),
        help='GPS longitude coordinate'
    )
    timestamp = fields.Datetime(
        string='Timestamp',
        required=True,
        help='When this GPS reading was recorded'
    )

    @api.constrains('latitude')
    def _check_latitude_range(self):
        """Validate latitude is within valid range [-90, 90]"""
        for record in self:
            if record.latitude is not False and (record.latitude < -90 or record.latitude > 90):
                raise ValidationError(
                    'Latitude must be between -90 and 90 degrees. '
                    f'Got: {record.latitude}'
                )

    @api.constrains('longitude')
    def _check_longitude_range(self):
        """Validate longitude is within valid range [-180, 180]"""
        for record in self:
            if record.longitude is not False and (record.longitude < -180 or record.longitude > 180):
                raise ValidationError(
                    'Longitude must be between -180 and 180 degrees. '
                    f'Got: {record.longitude}'
                )