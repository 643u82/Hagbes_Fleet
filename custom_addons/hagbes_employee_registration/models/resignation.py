from odoo import models, fields, api
from odoo.exceptions import ValidationError,UserError
import logging

_logger = logging.getLogger(__name__)

class EmployeeResignation(models.Model):
    _name = 'employee.resignation'
    _description = 'Employee Resignation'
    _order = 'resignation_date desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    action_type = fields.Selection([
                    ('approve', 'Approved'),
                    ('reject', 'Rejected'),
                    ('agreement_reached', 'Agreement Reached'),
                    ('forward', 'Forwarded')
                ], string='Action')

    approval_remark = fields.Text(string="Approval Remark", tracking=True)
    approved_by_job_id = fields.Many2one('hr.job', string="Approved By Job Position", tracking=True)
    is_current_user = fields.Boolean(compute="_compute_is_current_user", store=False)
    name = fields.Char(string="Resignation Reference", required=True, default='New', copy=False, readonly=True, tracking=True)
    employee_id = fields.Many2one('hr.employee', string='Employee', required=True,tracking=True)
    department_id = fields.Many2one(related='employee_id.department_id', readonly=True, tracking=True)
    job_id = fields.Many2one(related='employee_id.job_id', readonly=True,tracking=True)
    resignation_date = fields.Date(string='Resignation Date', required=True, tracking=True)
    reason = fields.Selection([
        ('personal', 'Personal Reasons'),
        ('health', 'Health Issues'),
        ('career', 'Career Change'),
        ('poor_work_env', 'Poor Working Environment'),
        ('low_salary', 'Compensation Below Expectations'),
        ('other', 'Other'),
    ], string='Reason for Resignation', required=True)
    can_approve = fields.Boolean( string="Can Approve", compute="_compute_can_approve", store=False )
    other_reason = fields.Text(string='Please specify', help="If you selected 'Other', explain here.")
    show_other_reason = fields.Boolean(compute="_compute_show_other_reason")
    remark_ids = fields.One2many(
        'approval.remark.wizard',
        'res_id',
        string='Remarks',
        compute='_compute_remarks', 
        store =True
    )
    company_id = fields.Many2one(
    'res.company', string='Company',
    default=lambda self: self.env.company
   )
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], default='draft', string='Status')
    approval_request_id = fields.Many2one('approval.request', string="Approval Request", readonly=True)
    step_progress = fields.Html(string="Approval Progress", compute='_compute_step_progress')
    branch_id = fields.Many2one(related='employee_id.branch_id', readonly=True, compute_sudo=True, tracking=True)
    @api.depends('reason')
    def _compute_show_other_reason(self):
        for rec in self:
            rec.show_other_reason = rec.reason == 'other'

    @api.constrains('reason', 'other_reason')
    def _check_other_reason(self):
        for rec in self:
            if rec.reason == 'other' and not rec.other_reason:
                raise ValidationError("Please specify the reason if you select 'Other'.")
     
    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        user = self.env.user
        employee = self.env['hr.employee'].search([('user_id', '=', user.id)], limit=1)

        if employee:
            if 'employee_id' in fields_list:
                res['employee_id'] = employee.id
            if 'branch_id' in fields_list and employee.branch_id:
                res['branch_id'] = employee.branch_id.id
            
        
        return res

    @api.model
    def create(self, vals):
        user = self.env.user
        employee = self.env['hr.employee'].search([('user_id', '=', user.id)], limit=1)

        # Fill default employee and branch if not provided
        if 'employee_id' not in vals and employee:
            vals['employee_id'] = employee.id
            if employee.branch_id:
                vals['branch_id'] = employee.branch_id.id

        # Set name ONLY via sequence
        if not vals.get('name') or vals['name'] == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('employee.resignation') or 'REQ-XXXX-00000'

        # Create record once
        record = super(EmployeeResignation, self).create(vals)

        # Post chatter message
        record.message_post(
            body="Resignation request created",
            message_type="notification",
            subtype_xmlid="mail.mt_note"
        )

        return record


     
    def _compute_remarks(self):
        for rec in self:
            rec.remark_ids = self.env['approval.remark.wizard'].search([
                ('res_model', '=', rec._name),
                ('res_id', '=', rec.id)
            ])
   

    def action_submit(self):
        self.ensure_one()

        if self.state == 'submitted' and self.approval_request_id:
            raise UserError("This record has already been submitted for approval.")

        # Find approval flow
        flow = self.env['approval.flow'].search([
            ('request_model_id.model', '=', 'employee.resignation'),
            ('active', '=', True),
            ('company_id', '=', self.company_id.id)
        ], limit=1)
        if not flow:
            raise UserError("No approval flow defined for Resignation!")

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

        # Post chatter message
        self.message_post(
            body="Resignation submitted for approval",
            message_type="notification",
            subtype_xmlid="mail.mt_note"
        )   


   
   
    def agreement_reached(self, comment=''):
        self.ensure_one()
           

        if not self.approval_request_id:
            raise UserError("No approval request linked to this Discipline.")

        # Save remark and approver’s job
        self.approval_remark = comment
        if self.env.user.employee_id and self.env.user.employee_id.job_id:
            self.approved_by_job_id = self.env.user.employee_id.job_id.id

        # Continue your approval logic
        self.approval_request_id.with_context(action_type='agreement_reached', comment=comment).process_action()
        self._sync_state_from_approval()



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

    def action_reject(self, comment=''):
        self.ensure_one()

        if not self.approval_request_id:
            raise UserError("No approval request linked to this Discipline.")

        # Save remark and approver’s job
        self.approval_remark = comment
        if self.env.user.employee_id and self.env.user.employee_id.job_id:
            self.approved_by_job_id = self.env.user.employee_id.job_id.id

        # Continue your approval logic
        self.approval_request_id.with_context(action_type='reject', comment=comment).process_action()
        self._sync_state_from_approval()
    def _sync_state_from_approval(self):
        if not self.approval_request_id:
            return
        status = self.approval_request_id.status
        if status == 'approved':
            self.state = 'approved'
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
    
    def action_open_remark_wizard_agreement_reached(self):
        return self.action_add_remark('agreement_reached')

   


    def create_acceptance_letter(self, approval_request):
        if not approval_request:
            raise ValidationError("No approval request provided for acceptance letter creation.")
        
        acceptance_vals = {
            'employee_id': self.employee_id.id,
            'name': self.name,
            'req_type': 'resignation',
            'comments': f"Accepted resignation for {self.employee_id.name}",
            'acceptance_date': fields.Date.today(),
            'state': 'draft',
        }
        # Create the acceptance letter    
        acceptance_letter = self.env['employee.resignation.acceptance'].create(acceptance_vals)

