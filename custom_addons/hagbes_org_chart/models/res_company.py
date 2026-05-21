from odoo import models, api, _
from odoo.exceptions import ValidationError

class ResCompany(models.Model):
    _inherit = 'res.company'

    def unlink(self):
        for record in self:
            linked_jobs = self.env['hr.job'].search_count([('company_id', '=', record.id)])
            if linked_jobs:
                raise ValidationError(_("You cannot delete this company. It is linked to one or more Job Positions."))
        return super().unlink()

    @api.onchange('name')
    def _onchange_format_name(self):
        if self.name:
            self.name = ' '.join(word.capitalize() for word in self.name.split())

    @api.model
    def create(self, vals):
        if vals.get('name'):
            cleaned_name = ' '.join(word.capitalize() for word in vals['name'].split())
            # Check for existing company with same cleaned name (case-insensitive)
            if self.env['res.company'].search([('name', '=ilike', cleaned_name)], limit=1):
                raise ValidationError(_("A company with the same name already exists."))
            vals['name'] = cleaned_name
        return super().create(vals)

    def write(self, vals):
        if vals.get('name'):
            cleaned_name = ' '.join(word.capitalize() for word in vals['name'].split())
            # Exclude self in duplicate check
            duplicate = self.env['res.company'].search([
                ('name', '=ilike', cleaned_name),
                ('id', '!=', self.id)
            ], limit=1)
            if duplicate:
                raise ValidationError(_("A company with the same name already exists."))
            vals['name'] = cleaned_name
        return super().write(vals)
