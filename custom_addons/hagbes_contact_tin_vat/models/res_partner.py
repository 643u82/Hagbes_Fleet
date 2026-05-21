from odoo import _, models, fields,api
from dateutil.relativedelta import relativedelta
from datetime import date
from odoo.exceptions import ValidationError

class ResPartner(models.Model):
    _inherit = 'res.partner'

    tin_number = fields.Char(
        string='TIN Number',
        help='Tax Identification Number for the company'
    )

    credit_limit_interval_months = fields.Integer(
        string="Credit Limit Duration (Months)",
        default=1,
        help="Customer must settle outstanding balance by the end of every N months (e.g., 1 = monthly, 2 = every 2 months).",
        groups="account.group_account_invoice,account.group_account_readonly"
    )
    partner_type = fields.Selection([
        ('B2B', 'B2B (Business to Business)'),
        ('B2C', 'B2C (Business to Consumer)'),
        ('B2G', 'B2G (Business to Government)'),
    ], string="Partner Type", required=True, default='B2C')

    @api.constrains('partner_type','tin_number','vat')
    def _check_tin_vat_for_b2b_b2g(self):
        for partner in self:
            if partner.partner_type in ('B2B, B2G'):
                if not partner.tin_number:
                    raise ValidationError(
                        _("TIN Number is required for %s partners.") % 
                        dict(self._fields['partner_type'].selection).get(partner.partner_type)
                    )
                if not partner.vat:
                    raise ValidationError(
                        _("VAT Number is required for %s partners.") % 
                        dict(self._fields['partner_type'].selection).get(partner.partner_type)
                    )

    def _compute_credit_limit_due_date(self):
        """Compute due date as: end of (current month + interval - 1)"""
        self.ensure_one()
        if not self.credit_limit_interval_months or self.credit_limit_interval_months <= 0:
            return False

        today = date.today()
        # Add (N - 1) months to current month, then go to last day of that month
        target_month_date = today + relativedelta(months=self.credit_limit_interval_months - 1)
        # Get last day of that month
        due_date = target_month_date + relativedelta(day=31)  # This auto-adjusts to last day
        return due_date

    credit_limit_due_date = fields.Date(
        string="Next Credit Due Date",
        compute="_compute_credit_limit_due_date_field",
        help="End of the current credit period. Customer must pay by this date.",
        groups="account.group_account_invoice,account.group_account_readonly"
    )

    def _compute_credit_limit_due_date_field(self):
        for partner in self:
            partner.credit_limit_due_date = partner._compute_credit_limit_due_date()