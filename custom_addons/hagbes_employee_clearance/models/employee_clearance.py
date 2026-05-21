import logging
from odoo import models, fields, api
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class EmployeeClearance(models.Model):
    _name = 'employee.clearance'
    _description = 'Employee Clearance'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    employee_id = fields.Many2one(
    'hr.employee',
    string="Employee",
    
    required=True,
    tracking=True,
    )
    
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
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('pending', 'Pending'),
    ], default='draft', string="Status", tracking=True)

    can_approve = fields.Boolean( string="Can Approve", compute="_compute_can_approve", store=False )
    approval_request_id = fields.Many2one(
        'approval.request',
        string="Approval Request"
        )
    company_id = fields.Many2one('res.company', string="Company")
    branch_id = fields.Many2one('account.analytic.account', string="Branch")
    department_id = fields.Many2one('hr.department', string="Department")
    job_id = fields.Many2one('hr.job', string="Job Position")
    # geting from acceptance letter
    # def _get_accepted_employee_ids(self):
    #     acceptance_records = self.env['employee.resignation.acceptance'].search([])
    #     return acceptance_records.mapped('employee_id').id

    @api.onchange('employee_id')
    def _onchange_employee_id(self):
        if self.employee_id:
            self.company_id = self.employee_id.company_id
            self.branch_id = self.employee_id.branch_id
            self.department_id = self.employee_id.department_id
            self.job_id = self.employee_id.job_id
        else:
            self.company_id = False
            self.branch_id = False
            self.department_id = False
            self.job_id = False
            
    def action_submit(self):
        self.ensure_one()

        if self.state == 'submitted' and self.approval_request_id:
            raise UserError("This record has already been submitted for approval.")

        # Find approval flow
        flow = self.env['approval.flow'].search([
            ('request_model_id.model', '=', 'employee.clearance'),
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
    def _compute_remarks(self):
            for rec in self:
                rec.remark_ids = self.env['approval.remark.wizard'].search([
                    ('res_model', '=', rec._name),
                    ('res_id', '=', rec.id)
                ])
    def _compute_step_progress(self):
            for rec in self:
                rec.step_progress = rec.approval_request_id.step_progress if rec.approval_request_id else "<span>No approval steps yet.</span>"


    def action_open_remark_wizard_approve(self):
        return self.action_add_remark('approve')

    def action_open_remark_wizard_reject(self):
        return self.action_add_remark('reject')

    # def action_open_remark_wizard_pass_legal(self):
    #     return self.action_add_remark('pass_to_legal')
    
    def action_open_remark_wizard_forward(self):
        return self.action_add_remark('forward')
    

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