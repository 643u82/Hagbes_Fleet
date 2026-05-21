from odoo import models, api, _
from odoo.exceptions import ValidationError

class HrDepartment(models.Model):
    _inherit = 'hr.department'

    def unlink(self):
        for record in self:
            linked_jobs = self.env['hr.job'].search_count([('department_id', '=', record.id)])
            if linked_jobs:
                raise ValidationError(_("You cannot delete this department. It is linked to one or more Job Positions."))
        return super().unlink()

    @api.onchange('name')
    def _onchange_format_name(self):
        if self.name:
            self.name = ' '.join(word.capitalize() for word in self.name.split())

    @api.model
    def create(self, vals):
        if vals.get('name'):
            cleaned_name = ' '.join(word.capitalize() for word in vals['name'].split())
            # Check for existing department with same cleaned name
            if self.env['hr.department'].search([('name', '=ilike', cleaned_name)], limit=1):
                raise ValidationError(_("A department with the same name already exists."))
            vals['name'] = cleaned_name
        return super().create(vals)

    def write(self, vals):
        if vals.get('name'):
            cleaned_name = ' '.join(word.capitalize() for word in vals['name'].split())
            # Exclude current record in duplicate check
            duplicate = self.env['hr.department'].search([
                ('name', '=ilike', cleaned_name),
                ('id', '!=', self.id)
            ], limit=1)
            if duplicate:
                raise ValidationError(_("A department with the same name already exists."))
            vals['name'] = cleaned_name
        return super().write(vals)
