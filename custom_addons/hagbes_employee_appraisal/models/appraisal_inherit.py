import logging
from odoo import models
from lxml import etree

_logger = logging.getLogger(__name__)

class EmployeeAppraisal(models.Model):
    _inherit = "employee.appraisal"

    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        res = super().fields_view_get(view_id=view_id, view_type=view_type, toolbar=toolbar, submenu=submenu)
        _logger.info(">>> fields_view_get called: view_type=%s, active_id=%s", view_type, self.env.context.get('active_id'))

        if view_type == 'form':
            active_id = self.env.context.get('active_id') or self.env.context.get('id')
            if active_id:
                rec = self.browse(active_id)
                if rec and rec.state in ('pending', 'approved', 'rejected'):
                    doc = etree.XML(res['arch'])
                    form = doc.xpath("//form")
                    if form:
                        form[0].set('edit', 'false')
                        form[0].set('create', 'false')
                        form[0].set('delete', 'false')
                    res['arch'] = etree.tostring(doc, encoding='unicode')
        return res
