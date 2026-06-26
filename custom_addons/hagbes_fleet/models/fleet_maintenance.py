# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

from .approval_integration_mixin import ApprovalIntegrationMixin

class HagbesFleetMaintenance(models.Model):
    _name = 'hagbes.fleet.maintenance'
    _description = 'Fleet Maintenance'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'approval.integration.mixin']
    _order = 'service_date desc, id desc'
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)

    vehicle_id = fields.Many2one('hagbes.fleet.vehicle', string='Vehicle', required=True, ondelete='restrict', index=True)
    service_type = fields.Selection([
        ('preventive', 'Preventive'),
        ('corrective', 'Corrective'),
    ], string='Service Type', required=True, index=True)
    service_date = fields.Date(string='Service Date', required=True, index=True)
    cost = fields.Float(string='Cost', required=True)
    product_id = fields.Many2one('product.product', string='Spare Part', ondelete='set null', index=True)
    description = fields.Text(string='Description')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('pending', 'Pending Approval'),
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('rejected', 'Rejected'),
    ], string='State', default='draft', tracking=True, index=True)

    @api.model_create_multi
    def create(self, vals_list):
        return super().create(vals_list)


    def action_submit(self):
        for rec in self:
            if not rec._requires_approval():
                rec._on_approval_approved()
                continue
            rec._trigger_approval()

    def _requires_approval(self):
        self.ensure_one()
        threshold = self._get_config_float('fleet.approval.maintenance_threshold', default=10000.0)
        return self.cost > threshold

    def _get_approval_request_vals(self):
        flow = self._get_approval_flow('fleet_maintenance')
        return {
            'res_model': self._name,
            'res_id': self.id,
            'requested_by': self.env.user.id,
            'flow_id': flow.id if flow else False,
            'module_name': 'hagbes_fleet',
        }

    def _set_waiting_approval_state(self):
        self.state = 'pending'

    def _on_approval_approved(self):
        self.state = 'active'

    def _on_approval_rejected(self):
        self.state = 'rejected'

    def action_approve(self):
        for rec in self:
            rec.state = 'active'

    def action_complete(self):
        for rec in self:
            rec.state = 'completed'

    def action_reject(self):
        for rec in self:
            rec.state = 'rejected'

    def action_force_activate(self):
        """
        Emergency bypass for orphaned workflows.
        Available only if approval system is disabled or missing.
        """
        self.ensure_one()
        if self.state != 'pending':
            raise UserError(_("Only pending maintenance can be force activated."))
        if self._is_approval_enabled():
            raise UserError(_("Cannot force activate while the approval system is active. Please use the standard approval workflow."))
        
        if not self.env.user.has_group('hagbes_fleet.group_fleet_admin'):
            raise UserError(_("Only a Fleet Admin can perform this action."))

        self.message_post(body=_("Record force activated by administrator bypassing approval workflow."), 
                         message_type='notification', subtype_xmlid='mail.mt_note')
        self._on_approval_approved()
