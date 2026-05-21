# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

from .approval_integration_mixin import ApprovalIntegrationMixin

class HagbesFleetVehicle(models.Model, ApprovalIntegrationMixin):
    _name = 'hagbes.fleet.vehicle'
    _description = 'Fleet Vehicle'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'approval.integration.mixin']
    _order = 'acquisition_date desc, id desc'
    _rec_names_search = ['name', 'plate_number', 'driver']
    _sql_constraints = [
        ('plate_number_unique', 'unique(plate_number)', 'Plate number must be unique!'),
        ('engine_number_unique', 'unique(engine_number)', 'Engine number must be unique!'),
        ('chassis_number_unique', 'unique(chassis_number)', 'Chassis number must be unique!'),
    ]
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)

    name = fields.Char(string='Vehicle Name', required=True, index=True)
    plate_number = fields.Char(string='Plate Number', required=True, index=True)
    model = fields.Char(string='Model', required=True, index=True)
    brand = fields.Char(string='Brand', required=True, index=True)
    year = fields.Char(string='Year', index=True)
    engine_number = fields.Char(string='Engine Number', required=True, index=True)
    chassis_number = fields.Char(string='Chassis Number', required=True, index=True)
    fuel_type = fields.Selection([
        ('petrol', 'Petrol'),
        ('diesel', 'Diesel'),
        ('electric', 'Electric'),
        ('hybrid', 'Hybrid'),
    ], string='Fuel Type', required=True)
    acquisition_date = fields.Date(string='Acquisition Date', required=True, index=True)
    cost = fields.Float(string='Acquisition Cost')
    status = fields.Selection([
        ('available', 'Available'),
        ('assigned', 'Assigned'),
        ('maintenance', 'Maintenance'),
        ('waiting_approval', 'Waiting Approval'),
        ('out_of_service', 'Out of Service'),
    ], string='Status', compute='_compute_status', store=True, tracking=True, index=True)
    disposal_state = fields.Selection([
        ('none', 'None'),
        ('waiting_approval', 'Waiting Approval'),
        ('out_of_service', 'Out of Service'),
    ], string='Disposal State', default='none', copy=False, tracking=True, index=True)
    driver = fields.Char(string='Driver Name', index=True)
    gps = fields.Selection([('Yes', 'Yes'), ('No', 'No')], string='Has GPS?', default='No')
    kmperl = fields.Float(string='Fuel Consumption (KM/L)', default=10.0)
    vehicle_type = fields.Selection([
        ('work', 'Work Vehicle'),
        ('managerial', 'Managerial Vehicle'),
    ], string='Vehicle Type', default='work')

    assignment_ids = fields.One2many('hagbes.fleet.vehicle.assign', 'vehicle_id', string='Assignments')
    maintenance_ids = fields.One2many('hagbes.fleet.maintenance', 'vehicle_id', string='Maintenance Records')
    history_ids = fields.One2many('fleet.vehicle.history', 'vehicle_id', string='Status History')
    allocation_ids = fields.One2many('hagbes.fleet.allocation', 'vehicle_id', string='Allocations')
    status_log_ids = fields.One2many('hagbes.fleet.vehicle.status.log', 'vehicle_id', string='Status Logs')

    @api.depends('name', 'plate_number', 'driver')
    def _compute_display_name(self):
        for rec in self:
            label = rec.name or ''
            if rec.plate_number:
                label = f"{rec.plate_number} - {label}" if label else rec.plate_number
            if rec.driver:
                label = f"{label} ({rec.driver})" if label else rec.driver
            rec.display_name = label

    @api.depends('assignment_ids.state', 'maintenance_ids.state', 'disposal_state', 'allocation_ids.state')
    def _compute_status(self):
        for rec in self:
            if rec.disposal_state == 'out_of_service':
                rec.status = 'out_of_service'
            elif rec.disposal_state == 'waiting_approval':
                rec.status = 'waiting_approval'
            elif any(m.state == 'active' for m in rec.maintenance_ids):
                rec.status = 'maintenance'
            elif any(a.state in ('assigned', 'dispatched', 'in_progress') for a in rec.allocation_ids):
                rec.status = 'assigned'
            elif any(a.state == 'active' for a in rec.assignment_ids):
                rec.status = 'assigned'
            else:
                rec.status = 'available'

    @api.model_create_multi
    def create(self, vals_list):
        return super().create(vals_list)

    def action_request_disposal(self):
        for rec in self:
            if rec.disposal_state in ('waiting_approval', 'out_of_service'):
                continue
            if rec._requires_approval():
                rec._trigger_approval()
            else:
                rec._on_approval_approved()
        return True

    def _requires_approval(self):
        self.ensure_one()
        return self._get_config_flag('fleet.approval.enable_disposal', default=True)

    def _get_approval_request_vals(self):
        flow = self._get_approval_flow('fleet_disposal')
        return {
            'res_model': self._name,
            'res_id': self.id,
            'requested_by': self.env.user.id,
            'flow_id': flow.id if flow else False,
            'module_name': 'hagbes_fleet',
        }

    def _set_waiting_approval_state(self):
        self.disposal_state = 'waiting_approval'

    def _on_approval_approved(self):
        self.disposal_state = 'out_of_service'

    def _on_approval_rejected(self):
        self.disposal_state = 'none'

    def action_force_disposal(self):
        """
        Emergency bypass for orphaned disposal workflows.
        Available only if approval system is disabled or missing.
        """
        self.ensure_one()
        if self.disposal_state != 'waiting_approval':
            raise UserError(_("Only vehicles waiting for disposal approval can be force retired."))
        if self._is_approval_enabled():
            raise UserError(_("Cannot force disposal while the approval system is active. Please use the standard approval workflow."))
        
        if not self.env.user.has_group('hagbes_fleet.group_fleet_admin'):
            raise UserError(_("Only a Fleet Admin can perform this action."))

        self.message_post(body=_("Vehicle force disposal authorized by administrator bypassing approval workflow."), 
                         message_type='notification', subtype_xmlid='mail.mt_note')
        self._on_approval_approved()
