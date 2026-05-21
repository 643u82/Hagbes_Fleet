from odoo import models, api
from odoo.exceptions import ValidationError

class OnDutyApproval(models.Model):
    _inherit = 'onduty.report'
    _name = 'onduty.approval'
    _description = 'OnDuty Approval'

    def action_approve_dept_manager(self):
        for rec in self:
            if rec.state != 'pending_dept_manager':
                raise ValidationError("Only pending department manager approvals can be approved.")
            # Approve by dept manager and move to HR approval state
            rec.state = 'pending_hr'

    def action_reject_dept_manager(self):
        for rec in self:
            if rec.state != 'pending_dept_manager':
                raise ValidationError("Only pending department manager approvals can be rejected.")
            rec.state = 'rejected_dept_manager'

    def action_approve_hr(self):
        for rec in self:
            if rec.state != 'pending_hr':
                raise ValidationError("Only pending HR approvals can be approved.")
            rec.state = 'approved_hr'

    def action_reject_hr(self):
        for rec in self:
            if rec.state != 'pending_hr':
                raise ValidationError("Only pending HR approvals can be rejected.")
            rec.state = 'rejected_hr'

    @api.model
    def _get_domain_for_dept_manager(self):
        current_employee = self.env['hr.employee'].search([('user_id', '=', self.env.uid)], limit=1)
        if not current_employee:
            # No access to any records if no employee linked to current user
            return [('id', '=', 0)]
        # Show only records of employees in current manager's department pending dept manager approval
        return [
            ('department_id', '=', current_employee.department_id.id),
            ('state', '=', 'pending_dept_manager')
        ]

    @api.model
    def _get_domain_for_hr_manager(self):
        # HR managers see all records pending HR approval
        return [('state', '=', 'pending_hr')]
