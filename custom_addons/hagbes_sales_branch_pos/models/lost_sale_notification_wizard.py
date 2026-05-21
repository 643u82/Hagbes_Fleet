from odoo import models, fields

class LostSaleNotificationWizard(models.TransientModel):
    _name = 'lost.sale.notification.wizard'
    _description = 'Lost Sale Notification Wizard'

    message = fields.Text(readonly=True, default="All requested products are unavailable. The order has been marked as a lost sale.")