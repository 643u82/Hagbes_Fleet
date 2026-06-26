from odoo import models, fields


class ApprovalRequest(models.Model):
    _inherit = 'approval.request'

    def write(self, vals):
        res = super(ApprovalRequest, self).write(vals)
        if 'current_step_id' in vals or 'status' in vals:
            for rec in self:
                if rec.res_model == 'fleet.requisition':
                    rec._sync_fleet_requisition_state()
        return res

    def _sync_fleet_requisition_state(self):
        """Sync fleet.requisition.state based on the current approval step.

        The requisition model only allows these states:
        draft, submitted, dept_approved, assigned, dispatched, completed,
        rejected, cancelled.

        This method only writes valid values and avoids the legacy invalid
        states that caused selection errors.
        """
        self.ensure_one()
        target = self.env['fleet.requisition'].sudo().browse(self.res_id)
        if not target.exists():
            return

        selection_field = target._fields.get('state')
        allowed_states = set()
        if selection_field and getattr(selection_field, 'selection', None):
            allowed_states = {key for key, _label in selection_field.selection}

        def safe_write_state(state_value, extra_vals=None):
            if not selection_field:
                return
            if allowed_states and state_value not in allowed_states:
                return
            vals = dict(extra_vals or {})
            vals['state'] = state_value
            target.with_context(allow_workflow=True).write(vals)

        step = self.current_step_id
        if not step:
            return

        dept_step = self.env.ref('hagbes_fleet.approval_step_fleet_requisition_dept_manager', raise_if_not_found=False)
        fmo_step = self.env.ref('hagbes_fleet.approval_step_fleet_requisition_fmo_officer', raise_if_not_found=False)
        final_step = self.env.ref('hagbes_fleet.approval_step_fleet_requisition_final', raise_if_not_found=False)

        if self.status != 'approved':
            return

        # approval.request stores the actor in env.user (not self.user_id)
        actor = self.env.user

        if dept_step and step == dept_step:
            safe_write_state('submitted', {
                'approved_by': actor.id,
                'approved_date': fields.Datetime.now(),
                'is_dept_manager_approved': True,
            })
        elif fmo_step and step == fmo_step:
            safe_write_state('assigned', {
                'assigned_by': actor.id,
                'assigned_date': fields.Datetime.now(),
            })
        elif final_step and step == final_step:
            safe_write_state('approved', {
                'approved_by': actor.id,
                'approved_date': fields.Datetime.now(),
            })

