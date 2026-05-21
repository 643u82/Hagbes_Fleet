from odoo import models, fields, api, _
from odoo.exceptions import UserError
class ResignationAcceptance(models.Model):
    _name = 'employee.resignation.acceptance'
    _description = 'Resignation Acceptance Letter'

    req_type = fields.Selection([
        ('resignation','Resignation'),
        ('retirement','Retirement'),
        ('discipline','Disciplinary Action')
    ], string="Request Type", default='resignation')

    name = fields.Char(string="Reference", required=True, default='New', readonly=True, copy=False)
    ref = fields.Char(string="Reference", help="Reference number for the other request type")

    employee_id = fields.Many2one('hr.employee', string="Employee", readonly=True)
    
    branch_id = fields.Many2one(
        'account.analytic.account',
        string='Branch',
        domain="[('id', 'in', available_branch_ids)]",
        default=lambda self: self.env.user.employee_id.branch_id if self.env.user.employee_id else False
    )
    acceptance_date = fields.Date(string="Acceptance Date", default=fields.Date.today, required=True)
    comments = fields.Text(string="HR Comments")

    cc_user_ids = fields.Many2many('res.users', string='CC')

    state = fields.Selection([
        ('draft', 'Draft'),
        ('approved', 'Approved'),
        ('to_terminate', 'To Terminate'),
        ('rejected', 'Rejected'),
        ('pending', 'Pending')
    ], default='draft')
    approval_request_id = fields.Many2one('approval.request', string="Approval Request", readonly=True)
    step_progress = fields.Html(string="Approval Progress", compute='_compute_step_progress')
    company_id = fields.Many2one(
    'res.company', string='Company',
    default=lambda self: self.env.company
    )          
    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('employee.resignation.acceptance') or 'AL-XX-00000'
            # vals['ref'] = vals['name']
            vals['req_type'] = vals.get('req_type', 'resignation')

            # Safely assign employee_id
            if not vals.get('employee_id'):
                if self.env.user.employee_id:
                    vals['employee_id'] = self.env.user.employee_id.id
                else:
                    raise ValueError("No employee is linked to the current user and no employee_id was provided.")

            # Convert cc_user_ids to M2M command
            if 'cc_user_ids' in vals and isinstance(vals['cc_user_ids'], list):
                vals['cc_user_ids'] = [(6, 0, vals['cc_user_ids'])]

        return super().create(vals)
    def action_submit(self):
        self.ensure_one()

        if self.state == 'submitted' and self.approval_request_id:
            raise UserError("This record has already been submitted for approval.")

        flow = self.env['approval.flow'].search([
            ('request_model_id.model', '=', 'employee.resignation.acceptance'),
            ('active', '=', True),
            ('company_id', '=', self.company_id.id)
        ], limit=1)
        if not flow:
            raise UserError("No approval flow defined for Acceptance!")

        first_step = self.env['approval.step'].search([
            ('flow_id', '=', flow.id)
        ], order='sequence asc', limit=1)
        if not first_step:
            raise UserError("No steps defined for this approval flow.")

        approval_req = self.env['approval.request'].create({
            'flow_id': flow.id,
            'res_model': self._name,
            'module_name': 'hr',
            'res_id': self.id,
            'current_step_id': first_step.id,
            'status': 'pending',
        })

        self.write({
            'state': 'pending',
            'approval_request_id': approval_req.id
        })

        approval_req.process_action()
        self._sync_state_from_approval()
    def action_approve(self, comment=''):
        self.ensure_one()
        if not self.approval_request_id:
            raise UserError("No approval request linked to this Resignation.")
        self.approval_request_id.with_context(action_type='approve', comment=comment).process_action()
        self._sync_state_from_approval()

    def action_reject(self, comment=''):
        self.ensure_one()
        if not self.approval_request_id:
            raise UserError("No approval request linked to this Resignation.")
        self.approval_request_id.with_context(action_type='reject', comment=comment).process_action()
        self._sync_state_from_approval()
    def _sync_state_from_approval(self):
        if not self.approval_request_id:
            return
        status = self.approval_request_id.status
        if status == 'approved':
            self.state = 'approved'
            # self.create_acceptance_letter(self.approval_request_id)
            # insert into ternination leter table
        elif status == 'rejected':
            self.state = 'rejected'
        elif status == 'pending':
            self.state = 'pending'
        else:
            self.state = 'draft'
    def _compute_step_progress(self):
        for rec in self:
            rec.step_progress = rec.approval_request_id.step_progress if rec.approval_request_id else "<span>No approval steps yet.</span>"

    # def _compute_cc_users(self):
    #     role_map = {
    #         'User': ['Managing Director', 'Finance Director', 'Payroll', 'Property Manager', 'IT Manager'],
    #         'Supervisor': ['Managing Director', 'Finance Director', 'Payroll', 'Property Manager', 'IT Manager'],
    #         'Department Manager': ['Managing Director', 'Finance Director', 'Payroll', 'Property Manager', 'IT Manager', 'General Manager'],
    #         'General Manager': ['Managing Director', 'Finance Director', 'Payroll', 'Property Manager', 'IT Manager', 'Director'],
    #         'Director': ['Managing Director', 'Finance Director', 'Payroll', 'Property Manager', 'IT Manager', 'Owner'],
    #     }

    #     for rec in self:
    #         job = rec.employee_id.job_id
    #         job_name = job.name if job else False

    #         # Default role = User
    #         role = 'User'
    #         if job_name in ['Supervisor', 'Department Manager', 'General Manager', 'Director']:
    #             role = job_name

    #         # Base CC roles
    #         cc_job_titles = role_map.get(role, [])

    #         # 🔹 Add Department Manager dynamically for User/Supervisor
    #         if role in ['User', 'Supervisor'] and job and job.parent_id:
    #             cc_job_titles.append(job.parent_id.name)

    #         # Fetch employees with these jobs
    #         cc_employees = self.env['hr.employee'].search([
    #             ('job_id.name', 'in', cc_job_titles)
    #         ])

    #         # Assign their linked users
    #         rec.cc_user_ids = cc_employees.mapped('user_id')



    # def action_load_cc_users(self):
    #     for record in self:
    #         record._compute_cc_users()
    #     return True


    @api.model
    def _find_department_manager(self, employee):
        """Find the Department Manager only in the employee's job hierarchy"""
        parent_job = employee.job_id.parent_id
        while parent_job:
            users = self.env['res.users'].search([
                ('employee_ids.job_id','=', parent_job.id),
                ('groups_id.name','=','Department Manager'),
                ('groups_id.category_id','=', 103)
            ])
            if users:
                return users
            parent_job = parent_job.parent_id
        return self.env['res.users']  # empty if none found

    @api.depends('employee_id')
    def _compute_cc_users(self):
        role_map = {
            'User': ['Managing Director', 'Finance Manager', 'Payroll', 'Property Manager', 'IT Manager', 'Department Manager'],
            'Supervisor': ['Managing Director', 'Finance Manager', 'Payroll', 'Property Manager', 'IT Manager', 'Department Manager'],
            'Department Manager': ['Managing Director', 'Finance Manager', 'Payroll', 'Property Manager', 'IT Manager', 'General Manager'],
            'General Manager': ['Managing Director', 'Finance Manager', 'Payroll', 'Property Manager', 'IT Manager', 'Director'],
            'Director': ['Managing Director', 'Finance Manager', 'Payroll', 'Property Manager', 'IT Manager', 'Owner'],
        }

        for record in self:
            if not record.employee_id:
                continue

            # Determine the employee role using groups
            employee_groups = record.employee_id.user_id.groups_id.filtered(lambda g: g.category_id.id == 103)
            employee_role = employee_groups.mapped('name')[0] if employee_groups else 'User'

            # Collect CC users based on role_map
            cc_users = self.env['res.users']
            for role_name in role_map.get(employee_role, []):
                users = self.env['res.users'].search([
                    ('groups_id.name','=', role_name),
                    ('groups_id.category_id','=', 103)
                ])
                cc_users |= users

            # Add Department Manager from employee hierarchy
            dm_users = self._find_department_manager(record.employee_id)
            cc_users |= dm_users

            # Assign to the field
            record.cc_user_ids = cc_users

    def action_load_cc_users(self):
        """Button to compute and fill CC users"""
        self._compute_cc_users()
    def action_to_terminate(self):
        for record in self:
            if record.state == 'approved':
                # 1. Change state
                record.state = 'to_terminate'

                # 2. Create record in employee.termination
                record.env['employee.termination'].create({
                    'employee_id': record.employee_id.id,
                    'termination_date': fields.Date.today(),
                    # 'reason': 'Auto termination after approval',  # or record.reason if exists
                    'termination_type': 'shelf',
                })