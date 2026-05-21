from odoo import models, fields


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Example field - replace with actual fields
    module_crud_logger = fields.Boolean(
        string='Enable CRUD Logger',
        help="Enable logging of CRUD operations"
    )