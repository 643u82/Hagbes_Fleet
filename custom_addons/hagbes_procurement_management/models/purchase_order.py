from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    state = fields.Selection(selection_add=[
        ('transit_done', 'Transit Done'),
        ('purchase',),
    ], ondelete={'transit_done': 'cascade'})

    document_order_number = fields.Char(
        string="Document Order Number",
        help="Reference number for the PO documents"
    )
    
    branch_id = fields.Many2one(
        'account.analytic.account',
        string='Branch',
        domain="[('plan_id.name', '=', 'Branch'), ('company_id', '=', company_id)]",
        help="The branch associated with this purchase order.",
        tracking=True,
        required=True,
        readonly=True
    )

    purchase_request_id = fields.Many2one(
        'purchase.request',
        string='Purchase Request',
        help='Purchase request that generated this order',
        tracking=True
    )
    local_purchase_request_id = fields.Many2one(
        'local.purchase.request',
        string='Local Purchase Request',
        help='Local Purchase request that generated this order',
        tracking=True
    )
    request_overall_status = fields.Char(
        string="Request Status",
        related="purchase_request_id.overall_status",
        store=False,
        readonly=True,
        help="The overall status of the originating Purchase Request."
    )
    
    order_type = fields.Selection(
        selection=[
            ('local', 'Local'),
            ('foreign', 'Foreign'),
        ],
        string="Order Type",
        default='foreign',
        help="Automatically set as 'Local' or 'Foreign' based on vendor's country."
    )
    
    # Currency and Exchange Rate Fields
    foreign_currency_id = fields.Many2one(
        'res.currency',
        string='Foreign Currency',
        help="Currency of the foreign supplier",
        tracking=True
    )
    
    local_currency_id = fields.Many2one(
        'res.currency',
        related='company_id.currency_id',
        readonly=True,
        help="Company's local currency"
    )
    
    exchange_rate = fields.Float(
        string='Exchange Rate',
        digits=(12, 6),
        default=1.0,
        help="Exchange rate from foreign currency to local currency (1 Foreign = X Local)",
        tracking=True
    )
    
    exchange_rate_date = fields.Date(
        string='Exchange Rate Date',
        default=fields.Date.context_today,
        help="Date for which the exchange rate is applicable"
    )
    
    # Total amounts in both currencies
    amount_total_local = fields.Monetary(
        string='Total (Local Currency)',
        compute='_compute_local_amounts',
        currency_field='local_currency_id',
        store=True,
        help="Total amount in local currency"
    )
    
    procurement_method = fields.Selection([
        ('direct', 'Direct Purchase'),
        ('lc', 'Letter of Credit'),
        ('advance', 'Advance Payment'),
    ], string='Procurement Method', tracking=True)
    
    incoterm_id = fields.Many2one(
        'account.incoterms',
        string='Incoterm',
        help='International Commercial Terms for international transactions.'
    )
    
    port_of_loading = fields.Char(string='Port of Loading')
    port_of_discharge = fields.Char(string='Port of Discharge')
    estimated_shipping_date = fields.Date(string='Estimated Shipping Date')
    estimated_arrival_date = fields.Date(string='Estimated Arrival Date')
    
    payment_request_ids = fields.One2many('foreign.payment.request', 'purchase_order_id', string='Payment Requests')
    lc_ids = fields.One2many('foreign.lc', 'purchase_order_id', string='Letters of Credit')
    shipment_ids = fields.One2many('foreign.shipment', 'purchase_order_id', string='Shipment Records')
    landing_ids = fields.One2many('foreign.landing', 'purchase_order_id', string='Landing Records')
    costing_ids = fields.One2many('foreign.costing', 'purchase_order_id', string='Costing Records')
    transit_process_ids = fields.One2many('foreign.transit.process', 'purchase_order_id', string='Transit Processes')
    bank_process_ids = fields.One2many('foreign.bank.process', 'purchase_order_id', string='Bank Processes')
    
    payment_request_count = fields.Integer(compute='_compute_related_counts', string='Payment Request Count')
    lc_count = fields.Integer(compute='_compute_related_counts', string='LC Count')
    shipment_count = fields.Integer(compute='_compute_related_counts', string='Shipment Count')
    landing_count = fields.Integer(compute='_compute_related_counts', string='Landing Count')
    costing_count = fields.Integer(compute='_compute_related_counts', string='Costing Count')
    
    foreign_procurement_state = fields.Selection([
        ('draft', 'Draft'),
        ('quotation_received', 'Quotation Received'),
        ('lc_processing', 'LC Processing'),
        ('goods_shipped', 'Goods Shipped'),
        ('goods_arrived', 'Goods Arrived'),
        ('customs_clearance', 'Customs Clearance'),
        ('completed', 'Completed'),
    ], string='Foreign Procurement Status', default='draft', tracking=True)
    
    costing_state = fields.Char(
        string="Costing Status",
        compute='_compute_related_process_states',
        store=True
    )
    transit_state = fields.Char(
        string="Transit Status",
        compute='_compute_related_process_states',
        store=True
    )
    bank_process_state = fields.Char(
        string="Bank Process Status",
        compute='_compute_related_process_states',
        store=True
    )

    total_landed_cost = fields.Monetary(
        string='Total Landed Cost',
        compute='_compute_total_landed_cost',
        currency_field='currency_id',
        store=True,
        help="Total cost including purchase price, shipping, duties, and other charges"
    )

    @api.constrains('state', 'order_line')
    def _check_order_lines(self):
        """Ensure at least one product line exists when confirming order"""
        for order in self:
            if order.state in ['purchase', 'done'] and not order.order_line:
                raise ValidationError(_("You cannot confirm a purchase order without at least one product line."))

    def button_confirm(self):
        """Override to add validation before confirming"""
        for order in self:
            if not order.order_line:
                raise UserError(_("You cannot confirm a purchase order without at least one product line. Please add products to continue."))
            if not order.document_order_number:
                # We can auto-generate a generic one if missing, or require it. For manual confirm, let's require it or auto-fill.
                # Actually, let's auto-fill if foreign, otherwise require.
                if order.order_type == 'foreign':
                    order.document_order_number = f"DOC-{order.name}"
                else:
                    raise UserError(_("Please provide the Document Order Number before confirming the order."))
        return super(PurchaseOrder, self).button_confirm()

    @api.onchange('branch_id')
    def _onchange_branch_id(self):
        if self.branch_id and self.branch_id.company_id and self.branch_id.company_id != self.company_id:
            self.company_id = self.branch_id.company_id
        elif not self.branch_id and self.env.user.company_id:
            self.company_id = self.env.user.company_id

    # Currency and Exchange Rate Methods
    @api.onchange('order_type')
    def _onchange_order_type(self):
        if self.order_type == 'foreign':
            if not self.procurement_method:
                self.procurement_method = 'lc'
            # Set foreign currency from partner if available
            if self.partner_id and self.partner_id.property_purchase_currency_id:
                self.foreign_currency_id = self.partner_id.property_purchase_currency_id
                self.currency_id = self.foreign_currency_id
        else:
            self.procurement_method = False
            self.foreign_procurement_state = False
            self.foreign_currency_id = False
            self.currency_id = self.company_id.currency_id

    @api.onchange('foreign_currency_id', 'exchange_rate_date')
    def _onchange_currency_exchange_rate(self):
        """Auto-compute exchange rate when currency or date changes"""
        if self.foreign_currency_id and self.local_currency_id and self.exchange_rate_date:
            if self.foreign_currency_id != self.local_currency_id:
                rate = self.foreign_currency_id._get_conversion_rate(
                    self.foreign_currency_id,
                    self.local_currency_id,
                    self.company_id,
                    self.exchange_rate_date
                )
                self.exchange_rate = rate
                self.currency_id = self.foreign_currency_id
            else:
                self.exchange_rate = 1.0
                self.currency_id = False  # When currencies are the same, set exchange rate to 1 and make it inactive

    @api.depends('amount_total', 'exchange_rate', 'foreign_currency_id', 'order_type')
    def _compute_local_amounts(self):
        for order in self:
            if order.order_type == 'foreign' and order.foreign_currency_id and order.exchange_rate:
                order.amount_total_local = order.amount_total * order.exchange_rate
            else:
                order.amount_total_local = order.amount_total

    @api.depends('partner_id', 'partner_id.country_id', 'company_id.country_id')
    def _compute_order_type(self):
        for order in self:
            vendor_country = order.partner_id.country_id if order.partner_id else False
            company_country = order.company_id.country_id if order.company_id else False
            if vendor_country and company_country:
                order.order_type = 'local' if vendor_country.id == company_country.id else 'foreign'
            else:
                order.order_type = 'local'

    @api.depends('payment_request_ids', 'lc_ids', 'shipment_ids', 'landing_ids')
    @api.depends('payment_request_ids', 'lc_ids', 'shipment_ids', 'costing_ids')
    def _compute_related_counts(self):
        for order in self:
            order.payment_request_count = len(order.payment_request_ids)
            order.lc_count = len(order.lc_ids)
            order.shipment_count = len(order.shipment_ids)
            order.landing_count = len(order.landing_ids)
            order.costing_count = len(order.costing_ids)

    @api.depends('amount_total', 'landing_ids.total_landing_cost')
    @api.depends('amount_total', 'costing_ids.total_landed_cost_fx')
    def _compute_total_landed_cost(self):
        for order in self:
            landing_costs = sum(landing.total_landing_cost for landing in order.landing_ids)
            landing_costs = sum(costing.total_landed_cost_fx for costing in order.costing_ids)
            order.total_landed_cost = order.amount_total + landing_costs

    @api.depends('costing_ids.state', 'transit_process_ids.state', 'bank_process_ids.state')
    def _compute_related_process_states(self):
        for order in self:
            costing = order.costing_ids and order.costing_ids[0]
            order.costing_state = dict(costing._fields['state'].selection).get(costing.state) if costing else ''
            transit = order.transit_process_ids and order.transit_process_ids[0]
            order.transit_state = dict(transit._fields['state'].selection).get(transit.state) if transit else ''
            bank_process = order.bank_process_ids and order.bank_process_ids[0]
            order.bank_process_state = dict(bank_process._fields['state'].selection).get(bank_process.state) if bank_process else ''

    # ... existing action methods remain unchanged ...
    def action_create_payment_request(self):
        return {
            'name': _('Create Payment Request'),
            'type': 'ir.actions.act_window',
            'res_model': 'foreign.payment.request',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_purchase_order_id': self.id,
                'default_supplier_id': self.partner_id.id,
                'default_currency_id': self.currency_id.id,
                'default_branch_id': self.branch_id.id,
            }
        }

    def action_create_lc(self):
        if self.order_type != 'foreign':
            raise UserError(_("Letter of Credit can only be created for foreign orders."))
        return {
            'name': _('Create Letter of Credit'),
            'type': 'ir.actions.act_window',
            'res_model': 'foreign.lc',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_purchase_order_id': self.id,
                'default_lc_amount': self.amount_total,
                'default_currency_id': self.currency_id.id,
            }
        }

    def action_create_shipment(self):
        return {
            'name': _('Create Shipment'),
            'type': 'ir.actions.act_window',
            'res_model': 'foreign.shipment',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_purchase_order_id': self.id,
                'default_port_of_loading': self.port_of_loading,
                'default_port_of_discharge': self.port_of_discharge,
            }
        }

    def action_create_landing(self):
        return {
            'name': _('Create Landing Process'),
            'type': 'ir.actions.act_window',
            'res_model': 'foreign.costing',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_purchase_order_id': self.id,
            }
        }

    def action_view_payment_requests(self):
        return {
            'name': _('Payment Requests'),
            'type': 'ir.actions.act_window',
            'res_model': 'foreign.payment.request',
            'view_mode': 'list,form',
            'domain': [('purchase_order_id', '=', self.id)],
            'context': {'default_purchase_order_id': self.id}
        }

    def action_view_lcs(self):
        return {
            'name': _('Letters of Credit'),
            'type': 'ir.actions.act_window',
            'res_model': 'foreign.lc',
            'view_mode': 'tree,form',
            'domain': [('purchase_order_id', '=', self.id)],
            'context': {'default_purchase_order_id': self.id}
        }

    def action_view_shipments(self):
        return {
            'name': _('Shipments'),
            'type': 'ir.actions.act_window',
            'res_model': 'foreign.shipment',
            'view_mode': 'list,form',
            'domain': [('purchase_order_id', '=', self.id)],
            'context': {'default_purchase_order_id': self.id}
        }

    def action_view_costing(self):
        return {
            'name': _('Costing Processes'),
            'type': 'ir.actions.act_window',
            'res_model': 'foreign.costing',                                                             
            'view_mode': 'list,form',
            'domain': [('purchase_order_id', '=', self.id)],
            'context': {'default_purchase_order_id': self.id}
        }

    def action_view_purchase_request(self):
        self.ensure_one()
        return {
            'name': _('Purchase Request'),
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.request',
            'view_mode': 'form',
            'res_id': self.purchase_request_id.id,
            'target': 'current',
        }

    @api.model
    def create(self, vals):
        if vals.get('branch_id') and (not vals.get('name') or vals.get('name') == 'New'):
            branch = self.env['account.analytic.account'].browse(vals['branch_id'])
            branch_code = branch.code or '00'
            year = datetime.now().year
            # Use base sequence
            seq = self.env['ir.sequence'].next_by_code('purchase.order')
            # Compose name manually
            vals['name'] = f"P{branch_code}{year}{seq[-5:]}"  # last 5 digits from seq padding
        return super(PurchaseOrder, self).create(vals)


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'
    
    product_id = fields.Many2one(
        'product.product',
        string='Product',
    )
    
    hs_code = fields.Char(string='HS Code', help='Harmonized System Code for customs classification')
    country_of_origin = fields.Many2one('res.country', string='Country of Origin')
    
    # Price fields in both currencies
    price_unit_local = fields.Monetary(
        string='Unit Price (Local)',
        compute='_compute_local_prices',
        currency_field='local_currency_id',
        store=True,
        help='Unit price in local currency'
    )
    
    price_subtotal_local = fields.Monetary(
        string='Subtotal (Local)',
        compute='_compute_local_prices',
        currency_field='local_currency_id',
        store=True,
        help='Subtotal in local currency'
    )
    
    local_currency_id = fields.Many2one(
        'res.currency',
        related='order_id.local_currency_id',
        string='Local Currency'
    )
    
    landed_cost_allocated = fields.Monetary(
        string='Allocated Landed Cost',
        currency_field='currency_id',
        help='Portion of total landed costs allocated to this line'
    )
    
    total_cost_per_unit = fields.Monetary(
        string='Total Cost per Unit',
        compute='_compute_total_cost_per_unit',
        currency_field='currency_id',
        help='Unit price including allocated landed costs'
    )

    @api.depends('price_unit', 'order_id.exchange_rate', 'price_subtotal', 'order_id.order_type', 'order_id.foreign_currency_id')
    def _compute_local_prices(self):
        for line in self:
            if line.order_id.order_type == 'foreign' and line.order_id.exchange_rate and line.order_id.foreign_currency_id:
                line.price_unit_local = line.price_unit * line.order_id.exchange_rate
                line.price_subtotal_local = line.price_subtotal * line.order_id.exchange_rate
            else:
                # For local orders, local prices are the same as regular prices
                line.price_unit_local = line.price_unit
                line.price_subtotal_local = line.price_subtotal

    @api.depends('price_unit', 'landed_cost_allocated', 'product_qty')
    def _compute_total_cost_per_unit(self):
        for line in self:
            if line.product_qty:
                line.total_cost_per_unit = line.price_unit + (line.landed_cost_allocated / line.product_qty)
            else:
                line.total_cost_per_unit = line.price_unit

    @api.model
    def _prepare_account_move_line(self, move=False):
        res = super()._prepare_account_move_line(move)
        if self.order_id.branch_id:
            branch = self.order_id.branch_id
            analytic_distribution = {str(branch.id): 100.0}
            if 'analytic_distribution' not in res or not res['analytic_distribution']:
                res['analytic_distribution'] = analytic_distribution
        return res







# ==========================================================================================================================


# from odoo import api, fields, models, _
# from odoo.exceptions import UserError
# from datetime import datetime

# class PurchaseOrder(models.Model):
#     _inherit = 'purchase.order'
    
#     branch_id = fields.Many2one(
#         'account.analytic.account',
#         string='Branch',
#         domain="[('plan_id.name', '=', 'Branch'), ('company_id', '=', company_id)]",
#         help="The branch associated with this purchase order.",
#         tracking=True,
#         required=True,
#     )
    
#     order_type = fields.Selection(
#         selection=[
#             ('local', 'Local'),
#             ('foreign', 'Foreign'),
#         ],
#         string="Order Type",
#         default='foreign',
#         help="Automatically set as 'Local' or 'Foreign' based on vendor's country."
#     )
    
#     # NEW: Currency and Exchange Rate Fields
#     foreign_currency_id = fields.Many2one(
#         'res.currency',
#         string='Foreign Currency',
#         help="Currency of the foreign supplier",
#         tracking=True
#     )
    
#     local_currency_id = fields.Many2one(
#         'res.currency',
#         string='Local Currency',
#         related='company_id.currency_id',
#         readonly=True,
#         help="Company's local currency"
#     )
    
#     exchange_rate = fields.Float(
#         string='Exchange Rate',
#         digits=(12, 6),
#         default=1.0,
#         help="Exchange rate from foreign currency to local currency (1 Foreign = X Local)",
#         tracking=True
#     )
    
#     exchange_rate_date = fields.Date(
#         string='Exchange Rate Date',
#         default=fields.Date.context_today,
#         help="Date for which the exchange rate is applicable"
#     )
    
#     # NEW: Total amounts in both currencies
#     amount_total_local = fields.Monetary(
#         string='Total (Local Currency)',
#         compute='_compute_local_amounts',
#         currency_field='local_currency_id',
#         store=True,
#         help="Total amount in local currency"
#     )
    
#     procurement_method = fields.Selection([
#         ('direct', 'Direct Purchase'),
#         ('lc', 'Letter of Credit'),
#         ('advance', 'Advance Payment'),
#     ], string='Procurement Method', tracking=True)
    
#     incoterm_id = fields.Many2one(
#         'account.incoterms',
#         string='Incoterm',
#         help='International Commercial Terms for international transactions.'
#     )
    
#     port_of_loading = fields.Char(string='Port of Loading')
#     port_of_discharge = fields.Char(string='Port of Discharge')
#     estimated_shipping_date = fields.Date(string='Estimated Shipping Date')
#     estimated_arrival_date = fields.Date(string='Estimated Arrival Date')
    
#     payment_request_ids = fields.One2many('foreign.payment.request', 'purchase_order_id', string='Payment Requests')
#     lc_ids = fields.One2many('foreign.lc', 'purchase_order_id', string='Letters of Credit')
#     shipment_ids = fields.One2many('foreign.shipment', 'purchase_order_id', string='Shipment Records')  # Changed label
#     landing_ids = fields.One2many('foreign.landing', 'purchase_order_id', string='Landing Records')  # Changed label
    
#     payment_request_count = fields.Integer(compute='_compute_related_counts', string='Payment Request Count')
#     lc_count = fields.Integer(compute='_compute_related_counts', string='LC Count')
#     shipment_count = fields.Integer(compute='_compute_related_counts', string='Shipment Count')  # Changed label
#     landing_count = fields.Integer(compute='_compute_related_counts', string='Landing Count')  # Changed label
    
#     foreign_procurement_state = fields.Selection([
#         ('draft', 'Draft'),
#         ('quotation_received', 'Quotation Received'),
#         ('lc_processing', 'LC Processing'),
#         ('goods_shipped', 'Goods Shipped'),
#         ('goods_arrived', 'Goods Arrived'),
#         ('customs_clearance', 'Customs Clearance'),
#         ('completed', 'Completed'),
#     ], string='Foreign Procurement Status', default='draft', tracking=True)
    
#     total_landed_cost = fields.Monetary(
#         string='Total Landed Cost',
#         compute='_compute_total_landed_cost',
#         currency_field='currency_id',
#         store=True,
#         help="Total cost including purchase price, shipping, duties, and other charges"
#     )

#     @api.onchange('branch_id')
#     def _onchange_branch_id(self):
#         if self.branch_id and self.branch_id.company_id and self.branch_id.company_id != self.company_id:
#             self.company_id = self.branch_id.company_id
#         elif not self.branch_id and self.env.user.company_id:
#             self.company_id = self.env.user.company_id

#     # NEW: Currency and Exchange Rate Methods
#     @api.onchange('order_type')
#     def _onchange_order_type(self):
#         if self.order_type == 'foreign':
#             if not self.procurement_method:
#                 self.procurement_method = 'lc'
#             # Set foreign currency from partner if available
#             if self.partner_id and self.partner_id.property_purchase_currency_id:
#                 self.foreign_currency_id = self.partner_id.property_purchase_currency_id
#                 self.currency_id = self.foreign_currency_id
#         else:
#             self.procurement_method = False
#             self.foreign_procurement_state = False
#             self.foreign_currency_id = False
#             self.currency_id = self.company_id.currency_id

#     @api.onchange('foreign_currency_id', 'exchange_rate_date')
#     def _onchange_currency_exchange_rate(self):
#         """Auto-compute exchange rate when currency or date changes"""
#         if self.foreign_currency_id and self.local_currency_id and self.exchange_rate_date:
#             if self.foreign_currency_id != self.local_currency_id:
#                 rate = self.foreign_currency_id._get_conversion_rate(
#                     self.foreign_currency_id,
#                     self.local_currency_id,
#                     self.company_id,
#                     self.exchange_rate_date
#                 )
#                 self.exchange_rate = rate
#                 self.currency_id = self.foreign_currency_id
#             else:
#                 self.exchange_rate = 1.0

#     @api.depends('amount_total', 'exchange_rate', 'foreign_currency_id')
#     def _compute_local_amounts(self):
#         for order in self:
#             if order.foreign_currency_id and order.exchange_rate:
#                 order.amount_total_local = order.amount_total * order.exchange_rate
#             else:
#                 order.amount_total_local = order.amount_total

#     @api.depends('partner_id', 'partner_id.country_id', 'company_id.country_id')
#     def _compute_order_type(self):
#         for order in self:
#             vendor_country = order.partner_id.country_id if order.partner_id else False
#             company_country = order.company_id.country_id if order.company_id else False
#             if vendor_country and company_country:
#                 order.order_type = 'local' if vendor_country.id == company_country.id else 'foreign'
#             else:
#                 order.order_type = 'local'

#     @api.depends('payment_request_ids', 'lc_ids', 'shipment_ids', 'landing_ids')
#     def _compute_related_counts(self):
#         for order in self:
#             order.payment_request_count = len(order.payment_request_ids)
#             order.lc_count = len(order.lc_ids)
#             order.shipment_count = len(order.shipment_ids)
#             order.landing_count = len(order.landing_ids)

#     @api.depends('amount_total', 'landing_ids.total_landing_cost')
#     def _compute_total_landed_cost(self):
#         for order in self:
#             landing_costs = sum(landing.total_landing_cost for landing in order.landing_ids)
#             order.total_landed_cost = order.amount_total + landing_costs

#     def action_create_payment_request(self):
#         return {
#             'name': _('Create Payment Request'),
#             'type': 'ir.actions.act_window',
#             'res_model': 'foreign.payment.request',
#             'view_mode': 'form',
#             'target': 'current',
#             'context': {
#                 'default_purchase_order_id': self.id,
#                 'default_supplier_id': self.partner_id.id,
#                 'default_currency_id': self.currency_id.id,
#                 'default_branch_id': self.branch_id.id,
#             }
#         }

#     def action_create_lc(self):
#         if self.order_type != 'foreign':
#             raise UserError(_("Letter of Credit can only be created for foreign orders."))
#         return {
#             'name': _('Create Letter of Credit'),
#             'type': 'ir.actions.act_window',
#             'res_model': 'foreign.lc',
#             'view_mode': 'form',
#             'target': 'current',
#             'context': {
#                 'default_purchase_order_id': self.id,
#                 'default_lc_amount': self.amount_total,
#                 'default_currency_id': self.currency_id.id,
#             }
#         }

#     def action_create_shipment(self):
#         return {
#             'name': _('Create Shipment'),
#             'type': 'ir.actions.act_window',
#             'res_model': 'foreign.shipment',
#             'view_mode': 'form',
#             'target': 'current',
#             'context': {
#                 'default_purchase_order_id': self.id,
#                 'default_port_of_loading': self.port_of_loading,
#                 'default_port_of_discharge': self.port_of_discharge,
#             }
#         }

#     def action_create_landing(self):
#         return {
#             'name': _('Create Landing Process'),
#             'type': 'ir.actions.act_window',
#             'res_model': 'foreign.costing',
#             'view_mode': 'form',
#             'target': 'current',
#             'context': {
#                 'default_purchase_order_id': self.id,
#             }
#         }

#     def action_view_payment_requests(self):
#         return {
#             'name': _('Payment Requests'),
#             'type': 'ir.actions.act_window',
#             'res_model': 'foreign.payment.request',
#             'view_mode': 'list,form',
#             'domain': [('purchase_order_id', '=', self.id)],
#             'context': {'default_purchase_order_id': self.id}
#         }

#     def action_view_lcs(self):
#         return {
#             'name': _('Letters of Credit'),
#             'type': 'ir.actions.act_window',
#             'res_model': 'foreign.lc',
#             'view_mode': 'tree,form',
#             'domain': [('purchase_order_id', '=', self.id)],
#             'context': {'default_purchase_order_id': self.id}
#         }

#     def action_view_shipments(self):
#         return {
#             'name': _('Shipments'),
#             'type': 'ir.actions.act_window',
#             'res_model': 'foreign.shipment',
#             'view_mode': 'list,form',
#             'domain': [('purchase_order_id', '=', self.id)],
#             'context': {'default_purchase_order_id': self.id}
#         }

#     def action_view_costing(self):
#         return {
#             'name': _('Costing Processes'),
#             'type': 'ir.actions.act_window',
#             'res_model': 'foreign.costing',                                                             
#             'view_mode': 'list,form',
#             'domain': [('purchase_order_id', '=', self.id)],
#             'context': {'default_purchase_order_id': self.id}
#         }

#     @api.model
#     def create(self, vals):
#         if vals.get('branch_id') and (not vals.get('name') or vals.get('name') == 'New'):
#             branch = self.env['account.analytic.account'].browse(vals['branch_id'])
#             branch_code = branch.code or '00'
#             year = datetime.now().year
#             # Use base sequence
#             seq = self.env['ir.sequence'].next_by_code('purchase.order')
#             # Compose name manually
#             vals['name'] = f"P{branch_code}{year}{seq[-5:]}"  # last 5 digits from seq padding
#         return super(PurchaseOrder, self).create(vals)


# class PurchaseOrderLine(models.Model):
#     _inherit = 'purchase.order.line'
    
#     product_id = fields.Many2one(
#         'product.product',
#         string='Product',
#         options={'no_create': True, 'no_create_edit': True}
#     )
    
#     hs_code = fields.Char(string='HS Code', help='Harmonized System Code for customs classification')
#     country_of_origin = fields.Many2one('res.country', string='Country of Origin')
    
#     # NEW: Price fields in both currencies
#     price_unit_local = fields.Monetary(
#         string='Unit Price (Local)',
#         compute='_compute_local_prices',
#         currency_field='local_currency_id',
#         store=True,
#         help='Unit price in local currency'
#     )
    
#     price_subtotal_local = fields.Monetary(
#         string='Subtotal (Local)',
#         compute='_compute_local_prices',
#         currency_field='local_currency_id',
#         store=True,
#         help='Subtotal in local currency'
#     )
    
#     local_currency_id = fields.Many2one(
#         'res.currency',
#         related='order_id.local_currency_id',
#         string='Local Currency'
#     )
    
#     landed_cost_allocated = fields.Monetary(
#         string='Allocated Landed Cost',
#         currency_field='currency_id',
#         help='Portion of total landed costs allocated to this line'
#     )
    
#     total_cost_per_unit = fields.Monetary(
#         string='Total Cost per Unit',
#         compute='_compute_total_cost_per_unit',
#         currency_field='currency_id',
#         help='Unit price including allocated landed costs'
#     )

#     # NEW: Local currency price computation
#     @api.depends('price_unit', 'order_id.exchange_rate', 'price_subtotal')
#     def _compute_local_prices(self):
#         for line in self:
#             if line.order_id.exchange_rate and line.order_id.foreign_currency_id:
#                 line.price_unit_local = line.price_unit * line.order_id.exchange_rate
#                 line.price_subtotal_local = line.price_subtotal * line.order_id.exchange_rate
#             else:
#                 line.price_unit_local = line.price_unit
#                 line.price_subtotal_local = line.price_subtotal

#     @api.depends('price_unit', 'landed_cost_allocated', 'product_qty')
#     def _compute_total_cost_per_unit(self):
#         for line in self:
#             if line.product_qty:
#                 line.total_cost_per_unit = line.price_unit + (line.landed_cost_allocated / line.product_qty)
#             else:
#                 line.total_cost_per_unit = line.price_unit

#     @api.model
#     def _prepare_account_move_line(self, move=False):
#         res = super()._prepare_account_move_line(move)
#         if self.order_id.branch_id:
#             branch = self.order_id.branch_id
#             analytic_distribution = {str(branch.id): 100.0}
#             if 'analytic_distribution' not in res or not res['analytic_distribution']:
#                 res['analytic_distribution'] = analytic_distribution
#         return res



#====================================================================================================================================





# from odoo import api, fields, models, _
# from odoo.exceptions import UserError
# from datetime import datetime

# class PurchaseOrder(models.Model):
#     _inherit = 'purchase.order'

#     branch_id = fields.Many2one(
#         'account.analytic.account',
#         string='Branch',
#         domain="[('plan_id.name', '=', 'Branch'), ('company_id', '=', company_id)]",
#         help="The branch associated with this purchase order.",
#         tracking=True,
#         required = True,
#     )

#     order_type = fields.Selection(
#         selection=[
#             ('local', 'Local'),
#             ('foreign', 'Foreign'),
#         ],
#         string="Order Type",
#         default='foreign',
#         help="Automatically set as 'Local' or 'Foreign' based on vendor's country."
#          )

#     procurement_method = fields.Selection([
#         ('direct', 'Direct Purchase'),
#         ('lc', 'Letter of Credit'),
#         ('advance', 'Advance Payment'),
#     ], string='Procurement Method', tracking=True)

#     incoterm_id = fields.Many2one(
#         'account.incoterms',
#         string='Incoterm',
#         help='International Commercial Terms for international transactions.'
#     )

#     port_of_loading = fields.Char(string='Port of Loading')
#     port_of_discharge = fields.Char(string='Port of Discharge')

#     estimated_shipping_date = fields.Date(string='Estimated Shipping Date')
#     estimated_arrival_date = fields.Date(string='Estimated Arrival Date')

#     payment_request_ids = fields.One2many('foreign.payment.request', 'purchase_order_id', string='Payment Requests')
#     lc_ids = fields.One2many('foreign.lc', 'purchase_order_id', string='Letters of Credit')
#     shipment_ids = fields.One2many('foreign.shipment', 'purchase_order_id', string='Shipments')
#     landing_ids = fields.One2many('foreign.landing', 'purchase_order_id', string='Landing Processes')

#     payment_request_count = fields.Integer(compute='_compute_related_counts', string='Payment Requests')
#     lc_count = fields.Integer(compute='_compute_related_counts', string='Letters of Credit')
#     shipment_count = fields.Integer(compute='_compute_related_counts', string='Shipments')
#     landing_count = fields.Integer(compute='_compute_related_counts', string='Landing Processes')

#     foreign_procurement_state = fields.Selection([
#         ('draft', 'Draft'),
#         ('quotation_received', 'Quotation Received'),
#         ('lc_processing', 'LC Processing'),
#         ('goods_shipped', 'Goods Shipped'),
#         ('goods_arrived', 'Goods Arrived'),
#         ('customs_clearance', 'Customs Clearance'),
#         ('completed', 'Completed'),
#     ], string='Foreign Procurement Status', default='draft', tracking=True)

#     total_landed_cost = fields.Monetary(
#         string='Total Landed Cost',
#         compute='_compute_total_landed_cost',
#         currency_field='currency_id',
#         store=True,
#         help="Total cost including purchase price, shipping, duties, and other charges"
#     )

#     @api.onchange('branch_id')
#     def _onchange_branch_id(self):
#         if self.branch_id and self.branch_id.company_id and self.branch_id.company_id != self.company_id:
#             self.company_id = self.branch_id.company_id
#         elif not self.branch_id and self.env.user.company_id:
#             self.company_id = self.env.user.company_id

#     @api.depends('partner_id', 'partner_id.country_id', 'company_id.country_id')
#     def _compute_order_type(self):
#         for order in self:
#             vendor_country = order.partner_id.country_id if order.partner_id else False
#             company_country = order.company_id.country_id if order.company_id else False
#             if vendor_country and company_country:
#                 order.order_type = 'local' if vendor_country.id == company_country.id else 'foreign'
#             else:
#                 order.order_type = 'local'

#     @api.depends('payment_request_ids', 'lc_ids', 'shipment_ids', 'landing_ids')
#     def _compute_related_counts(self):
#         for order in self:
#             order.payment_request_count = len(order.payment_request_ids)
#             order.lc_count = len(order.lc_ids)
#             order.shipment_count = len(order.shipment_ids)
#             order.landing_count = len(order.landing_ids)

#     @api.depends('amount_total', 'landing_ids.total_landing_cost')
#     def _compute_total_landed_cost(self):
#         for order in self:
#             landing_costs = sum(landing.total_landing_cost for landing in order.landing_ids)
#             order.total_landed_cost = order.amount_total + landing_costs

#     @api.onchange('order_type')
#     def _onchange_order_type(self):
#         if self.order_type == 'foreign':
#             if not self.procurement_method:
#                 self.procurement_method = 'lc'
#         else:
#             self.procurement_method = False
#             self.foreign_procurement_state = False




#     # @api.onchange('order_type')
#     # def _onchange_order_type_vendor_filter(self):
#     #     if self.order_type == 'foreign':
#     #         return {
#     #             'domain': {'partner_id': [('supplier_rank', '>', 0), ('vendor_type', '=', 'foreign')]}
#     #         }
#     #     else:
#     #         return {
#     #             'domain': {'partner_id': [('supplier_rank', '>', 0)]}
#     #         }




#     def action_create_payment_request(self):
#         return {
#             'name': _('Create Payment Request'),
#             'type': 'ir.actions.act_window',
#             'res_model': 'foreign.payment.request',
#             'view_mode': 'form',
#             'target': 'current',
#             'context': {
#                 'default_purchase_order_id': self.id,
#                 'default_supplier_id': self.partner_id.id,
#                 'default_currency_id': self.currency_id.id,
#                 'default_branch_id': self.branch_id.id,
#             }
#         }

#     def action_create_lc(self):
#         if self.order_type != 'foreign':
#             raise UserError(_("Letter of Credit can only be created for foreign orders."))
#         return {
#             'name': _('Create Letter of Credit'),
#             'type': 'ir.actions.act_window',
#             'res_model': 'foreign.lc',
#             'view_mode': 'form',
#             'target': 'current',
#             'context': {
#                 'default_purchase_order_id': self.id,
#                 'default_lc_amount': self.amount_total,
#                 'default_currency_id': self.currency_id.id,
#             }
#         }

#     def action_create_shipment(self):
#         return {
#             'name': _('Create Shipment'),
#             'type': 'ir.actions.act_window',
#             'res_model': 'foreign.shipment',
#             'view_mode': 'form',
#             'target': 'current',
#             'context': {
#                 'default_purchase_order_id': self.id,
#                 'default_port_of_loading': self.port_of_loading,
#                 'default_port_of_discharge': self.port_of_discharge,
#             }
#         }

#     def action_create_landing(self):
#         return {
#             'name': _('Create Landing Process'),
#             'type': 'ir.actions.act_window',
#             'res_model': 'foreign.landing',
#             'view_mode': 'form',
#             'target': 'current',
#             'context': {
#                 'default_purchase_order_id': self.id,
#             }
#         }

#     def action_view_payment_requests(self):
#         return {
#             'name': _('Payment Requests'),
#             'type': 'ir.actions.act_window',
#             'res_model': 'foreign.payment.request',
#             'view_mode': 'tree,form',
#             'domain': [('purchase_order_id', '=', self.id)],
#             'context': {'default_purchase_order_id': self.id}
#         }

#     def action_view_lcs(self):
#         return {
#             'name': _('Letters of Credit'),
#             'type': 'ir.actions.act_window',
#             'res_model': 'foreign.lc',
#             'view_mode': 'tree,form',
#             'domain': [('purchase_order_id', '=', self.id)],
#             'context': {'default_purchase_order_id': self.id}
#         }

#     def action_view_shipments(self):
#         return {
#             'name': _('Shipments'),
#             'type': 'ir.actions.act_window',
#             'res_model': 'foreign.shipment',
#             'view_mode': 'tree,form',
#             'domain': [('purchase_order_id', '=', self.id)],
#             'context': {'default_purchase_order_id': self.id}
#         }

#     def action_view_landings(self):
#         return {
#             'name': _('Landing Processes'),
#             'type': 'ir.actions.act_window',
#             'res_model': 'foreign.landing',
#             'view_mode': 'tree,form',
#             'domain': [('purchase_order_id', '=', self.id)],
#             'context': {'default_purchase_order_id': self.id}
#         }

#     @api.model
#     def create(self, vals):
#         if vals.get('branch_id') and (not vals.get('name') or vals.get('name') == 'New'):
#             branch = self.env['account.analytic.account'].browse(vals['branch_id'])
#             branch_code = branch.code or '00'
#             year = datetime.now().year

#             # Use base sequence
#             seq = self.env['ir.sequence'].next_by_code('purchase.order')

#             # Compose name manually
#             vals['name'] = f"P{branch_code}{year}{seq[-5:]}"  # last 5 digits from seq padding

#         return super(PurchaseOrder, self).create(vals)


# class PurchaseOrderLine(models.Model):
#     _inherit = 'purchase.order.line'

#     product_id = fields.Many2one(
#         'product.product',
#         string='Product',
#         options={'no_create': True, 'no_create_edit': True}
#     )

#     hs_code = fields.Char(string='HS Code', help='Harmonized System Code for customs classification')
#     country_of_origin = fields.Many2one('res.country', string='Country of Origin')

#     landed_cost_allocated = fields.Monetary(
#         string='Allocated Landed Cost',
#         currency_field='currency_id',
#         help='Portion of total landed costs allocated to this line'
#     )

#     total_cost_per_unit = fields.Monetary(
#         string='Total Cost per Unit',
#         compute='_compute_total_cost_per_unit',
#         currency_field='currency_id',
#         help='Unit price including allocated landed costs'
#     )

#     @api.depends('price_unit', 'landed_cost_allocated', 'product_qty')
#     def _compute_total_cost_per_unit(self):
#         for line in self:
#             if line.product_qty:
#                 line.total_cost_per_unit = line.price_unit + (line.landed_cost_allocated / line.product_qty)
#             else:
#                 line.total_cost_per_unit = line.price_unit

#     @api.model
#     def _prepare_account_move_line(self, move=False):
#         res = super()._prepare_account_move_line(move)
#         if self.order_id.branch_id:
#             branch = self.order_id.branch_id
#             analytic_distribution = {str(branch.id): 100.0}
#             if 'analytic_distribution' not in res or not res['analytic_distribution']:
#                 res['analytic_distribution'] = analytic_distribution
#         return res
