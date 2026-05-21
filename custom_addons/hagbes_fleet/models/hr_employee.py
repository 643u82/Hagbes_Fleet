# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    license_number = fields.Char(string='Driver License Number')
    license_expiry = fields.Date(string='License Expiry Date')
    is_driver = fields.Boolean(string='Is Driver', default=False)

    @api.constrains('license_expiry', 'is_driver')
    def _check_license_expiry(self):
        for rec in self:
            if rec.is_driver and rec.license_expiry and rec.license_expiry < fields.Date.today():
                raise ValidationError(_('Driver license has expired!'))

    # Scheduled notification logic to be implemented in next step
    @api.model
    def _cron_check_license_expiry(self):
        """Weekly check for licenses expiring in 30 days."""
        expiry_threshold = fields.Date.add(fields.Date.today(), days=30)
        expiring_drivers = self.search([
            ('is_driver', '=', True),
            ('license_expiry', '<=', expiry_threshold),
            ('license_expiry', '>=', fields.Date.today())
        ])
        for driver in expiring_drivers:
            # Create an activity for the Fleet Manager
            manager_group = self.env.ref('hagbes_fleet.group_fleet_manager')
            managers = manager_group.users
            for manager in managers:
                driver.activity_schedule(
                    'mail.mail_activity_data_todo',
                    user_id=manager.id,
                    summary=_('Driver License Expiry Warning: %s') % driver.name,
                    note=_('The driver license for %s will expire on %s.') % (driver.name, driver.license_expiry)
                )
