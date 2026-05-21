from odoo import models,fields

class BaseDocumentLayout(models.TransientModel):
    _inherit = 'base.document.layout'

    tin_number = fields.Char(related='company_id.tin_number', readonly=True)