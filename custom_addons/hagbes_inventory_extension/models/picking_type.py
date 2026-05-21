from odoo import models, fields, api

class StockPickingType(models.Model):
    _inherit = 'stock.picking.type'

    code = fields.Selection(
        selection_add=[
            ('exhibition_request', 'Exhibition Request'),
            ('exhibition_receive', 'Exhibition Receive'),
            ('mrcv', 'Material Receipt collection Voucher (MRCV)'),
            ('mrv', 'Material Receipt Voucher (MRV)'),
            ('internal_issue', 'Internal Issue')
        ],
        ondelete={
            'exhibition_request': 'set default',
            'exhibition_receive': 'set default',
            'mrcv': 'set default',
            'mrv': 'set default',
            'internal_issue': 'set default'
        }
    )

    count_internal_issue = fields.Integer(string="Internal Issue Count", compute="_compute_issue_counts")
    count_exhibition_issue = fields.Integer(string="Exhibition Count", compute="_compute_issue_counts")
    count_inter_store_issue = fields.Integer(string="Inter Store Count", compute="_compute_issue_counts")
    count_mrcv = fields.Integer(string="MRCV Count", compute="_compute_issue_counts")
    count_mrv = fields.Integer(string="MRV Count", compute="_compute_issue_counts")

    new_count_internal_issue = fields.Integer(string="Internal Issue Count", default=0)
    new_count_exhibition_issue = fields.Integer(string="Exhibition Count", default=0)
    new_count_inter_store_issue = fields.Integer(string="Inter Store Count", default=0)

    @api.depends('code')
    def _compute_show_picking_type(self):
        for record in self:
            # Include standard picking types + custom ones
            record.show_picking_type = record.code in [
                'incoming',
                'exhibition_request',
                'outgoing',
                'internal',  # Standard internal transfer
                'exhibition_receive',  # Your custom picking type
                'internal_issue',  # Internal issue type
                'mrcv',
                'mrv',
            ]

    @api.depends('code')
    def _compute_issue_counts(self):
        for picking_type in self:
            domain_base = [('picking_type_id', '=', picking_type.id)]
            picking_type.count_internal_issue = self.env['stock.picking'].search_count(domain_base + [('internal_issue', '=', True)])
            picking_type.count_exhibition_issue = self.env['stock.picking'].search_count(domain_base + [('exhibition_issue', '=', True)])
            picking_type.count_inter_store_issue = self.env['stock.picking'].search_count(domain_base + [('inter_store_issue', '=', True)])
            picking_type.count_mrcv = self.env['stock.picking'].search_count(domain_base + [('mrcv_issue', '=', True)])
            picking_type.count_mrv = self.env['stock.picking'].search_count(domain_base + [('mrv_issue', '=', True)])
