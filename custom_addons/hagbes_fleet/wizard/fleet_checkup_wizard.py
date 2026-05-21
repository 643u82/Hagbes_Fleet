# -*- coding: utf-8 -*-

from odoo import models, fields, api, _

class FleetCheckupWizard(models.TransientModel):
    _name = 'fleet.checkup.wizard'
    _description = 'Daily Vehicle Checkup'

    line_ids = fields.One2many('fleet.checkup.wizard.line', 'wizard_id', string='Vehicle Statuses')

    @api.model
    def default_get(self, fields):
        res = super(FleetCheckupWizard, self).default_get(fields)
        vehicles = self.env['hagbes.fleet.vehicle'].search([('status', '!=', 'out_of_service')])
        lines = []
        for vehicle in vehicles:
            # Map existing status to wizard status
            v_status = 'idle'
            if vehicle.status == 'assigned':
                v_status = 'in_use'
            elif vehicle.status == 'maintenance':
                v_status = 'parking'
                
            lines.append((0, 0, {
                'vehicle_id': vehicle.id,
                'current_driver_status': 'available',
                'current_vehicle_status': v_status,
            }))
        res['line_ids'] = lines
        return res

    def action_confirm(self):
        self.ensure_one()
        for line in self.line_ids:
            # Record in history
            self.env['fleet.vehicle.history'].create({
                'vehicle_id': line.vehicle_id.id,
                'driver_status': line.current_driver_status,
                'vehicle_status': line.current_vehicle_status,
                'notes': line.notes,
            })
            # Update vehicle status
            new_status = 'available'
            if line.current_vehicle_status == 'parking':
                new_status = 'maintenance'
            elif line.current_vehicle_status == 'in_use':
                new_status = 'assigned'
            
            # Additional logic for driver availability
            if line.current_driver_status == 'not_available' and new_status == 'available':
                # Maybe a custom status for driver not available
                pass

            line.vehicle_id.write({'status': new_status})
        return {'type': 'ir.actions.act_window_close'}

class FleetCheckupWizardLine(models.TransientModel):
    _name = 'fleet.checkup.wizard.line'
    _description = 'Daily Vehicle Checkup Line'

    wizard_id = fields.Many2one('fleet.checkup.wizard', string='Wizard')
    vehicle_id = fields.Many2one('hagbes.fleet.vehicle', string='Vehicle', readonly=True)
    current_driver_status = fields.Selection([
        ('available', 'Available'),
        ('not_available', 'Not Available')
    ], string='Driver Status', default='available')
    current_vehicle_status = fields.Selection([
        ('idle', 'Idle'),
        ('parking', 'Parking (Maintenance)'),
        ('in_use', 'In Use')
    ], string='Vehicle Status', default='idle')
    notes = fields.Text(string='Notes')
