from odoo import _, models, fields, api, exceptions
from odoo.exceptions import UserError,ValidationError
from odoo.tools.float_utils import float_compare

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    branch_id = fields.Many2one(
        'account.analytic.account',
        string='Branch',
        domain=lambda self: self._get_branch_domain(),
        required=True
    )
    state = fields.Selection(selection_add=[('lost', 'Lost')])
    warehouse_id = fields.Many2one(
        'stock.warehouse',
        string='Warehouse',
        required=True
    )
    job_number = fields.Char(string="Job Number")
    serial_number = fields.Char(string="Serial Number")
    plate_number = fields.Char(string="Plate Number")
    model_name = fields.Char(string="Model")
    
    origin_type = fields.Selection(
        [
            ('direct', 'Direct Sales'),
            ('service', 'Service'),
            ('tender', 'Tender'),
        ],
        string="Origin",
        compute="_compute_origin_type",
        store=True  
    )
    display_partner_vat = fields.Char(
        string="VAT",
        related='partner_id.vat',
        readonly=True,
        store=False 
    )

    display_partner_tin_number = fields.Char(
        string="TIN",
        related='partner_id.tin_number',
        readonly=True,
        store=False
    )
    employee_partner_ids = fields.Many2many(
        'res.partner',
        compute='_compute_employee_partner_ids',
        store=False
    )

    @api.depends()
    def _compute_employee_partner_ids(self):
        employees = self.env['hr.employee'].search([])
        partners = employees.mapped('user_id.partner_id')
        for record in self:
            record.employee_partner_ids = partners
    @api.depends('job_number')
    def _compute_origin_type(self):
        for order in self:
            if order.job_number:
                order.origin_type = 'service'
            else:
                order.origin_type = 'direct'
  

    def _check_empty_order_line(self):
        for order in self:
            if not order.order_line:
                raise ValidationError("You must add at least one product to the sales order before saving.")
            
    @api.onchange('branch_id')
    def _onchange_branch_id(self):
        domain = {'warehouse_id': []}
        if self.branch_id:
            # Find warehouses linked to this branch
            warehouses = self.env['stock.warehouse'].search([('branch_id', '=', self.branch_id.id)])
            domain['warehouse_id'] = [('id', 'in', warehouses.ids)]
            if warehouses:
                # Prefer the first warehouse as default
                self.warehouse_id = warehouses[0]
            else:
                self.warehouse_id = False
                # Optional: show a warning (note: onchange warnings are client-side only in modern Odoo)
                return {
                    'warning': {
                        'title': _("No Warehouse Found"),
                        'message': _("There is no warehouse assigned to this branch. Please assign one in Warehouse settings.")
                    }
                }
        else:
            self.warehouse_id = False
        return {'domain': domain}
    def _get_branch_domain(self):
        user = self.env.user
        return [('id', 'in', user.allowed_branch_ids.ids)]



    @api.model
    def create(self, vals):
        self._check_pricelist_permission(vals)
        return super().create(vals)

    def write(self, vals):
        self._check_pricelist_permission(vals)
        return super().write(vals)

    def _check_pricelist_permission(self, vals):
        user = self.env.user
        if 'pricelist_id' in vals and not user.has_group('sales_team.group_sale_manager'):
            raise exceptions.AccessError("You are not allowed to change the Pricelist.")

