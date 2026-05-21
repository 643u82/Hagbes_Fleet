from odoo import models, fields

class SuccessMessageWizard(models.TransientModel):
    _name = 'success.message.wizard'
    _description = 'Success Message Wizard'

    message = fields.Text(string="Message", readonly=True)
