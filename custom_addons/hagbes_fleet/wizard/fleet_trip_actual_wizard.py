# -*- coding: utf-8 -*-

from odoo import models, fields, api, _

class FleetTripActualWizard(models.TransientModel):
    _name = 'fleet.trip.actual.wizard'
    _description = 'Record Actual Trip Data'

    trip_id = fields.Many2one('fleet.trip', string='Trip', required=True)
    
    return_date = fields.Date(string='Return Date', default=fields.Date.today, required=True)
    return_time = fields.Float(string='Return Time', required=True)
    
    actual_start_place = fields.Char(string='Actual Starting Place', required=True)
    actual_destination = fields.Char(string='Actual Destination', required=True)
    
    km_at_start_actual = fields.Float(string='KM at Start (Actual Odo.)', required=True)
    km_at_end_actual = fields.Float(string='KM at End (Actual Odo.)', required=True)
    
    transport_km = fields.Float(string='Transport KM', default=0.0)
    signed_by = fields.Char(string='Signed By', required=True)
    
    discrepancy_reason = fields.Text(string='Discrepancy Reason')

    @api.onchange('trip_id')
    def _onchange_trip_id(self):
        if self.trip_id:
            self.actual_start_place = self.trip_id.start_location
            self.km_at_start_actual = self.trip_id.km_at_start
            # Get previous trip's end KM if not set
            if not self.km_at_start_actual:
                self.km_at_start_actual = self.trip_id.prev_trip_km_end

    def action_confirm(self):
        self.ensure_one()
        self.trip_id.write({
            'return_date': self.return_date,
            'return_time': self.return_time,
            'actual_start_place': self.actual_start_place,
            'actual_destination': self.actual_destination,
            'km_at_start_actual': self.km_at_start_actual,
            'km_at_end_actual': self.km_at_end_actual,
            'transport_km': self.transport_km,
            'signed_by': self.signed_by,
            'discrepancy_reason': self.discrepancy_reason,
        })
        self.trip_id.action_complete_trip()
        if self.trip_id.vehicle_id:
            self.trip_id.vehicle_id._compute_status()
        return {'type': 'ir.actions.act_window_close'}
