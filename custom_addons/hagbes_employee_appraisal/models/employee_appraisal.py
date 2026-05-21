import logging
from odoo import models, fields, api
from dateutil.relativedelta import relativedelta
from odoo.exceptions import UserError, AccessError
from lxml import etree
_logger = logging.getLogger(__name__)
class EmployeeAppraisal(models.Model):
    _name = "employee.appraisal" 
    _description = "Employee Appraisal"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    
    remark_ids = fields.One2many(
        'approval.remark.wizard',
        'res_id',
        string='Remarks',
        compute='_compute_remarks', 
        store =True
    )
    job_id = fields.Many2one('hr.job', string="Job Position")

    approval_remark = fields.Text(string='Approval Remark', readonly=True)
    approved_by_job_id = fields.Many2one('hr.job', string='Approved By Job', readonly=True)
    # approval_request_id = fields.Many2one(
    # 'approval.request',
    # string="Approval Request"
    # )
    # Related request fields for display in the appraisal form (read-only)
    request_flow_id = fields.Many2one(
        'approval.flow',
        related='approval_request_id.flow_id',
        string='Approval Flow',
        readonly=True,
        store=False,
    )
    request_status = fields.Selection(
        related='approval_request_id.status',
        string='Request Status',
        readonly=True,
        store=False
    )

    request_requested_by = fields.Many2one('res.users', related='approval_request_id.requested_by', string='Requested By', readonly=True, store=False)
    request_step_progress = fields.Html(related='approval_request_id.step_progress', string='Step Progress', readonly=True, store=False)
    request_res_model = fields.Char(related='approval_request_id.res_model', string='Resource Model', readonly=True, store=False)
    request_res_id = fields.Integer(related='approval_request_id.res_id', string='Resource ID', readonly=True, store=False)
    # is_readonly = fields.Boolean(
    #     compute='_compute_is_readonly',
    #     store=False
    # )
    can_user_manage = fields.Boolean(
        compute='_compute_can_user_manage',
        string="Can Current User Manage This Appraisal"
    )
    can_approve = fields.Boolean( string="Can Approve", compute="_compute_can_approve", store=False )
    action_type = fields.Selection([
                    ('approve', 'Approved'),
                    ('reject', 'Rejected'),
                    ('pass_to_legal', 'Passed to Legal'),
                    ('to_employee', 'Sent to Employee'),
                ], string='Action')

    total_score = fields.Integer(
        string="Total Score", related="employee_id.total_score", store=True, readonly=True
    )
    average_score = fields.Float(
        string="Average Score", related="employee_id.average_score", store=True, readonly=True
    )
    employee_id = fields.Many2one(
        'hr.employee',
        string="Employee",
        required=True,
        domain=[('active', '=', True)]
        # domain=lambda self: self._get_employee_domain()
    )
    approval_request_id = fields.Many2one(
    'approval.request',
    string="Approval Request"
    )
    step_progress = fields.Html(string="Approval Progress", compute='_compute_step_progress')
    company_id = fields.Many2one('res.company', string="Company", default=lambda self: self.env.company, required=True)
    branch_id = fields.Many2one(
    'account.analytic.account',
    string="Branch",
    default=lambda self: (
        self.env.user.employee_id.branch_id.id
        if self.env.user.employee_id and self.env.user.employee_id.branch_id
        else False
    ),
    required=False
    )

    department_id = fields.Many2one(
    'hr.department',
    string="Department",
    required=True,
    default=lambda self: (
        self.env.user.employee_id.department_id.id
        if self.env.user.employee_id and self.env.user.employee_id.department_id
        else False
    )
    )

    

            
    evaluator_id = fields.Many2one("res.users", string="Evaluator", default=lambda self: self.env.user)
    category_id = fields.Many2one("appraisal.criteria.category", string="Criteria Category", required=True)
    evaluation_type = fields.Selection([
        ('annual', "Annual"),
        ('bi_annual', 'Bi-Annual'),
        ('other', "Other"),
    ], string="Evaluation Type", required=True)
    evaluation_start_date = fields.Date(
        string="Evaluation Start Date",
        required=True
    )
    evaluation_end_date = fields.Date(
        string="Evaluation End Date"
    )
    state = fields.Selection([
        ('draft', 'Draft'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('pending', 'Pending'),
    ], default='draft', string="Status", tracking=True)
    criteria_line_ids = fields.One2many("employee.appraisal.line", "appraisal_id", string="Criteria Evaluations")
    remarks = fields.Text(string="Remarks")
    employee_feedback = fields.Text(string="Employee Feedback")
    # employee_response = fields.Selection([
    #     ('pending', "Pending"),
    #     ('accepted', "Accepted"),
    #     ('rejected', "Rejected"),
    # ], default="pending", string="Employee Response")
   
    
    @api.onchange('evaluation_type', 'evaluation_start_date')
    def _onchange_evaluation_dates(self):
        """ Auto-fill end date depending on evaluation type """
        for record in self:
            if record.evaluation_start_date:
                if record.evaluation_type == 'annual':
                    record.evaluation_end_date = record.evaluation_start_date + relativedelta(years=1, days=-1)
                elif record.evaluation_type == 'bi_annual':
                    record.evaluation_end_date = record.evaluation_start_date + relativedelta(months=6, days=-1)
                else:
                    record.evaluation_end_date = False 
    def action_load_criteria(self):
            """Load criteria from the selected category into this appraisal"""
            for record in self:
                if not record.category_id:
                    continue

                # Clear existing lines
                record.criteria_line_ids.unlink()

                # Get criteria from the selected category
                criteria = self.env["appraisal.criteria"].search([
                    ("category_id", "=", record.category_id.id),
                    # ("active", "=", True)
                ])

                lines = []
                for crit in criteria:
                    lines.append((0, 0, {
                        "criteria_id": crit.id,
                        "employee_id": record.employee_id.id,
                    }))
                record.criteria_line_ids = lines
   
    def action_submit(self):
        self.ensure_one()

        if self.state == 'submitted' and self.approval_request_id:
            raise UserError("This record has already been submitted for approval.")

        # Find approval flow
        flow = self.env['approval.flow'].search([
            ('request_model_id.model', '=', 'employee.appraisal'),
            ('active', '=', True),
            ('company_id', '=', self.company_id.id)
        ], limit=1)
        if not flow:
            raise UserError("No approval flow defined for appraisal!")

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
            'requested_for_id': self.employee_id.user_id.id,
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
        # self.message_post(
        #     body="appraisal submitted for approval",
        #     message_type="notification",
        #     subtype_xmlid="mail.mt_note"
        # )  

    def action_approve(self, comment=''):
        self.ensure_one()

        if not self.approval_request_id:
            raise UserError("No approval request linked to this Appraisal.")

        # Save remark and approver’s job
        self.approval_remark = comment
        if self.env.user.employee_id and self.env.user.employee_id.job_id:
            self.approved_by_job_id = self.env.user.employee_id.job_id.id

        # Continue your approval logic
        self.approval_request_id.with_context(action_type='approve', comment=comment).process_action()
        self._sync_state_from_approval()

    
    def action_reject(self, comment=''):
            self.ensure_one()
            # Save remark and approver’s job
            self.approval_remark = comment
            if self.env.user.employee_id and self.env.user.employee_id.job_id:
                self.approved_by_job_id = self.env.user.employee_id.job_id.id

            if not self.approval_request_id:
                raise UserError("No approval request linked to this Appraisal.")
            self.approval_request_id.with_context(action_type='reject', comment=comment).process_action()
            self._sync_state_from_approval()

    def to_employee (self, comment='' ):
          
            self.ensure_one()
            # Save remark and approver’s job
            self.approval_remark = comment
            if self.env.user.employee_id and self.env.user.employee_id.job_id:
                self.approved_by_job_id = self.env.user.employee_id.job_id.id

            if not self.approval_request_id:
                raise UserError("No approval request linked to this Appraisal.")
            self.approval_request_id.with_context(action_type='to_employee', comment=comment).process_action()
            self._sync_state_from_approval()
            
    def _compute_step_progress(self):
            for rec in self:
                rec.step_progress = rec.approval_request_id.step_progress if rec.approval_request_id else "<span>No approval steps yet.</span>"


    def _sync_state_from_approval(self):
            if not self.approval_request_id:
                return
            status = self.approval_request_id.status
            if status == 'approved':
                self.state = 'approved'
                # self.create_acceptance_letter(self.approval_request_id)
                # insert into acceptance leter table
            elif status == 'rejected':
                self.state = 'rejected'
            elif status == 'pending':
                self.state = 'pending'
            else:
                self.state = 'draft'
    @api.depends('criteria_line_ids.score')
    def _compute_scores(self):
        for appraisal in self:
            scores = appraisal.criteria_line_ids.mapped('score')
            # Convert to float safely, ignore invalid or empty values
            numeric_scores = []
            for s in scores:
                try:
                    numeric_scores.append(float(s))
                except (TypeError, ValueError):
                    continue
            appraisal.total_score = sum(numeric_scores) if numeric_scores else 0
            appraisal.average_score = sum(numeric_scores)/len(numeric_scores) if numeric_scores else 0.0

    def action_recompute_scores(self):
        self._compute_scores()



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
    
    def action_open_remark_wizard_to_employee(self):
        return self.action_add_remark('to_employee')

    def _compute_remarks(self):
            for rec in self:
                rec.remark_ids = self.env['approval.remark.wizard'].search([
                    ('res_model', '=', rec._name),
                    ('res_id', '=', rec.id)
                ])
   


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




    @api.model
    def action_view_my_appraisals(self):
        user = self.env.user

        # Allow HR Officers & HR Managers & Admin to see ALL appraisals
        if user.has_group('hr.group_hr_user') or user.has_group('hr.group_hr_manager') or user.has_group('base.group_system'):
            return {
                'type': 'ir.actions.act_window',
                'name': 'All Appraisals',
                'res_model': 'employee.appraisal',
                'view_mode': 'kanban,list,form',
                'domain': [],  # FULL ACCESS → no filtering
                'target': 'current',
                'context': {'readonly_mode': False},
            }

        # Normal employee / evaluator access
        employee = self.env['hr.employee'].search([('user_id', '=', user.id)], limit=1)

        # collect subordinate employee IDs (recursively)
        subordinate_ids = (
            employee._get_subordinates().ids
            if hasattr(employee, '_get_subordinates')
            else self.env['hr.employee'].search([('parent_id', 'child_of', employee.id)]).ids
        )

        # Domain for non-HR users
        domain = [
            '|', '|', '|',
            ('create_uid', '=', user.id),                # You created it
            ('evaluator_id.user_id', '=', user.id),      # You evaluate it
            ('employee_id.user_id', '=', user.id),       # You are the employee
            ('create_uid.employee_id', 'in', subordinate_ids),  # Your subordinates
        ]

        return {
            'type': 'ir.actions.act_window',
            'name': 'My Appraisals',
            'res_model': 'employee.appraisal',
            'view_mode': 'kanban,list,form',
            'domain': domain,
            'target': 'current',
            'context': {'readonly_mode': True},
        }

 

    
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        res = super().fields_view_get(view_id=view_id, view_type=view_type, toolbar=toolbar, submenu=submenu)
        print(">>> fields_view_get CALLED <<<", view_type)      
        if view_type == 'form':
            active_id = self.env.context.get('active_id') or self.env.context.get('id')
            if active_id:
                rec = self.browse(active_id)
                if rec and rec.state in ('pending', 'approved', 'rejected'):
                    doc = etree.XML(res['arch'])
                    form = doc.xpath("//form")
                    if form:
                        form[0].set('edit', 'false')
                        form[0].set('create', 'false')
                        form[0].set('delete', 'false')
                    res['arch'] = etree.tostring(doc, encoding='unicode')
        return res

    

class EmployeeAppraisalLine(models.Model):
    _name = "employee.appraisal.line"
    _description = "Employee Appraisal Line"
    
    employee_id = fields.Many2one('hr.employee', string='Employee', required=True)
    appraisal_id = fields.Many2one("employee.appraisal", string="Appraisal", ondelete="cascade")
    criteria_id = fields.Many2one("appraisal.criteria", string="Criteria", required=True)
    # score = fields.Integer(string="Score")
    score = fields.Selection([
        ('1', "★"),
        ('2', "★★"),
        ('3', "★★★"),
        ('4', "★★★★"),
        ('5', "★★★★★"),
    ], string="Score")
    note = fields.Text(string="Remarks")

    state = fields.Selection(related="appraisal_id.state", store=True, readonly=True)