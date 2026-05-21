# -*- coding: utf-8 -*-

from odoo import models, fields, api

class FleetVehicleHistory(models.Model):
    _name = 'fleet.vehicle.history'
    _description = 'Vehicle Status History'
    _order = 'check_date desc'

    vehicle_id = fields.Many2one('hagbes.fleet.vehicle', string='Vehicle', required=True, ondelete='cascade')
    check_date = fields.Datetime(string='Check Date', default=fields.Datetime.now, required=True)
    
    driver_status = fields.Selection([
        ('available', 'Available'),
        ('not_available', 'Not Available')
    ], string='Driver Status')
    
    vehicle_status = fields.Selection([
        ('idle', 'Idle'),
        ('parking', 'Parking (Maintenance)'),
        ('in_use', 'In Use')
    ], string='Vehicle Status')
    
    checked_by = fields.Many2one('res.users', string='Checked By', default=lambda self: self.env.user)
    notes = fields.Text(string='Notes')
