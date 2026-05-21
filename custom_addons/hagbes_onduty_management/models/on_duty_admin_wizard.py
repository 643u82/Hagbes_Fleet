from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import logging

_logger = logging.getLogger(__name__)

class OnDutyAdminWizard(models.TransientModel):
    _name = 'onduty.admin.wizard'
    _description = 'Admin OnDuty Report Wizard'

    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        required=True,
        domain=lambda self: self._get_employee_domain()
    )
    department_id = fields.Many2one(related='employee_id.department_id', string='Department', readonly=True, store=True)
    company_id = fields.Many2one(related='employee_id.company_id', string='Company', readonly=True, store=True)
    job_id = fields.Many2one(related='employee_id.job_id', string='Job Position', readonly=True, store=True)
    branch_id = fields.Many2one(
        related='employee_id.job_id.analytic_account_id',
        string='Branch',
        readonly=True,
        store=True
    )
    branch_company = fields.Many2one('account.analytic.account', string='Duty Branch')
    sister_company = fields.Many2one('res.company', string='Sister Company')
    other_company = fields.Char(string='Other Place')
    start_date = fields.Datetime(string='Start Date', required=True)
    end_date = fields.Datetime(string='End Date', required=True)
    duty = fields.Text(string='Duty Description', required=True)
    remark = fields.Text(string='Remark (Optional)', tracking=True)
    attachment = fields.Binary(string='Attachment (Optional)')

    admin_request_id = fields.Many2one('res.users', string='Admin Requester', readonly=True)
    def _get_employee_domain(self):
        """Return all employees if the user is HR/Admin, else employees in the same branch excluding self."""
        user = self.env.user
        logged_emp = user.employee_id

        # Check if the user is admin/HR (you can adjust the group)
        if user.has_group('base.group_system'):
            return []  # No domain restriction → show all employees

        # If user has no linked employee, return empty
        if not logged_emp:
            return []

        # Restrict to same branch and exclude self
        return [
            ('branch_id', '=', logged_emp.branch_id.id),
            ('id', '!=', logged_emp.id)
        ]

    def action_submit(self):
        admin_user = self.env.user
        OnDuty = self.env['onduty.report']
        for wizard in self:
            if not wizard.employee_id:
                raise ValidationError("Please select an employee.")
        # Prepare values for OnDutyReport
        vals = {
            'employee_id': wizard.employee_id.id,
            'branch_company': wizard.branch_company.id,
            'sister_company': wizard.sister_company.id,
            'other_company': wizard.other_company,
            'start_date': wizard.start_date,
            'end_date': wizard.end_date,
            'duty': wizard.duty,
            'remark': 'OnDuty requested by Others',
            'attachment': wizard.attachment,
            'admin_request_id': admin_user.id,   # audit
            'user_id': wizard.employee_id.user_id.id or False,

        }

        # Create the OnDutyReport as admin for auditing
        onduty = OnDuty.sudo().create(vals)

        # Submit workflow as the employee (so approval goes to approvers of employee)
        onduty = onduty.with_user(onduty.user_id)
        onduty.action_submit()

        # Post attachments as employee
        if self.attachment:
            onduty.message_post(attachment_ids=[self.attachment.id] if isinstance(self.attachment, int) else [])
        return self._open_success_message_wizard("OnDuty Request created successfully!")

    def _open_success_message_wizard(self, message):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Success',
            'res_model': 'success.message.wizard',
            'view_mode': 'form',
            'view_id': self.env.ref('hagbes_onduty_management.view_success_message_wizard_form_onduty').id,
            'target': 'new',
            'context': {'default_message': message},
        }
