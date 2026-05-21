from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import logging

_logger = logging.getLogger(__name__)
class OnDutyReport(models.Model):
    _name = 'onduty.report'
    _description = 'OnDuty Report'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        required=True,
        default=lambda self: self.env['hr.employee'].search([('user_id', '=', self.env.uid)], limit=1),
        readonly=True,
        tracking = True
    )
    user_id = fields.Many2one(
        'res.users',
        string='Requester User',
        required=True,
        default=lambda self: self.env.user,
        readonly=True,
        tracking=True
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

    branch_company = fields.Many2one(
        'account.analytic.account',
        string='Duty Branch',
        store=True
    )
    # change sister_company to a Many2one so user can pick from companies
    sister_company = fields.Many2one(
        'res.company',
        string='Sister Company',
        domain="[('id', '!=', company_id)]"
    )
    other_company = fields.Char(string='Other Place')

    start_date = fields.Datetime(string='Start Date', required=True)
    end_date = fields.Datetime(string='End Date', required=True)

    duty = fields.Text(string='Duty Description', required=True)
    remark = fields.Text(string='Remark (Optional)', tracking=True)
    attachment = fields.Binary(string='Attachment (Optional)')

    state = fields.Selection([
        ('draft', 'Draft'),
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string='Status', default='draft', tracking=True)
    approval_request_id = fields.Many2one('approval.request', string="Approval Request", readonly=True)
    step_progress = fields.Html(string="Approval Progress", compute='_compute_step_progress')
    can_approve = fields.Boolean(
        string="Can Approve", compute="_compute_can_approve", store=False
    )
    admin_request_id = fields.Many2one('res.users', string='Admin Requester', readonly=True)


    @api.depends("approval_request_id", "approval_request_id.approver_ids")
    def _compute_can_approve(self):
        uid = self.env.user.id
        for report in self:
                report.approval_request_id._compute_current_approvers()

                approvers = report.approval_request_id.approver_ids.mapped("id")
                report.can_approve = (
                        report.state not in ("approved", "rejected") and uid in approvers
                )


    def action_submit(self):
        self.ensure_one()

        if self.state != 'draft':
            raise UserError(_("This report is already submitted."))

        if not (self.branch_company or self.sister_company or self.other_company):
            raise ValidationError("Please fill Duty Company/Place before submitting.")
        if not self.start_date or not self.end_date:
            raise ValidationError("Please fill Duty Period before submitting.")
        if not self.duty:
            raise ValidationError("Please fill Duty Details before submitting.")

        flow = self.env['approval.flow'].search([
            ('request_model_id.model', '=', 'onduty.report'),
            ('active', '=', True),
            ('company_id', '=', self.company_id.id)
        ], limit=1)
        if not flow:
            raise UserError(_("No approval flow defined for OnDuty Reports!"))

        first_step = self.env['approval.step'].search([('flow_id', '=', flow.id)], order='sequence asc', limit=1)
        if not first_step:
            raise UserError(_("No approval steps defined for this flow."))

        approval_req = self.env['approval.request'].create({
            'flow_id': flow.id,
            'res_model': self._name,
            'module_name': 'onduty',
            'res_id': self.id,
            'current_step_id': first_step.id,
            'status': 'pending',
        })

        self.write({
            'state': 'pending',
            'approval_request_id': approval_req.id
        })

        approval_req.process_action()
        self.message_post(body=_("OnDuty Request submitted for approval"))
        return self._open_success_message_wizard("OnDuty Request created successfully!")

    def action_approve(self, comment=''):
        self.ensure_one()
        if not self.approval_request_id:
            raise UserError(_("No approval request linked to this OnDuty Report."))

        self.approval_request_id.with_context(action_type='approve', comment=comment).process_action()
        self._sync_state_from_approval()
        self.message_post(body=_("OnDuty Request approved by %s" % self.env.user.name))
        return self._open_success_message_wizard("OnDuty Request Approved successfully!")
    def action_reject(self, comment=''):
        self.ensure_one()
        if not self.approval_request_id:
            raise UserError(_("No approval request linked to this OnDuty Report."))

        self.approval_request_id.with_context(action_type='reject', comment=comment).process_action()
        self._sync_state_from_approval()
        self.message_post(body=_("OnDuty Request rejected by %s" % self.env.user.name))
        return self._open_success_message_wizard("OnDuty Request Rejected successfully!")
    def _sync_state_from_approval(self):
        if not self.approval_request_id:
            return
        status = self.approval_request_id.status
        if status == 'approved':
            self.state = 'approved'
        elif status == 'rejected':
            self.state = 'rejected'
        elif status == 'pending':
            self.state = 'pending'
        else:
            self.state = 'draft'

    def _compute_step_progress(self):
        for rec in self:
            rec.step_progress = rec.approval_request_id.step_progress if rec.approval_request_id else "<span>No approval steps yet.</span>"

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




