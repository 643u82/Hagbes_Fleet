# -*- coding: utf-8 -*-
"""
Fleet Requisition Rejection Wizard

This wizard provides a secure interface for Department Managers to reject
fleet requisitions with mandatory reason tracking and proper audit trails.
"""

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


class FleetRequisitionRejectWizard(models.TransientModel):
    """Wizard for rejecting fleet requisitions with mandatory reason."""
    
    _name = 'fleet.requisition.reject.wizard'
    _description = 'Fleet Requisition Rejection Wizard'

    # ─── Fields ─────────────────────────────────────────────────────────────
    requisition_id = fields.Many2one(
        'fleet.requisition',
        string='Requisition',
        required=True,
        readonly=True,
        ondelete='cascade',
    )
    reason = fields.Text(
        string='Rejection Reason',
        required=True,
        help='Please provide a detailed reason for rejecting this requisition.',
    )
    current_state = fields.Selection(
        related='requisition_id.state',
        string='Current State',
        readonly=True,
    )
    request_by = fields.Many2one(
        related='requisition_id.request_by',
        string='Requested By',
        readonly=True,
    )

    # ─── Default Methods ─────────────────────────────────────────────────────
    @api.model
    def default_get(self, fields_list):
        """Set default requisition_id from context."""
        defaults = super().default_get(fields_list)
        
        if 'requisition_id' in fields_list and not defaults.get('requisition_id'):
            context = self.env.context
            if context.get('active_model') == 'fleet.requisition' and context.get('active_id'):
                defaults['requisition_id'] = context['active_id']
        
        return defaults

    # ─── Constraints ─────────────────────────────────────────────────────────
    @api.constrains('reason')
    def _check_reason(self):
        """Validate rejection reason is meaningful."""
        for wizard in self:
            if wizard.reason and len(wizard.reason.strip()) < 10:
                raise ValidationError(
                    _('Please provide a more detailed rejection reason (minimum 10 characters).')
                )

    # ─── Business Logic ─────────────────────────────────────────────────────
    def action_confirm_reject(self):
        """Process the rejection with proper security validation."""
        self.ensure_one()
        
        # Security validation - only Department Managers can reject
        if not self.env.user.has_group('hagbes_fleet.group_dept_manager') and \
           not self.env.user.has_group('hagbes_fleet.group_fleet_admin') and \
           not self.env.user.has_group('base.group_system'):
            raise AccessError(_('Only Department Managers can reject requisitions.'))
        
        # Validate requisition state
        if self.requisition_id.state != 'submitted':
            raise ValidationError(_('Only submitted requisitions can be rejected.'))
        
        # Validate reason is provided
        if not self.reason or not self.reason.strip():
            raise ValidationError(_('Rejection reason is required.'))
        
        # Process rejection
        self.requisition_id.action_department_reject(self.reason.strip())
        
        # Return to requisition form
        return {
            'type': 'ir.actions.act_window',
            'name': _('Rejected Requisition'),
            'res_model': 'fleet.requisition',
            'res_id': self.requisition_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_cancel(self):
        """Cancel the rejection wizard."""
        return {'type': 'ir.actions.act_window_close'}

    # ─── Security Methods ───────────────────────────────────────────────────
    def check_access_rights(self, operation):
        """Override to enforce Department Manager access."""
        if operation in ('write', 'unlink', 'create'):
            if not self.env.user.has_group('hagbes_fleet.group_dept_manager') and \
               not self.env.user.has_group('hagbes_fleet.group_fleet_admin') and \
               not self.env.user.has_group('base.group_system'):
                raise AccessError(_('Only Department Managers can access rejection wizard.'))
        return super().check_access_rights(operation)

    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        """Restrict wizard access to Department Managers only."""
        if not self.env.user.has_group('hagbes_fleet.group_dept_manager') and \
           not self.env.user.has_group('hagbes_fleet.group_fleet_admin') and \
           not self.env.user.has_group('base.group_system'):
            raise AccessError(_('Only Department Managers can access rejection wizard.'))
        return super().fields_view_get(view_id, view_type, toolbar, submenu)
