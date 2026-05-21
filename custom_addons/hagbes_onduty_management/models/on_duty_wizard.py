from odoo import models, fields, api
from odoo.exceptions import ValidationError

class OnDutyReportWizard(models.TransientModel):
    _name = 'onduty.report.wizard'
    _description = 'OnDuty Report Wizard'

    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        required=True,
        default=lambda self: self.env['hr.employee'].search([('user_id', '=', self.env.uid)], limit=1),
        domain="[('user_id', '=', uid)]"
    )
    department_id = fields.Many2one(related='employee_id.department_id', string='Department', readonly=True)
    company_id = fields.Many2one(related='employee_id.company_id', string='Company', readonly=True)
    job_id = fields.Many2one(related='employee_id.job_id', string='Job Position', readonly=True)

    # Branch -> analytic accounts (assumes you mark branch analytic accounts in some way)
    branch_id = fields.Many2one('account.analytic.account', string='Branch',
                                domain="[('plan_id.name', '=', 'Branch')]")  # adapt domain if needed

    # Sister company -> pick from companies
    sister_company = fields.Many2one('res.company', string='Sister Company')

    other_company = fields.Char(string='Other Place')

    start_date = fields.Datetime(string='Start Date', required=True)
    end_date = fields.Datetime(string='End Date', required=True)

    duty = fields.Text(string='Duty Description', required=True)
    remark = fields.Text(string='Remark (Optional)')
    attachment = fields.Binary(string='Attachment (Optional)')

    @api.constrains('start_date', 'end_date')
    def _check_dates(self):
        for rec in self:
            if rec.start_date and rec.end_date and rec.end_date < rec.start_date:
                raise ValidationError("End Date must be greater than or equal to Start Date.")

    def action_submit(self):
        """Create an actual onduty.report record from wizard and close the wizard."""
        self.ensure_one()
        if not (self.branch_id or self.sister_company or self.other_company):
            raise ValidationError("Please select Branch, Sister Company or Other Place.")
        vals = {
            'employee_id': self.employee_id.id,
            'department_id': self.department_id.id,
            'company_id': self.company_id.id,
            'job_id': self.job_id.id,
            # map wizard branch -> real model branch_id
            'branch_id': self.branch_id.id or False,
            'sister_company': self.sister_company.id or False,
            'other_company': self.other_company,
            'start_date': self.start_date,
            'end_date': self.end_date,
            'duty': self.duty,
            'remark': self.remark,
            'attachment': self.attachment,
            'state': 'pending',
        }
        created = self.env['onduty.report'].create(vals)
        # optional: open the newly created record after wizard closes
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'onduty.report',
            'res_id': created.id,
            'view_mode': 'form,tree',
            'target': 'current',
        }
