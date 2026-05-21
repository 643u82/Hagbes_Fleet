from odoo import models, fields, api


class HrEmployee(models.Model):
    _inherit = 'hr.employee'
    house_number = fields.Char(string="House Number")
    company_id = fields.Many2one(
        'res.company', string='Company',
        domain=lambda self: [('id', 'in', self._get_companies_from_jobs())],
    )

    branch_id = fields.Many2one(
        'account.analytic.account',
        string='Branch',
        domain="[('id', 'in', available_branch_ids)]"
    )

    department_id = fields.Many2one(
        'hr.department',
        string='Department',
        domain="[('id', 'in', available_department_ids)]"
    )

    job_id = fields.Many2one(
        'hr.job',
        string='Job Position',
        domain="[('id', 'in', available_job_ids)]"
    )

    # Compute available options for dynamic domains
    available_branch_ids = fields.Many2many(
        'account.analytic.account',
        compute='_compute_available_options'
    )
    available_department_ids = fields.Many2many(
        'hr.department',
        compute='_compute_available_options'
    )
    available_job_ids = fields.Many2many(
        'hr.job',
        compute='_compute_available_options'
    )

    @api.model
    def _get_companies_from_jobs(self):
        return list(set(self.env['hr.job'].search([]).mapped('company_id.id')))

    @api.depends('company_id', 'branch_id', 'department_id')
    def _compute_available_options(self):
        for record in self:
            # Initialize empty lists
            record.available_branch_ids = False
            record.available_department_ids = False
            record.available_job_ids = False

            # Filter branches by company
            if record.company_id:
                jobs = self.env['hr.job'].search([('company_id', '=', record.company_id.id)])
                record.available_branch_ids = jobs.mapped('analytic_account_id')

                # Filter departments by company and branch
                if record.branch_id:
                    jobs = jobs.filtered(lambda j: j.analytic_account_id == record.branch_id)
                    record.available_department_ids = jobs.mapped('department_id')

                    # Filter jobs by company, branch and department
                    if record.department_id:
                        record.available_job_ids = jobs.filtered(
                            lambda j: j.department_id == record.department_id
                        )
                    else:
                        record.available_job_ids = jobs
                else:
                    record.available_department_ids = jobs.mapped('department_id')
                    record.available_job_ids = jobs

    @api.onchange('company_id')
    def _onchange_company_id(self):
        self.branch_id = False
        self.department_id = False
        self.job_id = False

    @api.onchange('branch_id')
    def _onchange_branch_id(self):
        self.department_id = False
        self.job_id = False

    @api.onchange('department_id')
    def _onchange_department_id(self):
        self.job_id = False




    # Auto change branch in user when employee is created or updated

    @api.model
    def create(self, vals):
        employee = super().create(vals)
        employee._sync_branch_to_user()
        return employee

    def write(self, vals):
        res = super().write(vals)   

        if 'branch_id' in vals:
            self._sync_branch_to_user()

        return res

    def _sync_branch_to_user(self):
        for emp in self:
            if emp.user_id and emp.branch_id:
                emp.user_id.sudo().write({
                    'allowed_branch_ids': [(6, 0, [emp.branch_id.id])]
                })