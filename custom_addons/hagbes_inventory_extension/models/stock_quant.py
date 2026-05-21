from email.policy import default

from odoo import models, fields,api
from odoo.exceptions import UserError

class StockQuant(models.Model):
    _inherit = 'stock.quant'

    needs_review = fields.Boolean(string="Needs Review", compute="_compute_needs_review", store=True, default=False)
    remark = fields.Text(string="Remark",default="")
    difference_justification = fields.Text(string="Justification",help="Counting Difference Justification",default="")
    adjustment_count = fields.Integer(string="Adjustment Count", default=0,store=True)
    review_confirmed_by = fields.Many2one('res.users', string="Reviewed By", readonly=True)
    count_confirmed_by = fields.Many2one('res.users', string="Confirmed By", readonly=True)
    review_confirmed_date = fields.Datetime(string="Confirmed On", readonly=True)
    
    can_edit_remark = fields.Boolean(compute='_compute_can_edit_remark', default=False)

    @api.depends_context('uid')
    def _compute_can_edit_remark(self):
        for record in self:
            record.can_edit_remark = self.env.user.has_group('hagbes_inventory_extension.group_custom_approve_adjustment')

    can_edit_inventory_quantity = fields.Boolean(compute='_compute_can_edit_inventory_quantity', default=False)

    @api.depends_context('uid')
    def _compute_can_edit_inventory_quantity(self):
        for record in self:
            record.can_edit_inventory_quantity = self.env.user.has_group('hagbes_inventory_extension.group_custom_count_team')

    can_edit_justification = fields.Boolean(compute='_compute_can_edit_justification', default=False)

    @api.depends_context('uid')
    def _compute_can_edit_justification(self):
        for record in self:
            record.can_edit_justification = self.env.user.has_group('hagbes_inventory_extension.group_custom_warehouse_manager')

    status = fields.Selection(
        string="Status",
        selection=[('pending', 'Not Counted'),('counted', 'Counted'), ('recounted', 'Recounted'),('reviewed', 'Count Reviewed'),('confirmed', 'Count Confirmed')],
        store=True,
        default="pending"
    )
    product_default_code = fields.Char(
        string='Part Number',
        related='product_id.default_code',
        store=False,  # or True if you want it stored and searchable

    )
    product_name_only = fields.Char(
        string="Product Name",
        related='product_id.name',
        store=False,
    )

    product_sales_price = fields.Float(
        string="Sales Price",
        related='product_id.list_price',
        readonly=True
    )

    interchable_number = fields.One2many(
        'product.interchange',
        string="Interchangeable Numbers",
        related='product_id.interchangeable_number_ids',

    )

    user_id = fields.Many2one(
        'res.users',
        string='Assigned To',
        help="User assigned to do product count.",
        default=lambda self: self.env.user
    )

    def action_apply_inventory(self):
        self = self.with_context(allow_quant_creation=True)
        res = super(StockQuant, self).action_apply_inventory()
        self.write({
            'status': 'confirmed',
            'count_confirmed_by': self.env.user.id
        })
        return res

    @api.depends("inventory_quantity")
    def _compute_needs_review(self):
        for quant in self:
            quant.needs_review = (quant.inventory_quantity and quant.inventory_quantity != quant.quantity)
            self.status = 'counted'
    def action_review_difference(self):
        return {
            'name': 'Review Stock Differences',
            'type': 'ir.actions.act_window',
            'res_model': 'stock.quant',
            'view_mode': 'list',
            'views': [
                (self.env.ref('hagbes_inventory_extension.stock_quant_tree_inherit_open_template').id, 'list'),
            ],
            'domain': [('needs_review', '=', True)],
            'context': dict(self.env.context, allow_quant_creation=True),
        }

    def action_stock_adjustment(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Adjust Stock',
            'res_model': 'stock.adjust.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_quant_ids': [(6, 0, self.ids)],
            }
        }

    @api.onchange('difference_justification')
    def _onchange_difference_justification(self):
        if self.difference_justification:
            self.status = 'recounted'
    def action_all_history(self):
        action = super().action_view_inventory()
        # ➤ Add domain to show only quants with no difference
        domain = action.get("domain", [])
        domain += [
            ('status', 'in', ['confirmed', 'reviewed']),
        ]
        action["domain"] = domain
        return action

    def action_view_inventory(self):
        action = super().action_view_inventory()
        domain = action.get("domain", [])

        # Check if the user has the 'approve_inventory' group
        approve_group = self.env.ref('hagbes_inventory_extension.group_custom_verify_difference')
        if approve_group in self.env.user.groups_id:
            # Show only quants that need approval (difference exists)
            domain += [('status', 'in', ['recounted', 'reviewed'])]
        else:
            # For other users, show everything except confirmed
            pass

        action["domain"] = domain
        return action

    def action_difference_justification(self):
        for rec in self:
            if not rec.difference_justification:
                raise UserError("Please provide a justification before proceeding.")
            if rec.status == 'confirmed':
                raise UserError("Confirmed records cannot be modified.")

            rec.write({
                'status': 'reviewed',
                'review_confirmed_by': self.env.user.id,
            })
        return True

    def action_reset_line(self):
        for rec in self:
            if rec.status != 'confirmed':
                raise UserError("Only confirmed records can be reset.")

            rec.write({
                'remark': False,
                'review_confirmed_by': False,
                'count_confirmed_by': False,
                'difference_justification': False,
                'status': 'pending',  # reset status to initial
            })

    def action_reset_all(self):
        for rec in self:
            if rec.status != 'confirmed':
                raise UserError("Only confirmed records can be reset.")
            rec.write({
                'remark': False,
                'review_confirmed_by': False,
                'count_confirmed_by': False,
                'difference_justification': False,
                'status': 'pending',  # reset status to initial
            })

    def _get_inventory_fields_create(self):
        allowed_fields = super()._get_inventory_fields_create()
        allowed_fields += [
            'difference_justification',
            'remark',
            'status',
            'review_confirmed_by',
            'count_confirmed_by',
            'user_id',
        ]
        return allowed_fields
