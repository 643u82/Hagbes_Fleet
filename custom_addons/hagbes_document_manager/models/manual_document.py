from odoo import models, fields, api
from odoo.exceptions import AccessError


class ManualDocument(models.Model):
    _name = 'manual.document'
    _description = 'Department User Manual'
    _rec_name = 'name'

    name = fields.Char(required=True)
    description = fields.Text()
    
    department_id = fields.Many2one(
        'hr.department',
        string="Department",
        required=True
    )

    file = fields.Binary(string="Upload File", required=True)
    file_name = fields.Char(string="File Name")

    uploaded_by = fields.Many2one(
        'res.users',
        string="Uploaded By",
        default=lambda self: self.env.user,
        readonly=True
    )

    upload_date = fields.Datetime(
        default=fields.Datetime.now,
        readonly=True
    )

    def action_download(self):
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/manual.document/{self.id}/file/{self.file_name}?download=true',
            'target': 'self',
        }

    @api.model
    def search(self, args, **kwargs):
        user = self.env.user
        if not user.has_group('hagbes_document_manager.group_manual_admin'):
            employee = self.env['hr.employee'].search(
                [('user_id', '=', user.id)], limit=1
            )
            if employee and employee.department_id:
                args.append(('department_id', '=', employee.department_id.id))
            else:
                args.append(('id', '=', 0))
        return super().search(args, **kwargs)