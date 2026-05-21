# -*- coding: utf-8 -*-

from odoo import models, fields, _
from odoo.exceptions import UserError, ValidationError

class ApprovalIntegrationMixin(models.AbstractModel):
    _name = 'approval.integration.mixin'
    _description = 'Approval Integration Mixin'
    _inherit = []
    _abstract = True

    def _is_approval_module_installed(self):
        """
        Check if hagbes_approval_workflow is installed and present in the registry.
        """
        return 'approval.request' in self.env.registry

    def _is_approval_enabled(self):
        """
        Master toggle: Check if module is installed and enabled in settings.
        """
        if not self._is_approval_module_installed():
            return False
        return self._get_config_flag('fleet.approval.master_enabled', default=True)

    is_approval_disabled_or_missing = fields.Boolean(
        compute='_compute_is_approval_disabled_or_missing',
        string='Approval Disabled or Missing'
    )

    def _compute_is_approval_disabled_or_missing(self):
        for rec in self:
            rec.is_approval_disabled_or_missing = not rec._is_approval_enabled()

    def _requires_approval(self):
        """
        Should be implemented in inheriting models.
        Return True if approval is required for this record/action.
        """
        self.ensure_one()
        return False

    def _get_approval_request_vals(self):
        """
        Return dict of values for approval.request creation.
        Should be implemented in inheriting models.
        """
        self.ensure_one()
        return {}

    def _get_record_company(self):
        self.ensure_one()
        if 'company_id' in self._fields and self.company_id:
            return self.company_id
        return self.env.company

    def _get_config_flag(self, key, default=False):
        value = self.env['ir.config_parameter'].sudo().get_param(key, str(default))
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {'1', 'true', 'yes', 'on'}

    def _get_config_float(self, key, default=0.0):
        value = self.env['ir.config_parameter'].sudo().get_param(key, default)
        try:
            return float(value)
        except (TypeError, ValueError):
            return float(default)

    def _get_approval_flow(self, request_type):
        self.ensure_one()
        if not self._is_approval_module_installed():
            return None
        
        company = self._get_record_company()
        flow_domain = [
            ('request_type', '=', request_type),
            ('request_model_id.model', '=', self._name),
            ('active', '=', True),
        ]
        ApprovalFlow = self.env['approval.flow'].sudo()
        flow = ApprovalFlow.search(
            flow_domain + [('company_id', '=', company.id)],
            order='id desc',
            limit=1,
        )
        if not flow:
            flow = ApprovalFlow.search(
                flow_domain + [('company_id', '=', False)],
                order='id desc',
                limit=1,
            )
        if not flow:
            raise ValidationError(
                _('No active approval flow configured for %(model)s (%(request_type)s).') % {
                    'model': self._description or self._name,
                    'request_type': request_type,
                }
            )
        return flow

    def _prepare_approval_request_vals(self, vals):
        self.ensure_one()
        if not self._is_approval_module_installed():
            return vals
            
        ApprovalFlow = self.env['approval.flow'].sudo()
        flow = ApprovalFlow.browse(vals.get('flow_id'))
        if not flow.exists():
            raise ValidationError(_('The selected approval flow does not exist anymore.'))

        if not vals.get('current_step_id'):
            first_step = flow.step_ids.sorted(key=lambda step: step.sequence)[:1]
            if not first_step:
                raise ValidationError(_('No steps defined for approval flow %s.') % flow.display_name)
            vals['current_step_id'] = first_step.id

        vals.setdefault('requested_by', self.env.user.id)
        vals.setdefault('status', 'pending')
        return vals

    def _trigger_approval(self):
        """
        Generic approval trigger. Returns the request if created, or False if bypassed.
        Only allows auto-bypass for new requests (draft state).
        """
        self.ensure_one()
        if not self._is_approval_enabled():
            # Safety: If approval is disabled mid-process, only 'draft' records auto-pass.
            # Existing 'pending' records MUST be force-activated by an admin.
            can_bypass = False
            if 'state' in self._fields and self.state == 'draft':
                can_bypass = True
            elif 'disposal_state' in self._fields and self.disposal_state == 'none':
                can_bypass = True
            
            if can_bypass:
                self._on_approval_approved()
                return False
            else:
                # If already in pending/waiting_approval, do nothing (wait for Admin Force Action)
                return False

        ApprovalRequest = self.env['approval.request']
        approval_vals = self._get_approval_request_vals()
        if not approval_vals.get('flow_id'):
             # Fallback if flow selection is missing despite being enabled
             self._on_approval_approved()
             return False

        vals = self._prepare_approval_request_vals(approval_vals)
        # Prevent duplicate requests
        existing = ApprovalRequest.search([
            ('res_model', '=', self._name),
            ('res_id', '=', self.id),
            ('status', 'in', ['pending']),
        ], limit=1)
        if existing:
            raise UserError(_('Approval already requested and pending.'))
        
        request = ApprovalRequest.create(vals)
        self._set_waiting_approval_state()
        if request.current_step_id and request.current_step_id.is_initiator:
            request.process_action()
        return request

    def _set_waiting_approval_state(self):
        """
        Set state/status to waiting_approval. Should be implemented in inheriting models.
        """
        raise NotImplementedError('_set_waiting_approval_state must be implemented in the business model.')

    def _check_approval_status(self):
        """
        Check approval status for this record. Raise if not approved.
        """
        self.ensure_one()
        if not self._is_approval_enabled():
            return True

        ApprovalRequest = self.env.get('approval.request')
        if not ApprovalRequest:
            return True

        req = ApprovalRequest.search([
            ('res_model', '=', self._name),
            ('res_id', '=', self.id),
        ], order='id desc', limit=1)
        if req and req.status == 'approved':
            return True
        elif req and req.status == 'rejected':
            raise UserError(_('Approval was rejected.'))
        elif req:
            raise UserError(_('Approval is still pending.'))
        return False

    def _on_approval_approved(self):
        """
        Called by approval workflow when approved. Should be implemented in inheriting models.
        """
        raise NotImplementedError('_on_approval_approved must be implemented in the business model.')

    def _on_approval_rejected(self):
        """
        Called by approval workflow when rejected. Should be implemented in inheriting models.
        """
        raise NotImplementedError('_on_approval_rejected must be implemented in the business model.')
