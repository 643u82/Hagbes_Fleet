import logging
import requests 
from odoo import api, models, fields, _
from odoo.exceptions import ValidationError

_logger =logging.getLogger(__name__)

class AccountMove (models.Model):
    _inherit = 'account.move'

    def action_open_cancel_wizard(self):
        self.ensure_one()
        return  {
            'name':"Cancel Invoice",
            'type' : "ir.actions.act_window",
            'res_model': 'account.move.cancel.wizard',
            'view_mode':'form',
            'target':'new',
            'context': {'default_invoice_id':self.id},
        }

