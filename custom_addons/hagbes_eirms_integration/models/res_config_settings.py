# models/res_config_settings.py
from odoo import fields, models

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    mor_client_id = fields.Char(string="MOR Client ID")
    mor_client_secret = fields.Char(string="MOR Client Secret")
    mor_api_key = fields.Char(string="MOR API Key")
    mor_seller_tin = fields.Char(string="MOR Seller TIN")

    def get_values(self):
        res = super().get_values()
        ICP = self.env['ir.config_parameter'].sudo()
        res.update(
            mor_client_id = ICP.get_param('mor.client_id', default=''),
            mor_client_secret = ICP.get_param('mor.client_secret', default=''),
            mor_api_key = ICP.get_param('mor.api_key', default=''),
            mor_seller_tin = ICP.get_param('mor.seller_tin', default=''),
        )
        return res

    def set_values(self):
        super().set_values()
        ICP = self.env['ir.config_parameter'].sudo()
        ICP.set_param('mor.client_id', self.mor_client_id or '')
        ICP.set_param('mor.client_secret', self.mor_client_secret or '')
        ICP.set_param('mor.api_key', self.mor_api_key or '')
        ICP.set_param('mor.seller_tin', self.mor_seller_tin or '')
