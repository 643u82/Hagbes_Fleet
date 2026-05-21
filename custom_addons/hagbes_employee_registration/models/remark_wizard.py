from odoo import models, fields, api
from odoo.exceptions import UserError

class ApprovalRemarkWizard(models.Model):
    _name = 'approval.remark.wizard'  # now a permanent model
    _description = 'Approval Remark Wizard'
    _order = 'date desc'

    # Reference to any main record
    res_model = fields.Char(string="Model", required=True)
    res_id = fields.Integer(string="Record ID", required=True)

    action_type = fields.Selection([
        ('approve', 'Approved'),
        ('reject', 'Rejected'),
        ('pass_to_legal', 'Passed to Legal'),
    ], string='Action', required=True)

    user_id = fields.Many2one(
        'res.users',
        string="Given By",
        default=lambda self: self.env.user,
        required=True
    )

    job_id = fields.Many2one(
        'hr.job',
        string='Job Position',
        default=lambda self: self.env.user.employee_id.job_id if self.env.user.employee_id else False
    )

    comment = fields.Text(string='Remark')
    date = fields.Datetime(string='Date', default=fields.Datetime.now)

    @api.model
    def create_remark(self, res_model, res_id, action_type, comment):
        """Helper to create a remark record in this model"""
        return self.create({
            'res_model': res_model,
            'res_id': res_id,
            'action_type': action_type,
            'comment': comment,
            'user_id': self.env.user.id,
            'job_id': self.env.user.employee_id.job_id.id if self.env.user.employee_id and self.env.user.employee_id.job_id else False,
        })

    def action_confirm(self):
        """Called when user submits the remark pop-up"""
        self.ensure_one()

        if not self.res_model or not self.res_id:
            raise UserError("No linked record found.")

        # Fetch main record
        target_record = self.env[self.res_model].browse(self.res_id)
        if not target_record.exists():
            raise UserError("The target record no longer exists.")

        # Call the main record method dynamically
        if hasattr(target_record, f"action_{self.action_type}"):
            getattr(target_record, f"action_{self.action_type}")(comment=self.comment)

       

        return {'type': 'ir.actions.act_window_close'}
