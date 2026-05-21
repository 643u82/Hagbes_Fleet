# models/res_company.py
from odoo import models, fields


class ResCompany(models.Model):
    _inherit = 'res.company'

    
    vat = fields.Char(string="VAT")  

    tin_number = fields.Char(
        string='TIN Number',
        help='Tax Identification Number for the company'
    )
    
    prefix = fields.Char(string="Prefix",)