from odoo import models, fields, api

class StockMoveLineInherit(models.Model):
    _inherit = "stock.move.line"

    display_quantity = fields.Float(
        string="In/Out Quantity",
        compute="_compute_display_quantity",
        store=True
    )

    move_type = fields.Char(
        string="Move Type",
        compute="_compute_moves_types",
        store=True
    )
    location_group_ids = fields.Many2many(
        'stock.location',
        compute='_compute_location_group_ids',
        string='Locations for Grouping',
        store=True
    )

    @api.depends('location_id', 'location_dest_id')
    def _compute_location_group_ids(self):
        for line in self:
            line.location_group_ids = [(6, 0, filter(None, [line.location_id.id, line.location_dest_id.id]))]

    @api.depends('quantity', 'location_id', 'location_dest_id')
    def _compute_display_quantity(self):
        for record in self:

            # Special rule: Inventory → MRCV must always be OUT/negative
            if (record.location_id.usage == 'internal'
                    and record.location_dest_id.usage == 'transit'
                    and 'mrcv' in (record.location_dest_id.name or '').lower()):
                record.display_quantity = -abs(record.quantity)
                continue

            # Default Outflow → negative
            if (record.location_id.usage in ('internal', 'transit')
                    and record.location_dest_id.usage not in ('internal', 'transit')):
                record.display_quantity = -abs(record.quantity)
            else:
                # Default Inflow → positive
                record.display_quantity = abs(record.quantity)

    @api.depends('quantity', 'location_id', 'location_dest_id')
    def _compute_moves_types(self):
        for record in self:

            # 1. Custom rule: Inventory → MRCV must be OUT
            if (record.location_id.usage == 'internal'
                    and record.location_dest_id.usage == 'transit'
                    and 'mrcv' in record.location_dest_id.name.lower()):
                record.move_type = "OUT"
                continue  # stop here, do not evaluate next rules

            # 2. Default rule: Outflow → negative
            if record.location_id.usage in ('internal', 'transit') and record.location_dest_id.usage not in ('internal',
                                                                                                             'transit'):
                record.move_type = "OUT"
            else:
                # 3. Default inflow → positive
                record.move_type = "IN"
