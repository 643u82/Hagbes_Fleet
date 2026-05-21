from odoo import models, api, _
from odoo.exceptions import ValidationError

class AccountAnalyticAccount(models.Model):
    _inherit = 'account.analytic.account'

    def unlink(self):
        for record in self:
            linked_jobs = self.env['hr.job'].search_count([('analytic_account_id', '=', record.id)])
            if linked_jobs:
                raise ValidationError(_("You cannot delete this branch because it is linked to one or more Job Positions."))
        return super().unlink()

    @api.onchange('name')
    def _onchange_format_name(self):
        if self.name:
            self.name = ' '.join(word.capitalize() for word in self.name.split())

    @api.model
    def create(self, vals):
        if vals.get('name'):
            cleaned_name = ' '.join(word.capitalize() for word in vals['name'].split())
            vals['name'] = cleaned_name

            # Check for duplicate name + company
            domain = [
                ('name', '=ilike', cleaned_name),
                ('company_id', '=', vals.get('company_id')),
            ]
            if self.search(domain, limit=1):
                raise ValidationError(_("A branch with the same name already exists for the selected company."))

        return super().create(vals)

    def write(self, vals):
        for record in self:
            new_name = vals.get('name') or record.name
            new_company_id = vals.get('company_id', record.company_id.id)

            cleaned_name = ' '.join(word.capitalize() for word in new_name.split())
            vals['name'] = cleaned_name

            # Check for duplicate excluding the current record
            domain = [
                ('id', '!=', record.id),
                ('name', '=ilike', cleaned_name),
                ('company_id', '=', new_company_id),
            ]
            if self.search(domain, limit=1):
                raise ValidationError(_("A branch with the same name already exists for the selected company."))

        return super().write(vals)
