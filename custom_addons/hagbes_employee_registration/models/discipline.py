import logging
from odoo import models, fields, api
from odoo.exceptions import UserError , ValidationError

_logger = logging.getLogger(__name__)

class EmployeeDisciplinaryAction(models.Model):
    _name = 'employee.discipline'
    _description = 'Employee Disciplinary Action'
    _order = 'date desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    remark_ids = fields.One2many(
        'approval.remark.wizard',
        'res_id',
        string='Remarks',
        compute='_compute_remarks', 
        store =True,
        tracking=True
    )
    action_type = fields.Selection([
                    ('approve', 'Approved'),
                    ('reject', 'Rejected'),
                    ('pass_to_legal', 'Passed to Legal'),
                ], string='Action')

    
    approval_remark = fields.Text(string='Approval Remark', readonly=True)
    approved_by_job_id = fields.Many2one('hr.job', string='Approved By Job', readonly=True)
    approval_request_id = fields.Many2one(
    'approval.request',
    string="Approval Request"
    )
    can_approve = fields.Boolean( string="Can Approve", compute="_compute_can_approve", store=False )
    name = fields.Char(
        string="Reference", 
        default='New', 
        required=True, 
        copy=False, 
        readonly=True
    )
    employee_id = fields.Many2one(
        'hr.employee', 
        string="Employee",
        required=True,
        domain="[('id', 'in', available_employee_ids)]",
    )
    branch_id = fields.Many2one(
        'account.analytic.account',
        string='Branch',
        domain="[('id', 'in', available_branch_ids)]",
        default=lambda self: self.env.user.employee_id.branch_id if self.env.user.employee_id else False
    )
    department_id = fields.Many2one(
        'hr.department',
        string='Department',
        domain="[('id', 'in', available_department_ids)]",
        default=lambda self: self.env.user.employee_id.department_id if self.env.user.employee_id else False
    )
    job_id = fields.Many2one(
        'hr.job',
        string='Job Position',
        domain="[('id', 'in', available_job_ids)]"
    )
    date = fields.Date(
         string="Date", 
         required=True, 
         default=fields.Date.today
    )
    company_id = fields.Many2one(
        'res.company', string='Company',
        default=lambda self: self.env.user.employee_id.company_id.id or self.env.company.id,
        domain=lambda self: [('id', 'in', self._get_companies_from_jobs())],
    )
    
    # -----------------------
    # Helper fields for dynamic options
    # -----------------------
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

    available_employee_ids = fields.Many2many(
        'hr.employee',
        compute="_compute_available_options"
    )


    description = fields.Text(string="Discipline")
    action_type = fields.Selection([
        ('warning', 'Warning'),
        ('suspension', 'Suspension'),
        ('termination', 'Termination'),
    ], string="Action Type", required=False)
    reason = fields.Text(string="Reason")
    state = fields.Selection([
        ('draft', 'Draft'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('pending', 'Pending'),
    ], default='draft', string="Status", tracking=True)
    step_progress = fields.Html(string="Approval Progress", compute='_compute_step_progress')

    @api.model
    def _get_companies_from_jobs(self):
        return list(set(self.env['hr.job'].search([]).mapped('company_id.id')))
    
    @api.depends('company_id', 'branch_id', 'department_id', 'job_id')
    def _compute_available_options(self):
        for record in self:
            # initialize empty recordsets
            record.available_branch_ids = self.env['account.analytic.account']
            record.available_department_ids = self.env['hr.department']
            record.available_job_ids = self.env['hr.job']
            record.available_employee_ids = self.env['hr.employee']

            if record.company_id:
                jobs = self.env['hr.job'].search([('company_id', '=', record.company_id.id)])
                record.available_branch_ids = jobs.mapped('analytic_account_id')

                if record.branch_id:
                    jobs = jobs.filtered(lambda j: j.analytic_account_id == record.branch_id)
                    record.available_department_ids = jobs.mapped('department_id')

                    if record.department_id:
                        jobs = jobs.filtered(lambda j: j.department_id == record.department_id)
                        record.available_job_ids = jobs

                        if record.job_id:
                            record.available_job_ids = jobs.filtered(lambda j: j.id == record.job_id.id)
                            record.available_employee_ids = record.job_id.employee_ids
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
        self.employee_id = False
    @api.onchange('branch_id')
    def _onchange_branch_id(self):
        self.department_id = False
        self.job_id = False
        self.employee_id = False
    @api.onchange('department_id')
    def _onchange_department_id(self):
        self.job_id = False
        self.employee_id = False

    @api.onchange('job_id')
    def _onchange_job_id(self):
        self.employee_id = False

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('employee.discipline') or 'DES-XX-00000'
        return super().create(vals)

    

    def action_submit(self):
        self.ensure_one()

        if self.state == 'submitted' and self.approval_request_id:
            raise UserError("This record has already been submitted for approval.")

        # Find approval flow
        flow = self.env['approval.flow'].search([
            ('request_model_id.model', '=', 'employee.discipline'),
            ('active', '=', True),
            ('company_id', '=', self.company_id.id)
        ], limit=1)
        if not flow:
            raise UserError("No approval flow defined for Discipline!")

        # Get first step
        first_step = self.env['approval.step'].search([
            ('flow_id', '=', flow.id)
        ], order='sequence asc', limit=1)
        if not first_step:
            raise UserError("No steps defined for this approval flow.")

        # Create approval request
        approval_req = self.env['approval.request'].create({
            'flow_id': flow.id,
            'res_model': self._name,
            'module_name': 'hr',
            'res_id': self.id,
            'current_step_id': first_step.id,
            'status': 'pending',
        })

        # Update record state
        self.write({
            'state': 'pending',
            'approval_request_id': approval_req.id
        })

        # Trigger approval step action
        approval_req.process_action()

         


    def _compute_remarks(self):
            for rec in self:
                rec.remark_ids = self.env['approval.remark.wizard'].search([
                    ('res_model', '=', rec._name),
                    ('res_id', '=', rec.id)
                ])

    def action_reject(self, comment=''):
            self.ensure_one()
            # Save remark and approver’s job
            self.approval_remark = comment
            if self.env.user.employee_id and self.env.user.employee_id.job_id:
                self.approved_by_job_id = self.env.user.employee_id.job_id.id

            if not self.approval_request_id:
                raise UserError("No approval request linked to this Discipline.")
            self.approval_request_id.with_context(action_type='reject', comment=comment).process_action()
            self._sync_state_from_approval()

    def _sync_state_from_approval(self):
            if not self.approval_request_id:
                return
            status = self.approval_request_id.status
            if status == 'approved':
                self.state = 'approved'
                if self.action_type == 'termination':
                   self.create_acceptance_letter(self.approval_request_id)
                # insert into acceptance leter table
            elif status == 'rejected':
                self.state = 'rejected'
            elif status == 'pending':
                self.state = 'pending'
            else:
                self.state = 'draft'

    def _compute_step_progress(self):
            for rec in self:
                rec.step_progress = rec.approval_request_id.step_progress if rec.approval_request_id else "<span>No approval steps yet.</span>"
    def create_acceptance_letter(self, approval_request):
            if not approval_request:
                raise ValidationError("No approval request provided for acceptance letter creation.")
            
            acceptance_vals = {
                'employee_id': self.employee_id.id,
                'name': self.name,
                'req_type': 'discipline',
                'comments': f"Accepted Discipline for {self.employee_id.name}",
                'acceptance_date': fields.Date.today(),
                'state': 'draft',
            }
            # Create the acceptance letter    
            acceptance_letter = self.env['employee.resignation.acceptance'].create(acceptance_vals)

    def action_pass_to_legal(self, comment=''):
            self.ensure_one()
            self.approval_remark = comment
            if self.env.user.employee_id and self.env.user.employee_id.job_id:
                self.approved_by_job_id = self.env.user.employee_id.job_id.id

            if not self.approval_request_id:
                raise UserError("No approval request linked to this Discipline.")

            self.approval_request_id.with_context(action_type='pass_to_legal', comment=comment).process_action()
            self._sync_state_from_approval()


    def action_forward(self, comment=''):
            self.ensure_one()
            self.approval_remark = comment
            if self.env.user.employee_id and self.env.user.employee_id.job_id:
                self.approved_by_job_id = self.env.user.employee_id.job_id.id

            if not self.approval_request_id:
                raise UserError("No approval request linked to this Discipline.")

            self.approval_request_id.with_context(action_type='forward', comment=comment).process_action()
            self._sync_state_from_approval()
    

    @api.depends("approval_request_id", "approval_request_id.approver_ids")
    def _compute_can_approve(self):
        uid = self.env.user.id
        for leave in self:
            # Ensure the approver list is up-to-date
            leave.approval_request_id._compute_current_approvers()

            # Get list of approver user IDs
            approvers = leave.approval_request_id.approver_ids.ids or []

            # Compute permission
            leave.can_approve = (
                leave.state not in ("approved", "rejected")
                and uid in approvers
            )

            # Debug log for troubleshooting
            _logger.debug(
                f"[DEBUG CAN_APPROVE] Leave {leave.id} | State: {leave.state} | Approvers: {approvers} | UID: {uid} | Can Approve? {leave.can_approve}"
            )
    
    def action_add_remark(self,action_type):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Add Remark',
            'res_model': 'approval.remark.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_res_model': self._name,   # automatically sets model name
                'default_res_id': self.id,
                'default_action_type': action_type,
            }
        }
    
    
    def action_open_remark_wizard_approve(self):
        return self.action_add_remark('approve')

    def action_open_remark_wizard_reject(self):
        return self.action_add_remark('reject')

    def action_open_remark_wizard_pass_legal(self):
        return self.action_add_remark('pass_to_legal')
    
    def action_open_remark_wizard_forward(self):
        return self.action_add_remark('forward')
    
    def action_approve(self, comment=''):
        self.ensure_one()

        if not self.approval_request_id:
            raise UserError("No approval request linked to this Discipline.")

        # Save remark and approver’s job
        self.approval_remark = comment
        if self.env.user.employee_id and self.env.user.employee_id.job_id:
            self.approved_by_job_id = self.env.user.employee_id.job_id.id

        # Continue your approval logic
        self.approval_request_id.with_context(action_type='approve', comment=comment).process_action()
        self._sync_state_from_approval()

    