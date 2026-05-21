from odoo import models, fields
from odoo.exceptions import UserError

class DisciplineRemark(models.Model):
    _name = 'discipline.remark'
    _description = 'Discipline Remark'
    _order = 'create_date desc'
    
    discipline_id = fields.Many2one('employee.discipline', string='Discipline', required=True, ondelete='cascade')
    user_id = fields.Many2one('res.users', string='Given By', required=True)
    job_id = fields.Many2one('hr.job', string='Job Position')
    action_type = fields.Selection([
        ('approve', 'Approved'),
        ('reject', 'Rejected'),
        ('pass_to_legal', 'Passed to Legal'),
    ], string='Action')
    comment = fields.Text(string='Remark')
    create_date = fields.Datetime(string='Date', readonly=True)
    date = fields.Datetime(string='Date', default=fields.Datetime.now) 
    def action_confirm(self):
        """Called when user submits the remark pop-up"""
        self.ensure_one()

        record = self.record_id
        if not record:
            raise UserError("No related Discipline record found.")

        # ✅ Save the remark history
        self.env['discipline.remark'].create({
            'discipline_id': record.id,
            'remark': self.comment,
            'user_id': self.env.user.id,
            'action_type': self.action_type,
        })

        # ✅ Call the appropriate action on the main record
        if self.action_type == 'approve':
            record.action_approve(self.comment)
        elif self.action_type == 'reject':
            record.action_reject(self.comment)
        elif self.action_type == 'to_legal':
            record.action_to_legal(self.comment)

        return {'type': 'ir.actions.act_window_close'}
