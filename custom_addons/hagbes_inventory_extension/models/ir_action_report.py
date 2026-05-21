from odoo import models, api

class ReportCustomPicking(models.AbstractModel):
    _name = 'report.hagbes_inventory_extension.report_custom_picking'
    _description = 'Custom Picking Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['stock.picking'].browse(docids)  # your documents
        company = self.env.company  # current user's company record
        return {
            'doc_ids': docids,
            'doc_model': 'stock.picking',
            'docs': docs,
            'company': company,  # make sure it's a record
        }


