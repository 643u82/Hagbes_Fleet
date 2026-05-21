from odoo import models, fields

class HrJobOrgChart(models.Model):
    _name = 'hr.job.org.chart'
    _description = 'HR Job Org Chart View'
    _auto = False  # Important: This model uses a DB view

    id = fields.Integer(string='ID', readonly=True)
    job_id = fields.Many2one('hr.job', string='Job Position', readonly=True)
    job_name = fields.Char(string='Job Name', readonly=True)
    parent_job_id = fields.Many2one('hr.job', string='Parent Job', readonly=True)
    company_id = fields.Many2one('res.company', string='Company', readonly=True)
    department_id = fields.Many2one('hr.department', string='Department', readonly=True)
    branch_id = fields.Many2one('account.analytic.account', string='Branch', readonly=True)
    expected_employees = fields.Integer(string='Expected Employees', readonly=True)
    no_of_employee = fields.Integer(string='Current Employees', readonly=True)

    def init(self):
        """Override to create or replace view at module installation."""
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW hr_job_org_chart AS (
                SELECT
                    job.id AS id,
                    job.id AS job_id,
                    job.name AS job_name,
                    job.parent_id AS parent_job_id,
                    job.company_id AS company_id,
                    job.department_id AS department_id,
                    job.analytic_account_id AS branch_id,
                    job.expected_employees,
                    (SELECT COUNT(*) FROM hr_employee emp WHERE emp.job_id = job.id AND emp.active = TRUE) AS no_of_employee
                FROM
                    hr_job job
            )
        """)
