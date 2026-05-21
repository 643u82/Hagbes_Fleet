# hagbes_employee_registration/reports/report.py
from odoo import models

class PrivateEmployeeReport(models.AbstractModel):
    _name = 'report.hagbes_employee_registration.private_employee_report'
    _description = 'Private Employee Report'

    def _get_report_values(self, docids, data=None):
        docs = self.env['hr.employee'].browse(docids)
        return {
            'doc_ids': docids,
            'doc_model': 'hr.employee',
            'docs': docs,
        }
