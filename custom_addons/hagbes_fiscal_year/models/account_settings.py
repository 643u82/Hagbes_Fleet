from odoo import api, fields, models

MONTH_SELECTION = [
    ('1', 'January'),
    ('2', 'February'),
    ('3', 'March'),
    ('4', 'April'),
    ('5', 'May'),
    ('6', 'June'),
    ('7', 'July'),
    ('8', 'August'),
    ('9', 'September'),
    ('10', 'October'),
    ('11', 'November'),
    ('12', 'December'),
]


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    fiscalyear_last_day = fields.Integer(
        related='company_id.fiscalyear_last_day', readonly=False,
        string="Fiscalyear Last Day"
    )
    fiscalyear_last_month = fields.Selection(
        selection=MONTH_SELECTION,
        related='company_id.fiscalyear_last_month', readonly=False,
        string="Fiscalyear Last Month"
    )
    tax_lock_date = fields.Date(
        related='company_id.tax_lock_date', readonly=False
    )
    sale_lock_date = fields.Date(
        related='company_id.sale_lock_date', readonly=False
    )
    purchase_lock_date = fields.Date(
        related='company_id.purchase_lock_date', readonly=False
    )
    hard_lock_date = fields.Date(
        related='company_id.hard_lock_date', readonly=False
    )
    fiscalyear_lock_date = fields.Date(
        related='company_id.fiscalyear_lock_date', readonly=False
    )
    group_fiscal_year = fields.Boolean(
        string='Fiscal Years', implied_group='hagbes_fiscal_year.group_fiscal_year'
    )
