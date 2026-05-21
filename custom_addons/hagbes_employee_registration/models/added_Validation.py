from odoo import models, api, fields
from odoo.exceptions import ValidationError
import re

class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    # ----------------------
    # Certificate Selection
    # ----------------------
    CERTIFICATE_SELECTION = [
        ('tvt level 1', 'TVET LEVEL I'),
        ('tvt level 2', 'TVET LEVEL II'),
        ('tvt level 3', 'TVET LEVEL III'),
        ('tvt level 4', 'TVET LEVEL IV'),
        ('tvt level 5', 'TVET LEVEL V'),
        ('bachelor', 'Bachelor'),
        ('diploma', 'Diploma'),
        ('ba', 'BA'),
        ('bsc', 'BSc'),
        ('ma', 'MA'),
        ('msc', 'MSc'),
        # Add more if needed
    ]

    # ----------------------
    # Custom Fields
    # ----------------------
    certificate = fields.Selection(
        selection=CERTIFICATE_SELECTION,
        string='Certificate',
       
        help='Educational qualification of the employee',
    )
    tin_no = fields.Char(string='TIN Number')
    pension_id = fields.Char(string='Pension ID')

    # ----------------------
    # SQL Constraints
    # ----------------------
    _sql_constraints = [
        ('unique_passport_id', 'UNIQUE(passport_id)', 'Passport Number must be unique!'),
        ('unique_tin_no', 'UNIQUE(tin_no)', 'TIN Number must be unique!'),
        ('unique_pension_id', 'UNIQUE(pension_id)', 'Pension ID must be unique!'),
    ]

    # ----------------------
    # Manual Uniqueness Validation
    # ----------------------
    @api.constrains('passport_id', 'tin_no', 'pension_id')
    def _check_unique_ids(self):
        for rec in self:
            if rec.passport_id:
                existing = self.search([
                    ('passport_id', '=', rec.passport_id),
                    ('id', '!=', rec.id)
                ])
                if existing:
                    raise ValidationError("Passport Number must be unique!")
            if rec.tin_no:
                existing = self.search([
                    ('tin_no', '=', rec.tin_no),
                    ('id', '!=', rec.id)
                ])
                if existing:
                    raise ValidationError("TIN Number must be unique!")
            if rec.pension_id:
                existing = self.search([
                    ('pension_id', '=', rec.pension_id),
                    ('id', '!=', rec.id)
                ])
                if existing:
                    raise ValidationError("Pension ID must be unique!")

    # ----------------------
    # Phone Format Validation
    # ----------------------
    @api.constrains('work_phone', 'mobile_phone', 'emergency_phone')
    def _check_work_phone_mobile(self):
        pattern = r'^(\+251|0)?9\d{8}$'
        for rec in self:
            for field in ['work_phone', 'mobile_phone', 'emergency_phone']:
                number = getattr(rec, field, False)
                if number and not re.match(pattern, number):
                    raise ValidationError(
                        f"Field '{field}' has invalid phone number format: {number}. "
                        "Expected format: +2519xxxxxxxx or 09xxxxxxxx."
                    )
