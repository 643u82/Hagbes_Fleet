# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

from .approval_integration_mixin import ApprovalIntegrationMixin

class HagbesFleetVehicleAssign(models.Model, ApprovalIntegrationMixin):
    _name = 'hagbes.fleet.vehicle.assign'
    _description = 'Fleet Vehicle Assignment'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'approval.integration.mixin']
    _order = 'start_date desc, id desc'
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)

    vehicle_id = fields.Many2one('hagbes.fleet.vehicle', string='Vehicle', required=True, ondelete='restrict', index=True)
    employee_id = fields.Many2one('hr.employee', string='Employee', required=True, ondelete='restrict', index=True)
    start_date = fields.Date(string='Start Date', required=True, default=fields.Date.today, index=True)
    end_date = fields.Date(string='End Date', index=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('pending', 'Pending Approval'),
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('rejected', 'Rejected'),
    ], string='State', default='draft', tracking=True, index=True)
    notes = fields.Text(string='Notes')

    _sql_constraints = [
        ('no_overlap', 'CHECK(1=1)', 'Overlapping assignments are not allowed.'),
    ]

    @api.constrains('start_date', 'end_date')
    def _check_date_range(self):
        for rec in self:
            if rec.end_date and rec.end_date < rec.start_date:
                raise ValidationError(_('End date cannot be earlier than start date.'))

    @api.constrains('vehicle_id', 'start_date', 'end_date', 'state')
    def _check_no_overlap(self):
        for rec in self:
            if rec.state in ['draft', 'rejected', 'completed']:
                continue
            domain = [
                ('vehicle_id', '=', rec.vehicle_id.id),
                ('id', '!=', rec.id),
                ('state', 'in', ['pending', 'active']),
                ('start_date', '<=', rec.end_date or rec.start_date),
                '|',
                ('end_date', '=', False),
                ('end_date', '>=', rec.start_date),
            ]
            overlap = self.search(domain, limit=1)
            if overlap:
                raise ValidationError(_('This vehicle is already assigned for the selected period.'))


    def action_submit(self):
        for rec in self:
            if not rec._requires_approval():
                rec._on_approval_approved()
                continue
            rec._trigger_approval()

    def _requires_approval(self):
        self.ensure_one()
        return self._get_config_flag('fleet.approval.enable_assignment', default=True)

    def _get_approval_request_vals(self):
        flow = self._get_approval_flow('fleet_assignment')
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
            raise UserError(_("Only pending assignments can be force activated."))
        if self._is_approval_enabled():
            raise UserError(_("Cannot force activate while the approval system is active. Please use the standard approval workflow."))
        
        if not self.env.user.has_group('hagbes_fleet.group_fleet_admin'):
            raise UserError(_("Only a Fleet Admin can perform this action."))

        self.message_post(body=_("Record force activated by administrator bypassing approval workflow."), 
                         message_type='notification', subtype_xmlid='mail.mt_note')
        self._on_approval_approved()
