from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError, UserError
import logging
import math
from datetime import datetime

_logger = logging.getLogger(__name__)

class ForeignCosting(models.Model):
    _name = 'foreign.costing'
    _description = 'Foreign Costing - Comprehensive Import Costing System'
    _rec_name = 'reference'
    _order = 'date desc, id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # Basic Information
    reference = fields.Char(
        string='Reference',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: self.env['ir.sequence'].next_by_code('foreign.costing'),
        tracking=True
    )
    date = fields.Date(
        string='Date',
        default=fields.Date.context_today,
        required=True,
        tracking=True
    )
    purchase_order_id = fields.Many2one(
        'purchase.order',
        string='Purchase Order',
        tracking=True,
        required=False
    )
    
    
    is_marketing_costing = fields.Boolean(string='Marketing/Tenders Costing', default=False, tracking=True)
    costing_type = fields.Selection([('actual', 'Actual Costing'), ('tentative', 'Tentative Costing')], string='Costing Type', default='actual', tracking=True)
    is_deposit_costing = fields.Boolean(string='Product via Deposit', default=False, tracking=True)
    
    include_vat = fields.Boolean(string='Include VAT', default=False, tracking=True)
    include_withholding = fields.Boolean(string='Include Withholding Tax', default=False, tracking=True)
    
    client_id = fields.Many2one('res.partner', string='Client', tracking=True)
    company_id = fields.Many2one(
    'res.company',
    string='Company',
    required=True,
    default=lambda self: self.env.company
)
    branch_id = fields.Many2one(
    'account.analytic.account',
    string='Branch',
    store=True, # Make sure to add this  transit_done
    tracking=True,
    readonly=True
    )
    state = fields.Selection([
        ('draft', 'Draft'),
        ('calculated', 'Calculated'),
        ('waiting_for_manager', 'Waiting for Procurement Manager'),
        ('waiting_for_gm', 'Waiting for General Manager'),
        ('waiting_for_director', 'Waiting for Director'),
        ('waiting_for_finance', 'Waiting for Finance Manager'),
        ('waiting_for_approval', 'Waiting For Approval'),
        ('approved', 'Approved'),
        ('confirmed', 'Confirmed'),
        ('done', 'Done'),
        ('cancelled', 'Cancelled'),
        ('rejected', 'Rejected'),
    ], string='Status', default='draft', readonly=True, tracking=True)

     # Centralized Approval Fields
    approval_request_id = fields.Many2one(
        'approval.request', 
        string="Approval Request", 
        readonly=True
    )
    step_progress = fields.Html(
        string="Approval Progress", 
        compute='_compute_step_progress'
    )
    # Relations to existing models
   
    # Added bank_process_id for LC details
    bank_process_id = fields.Many2one(
        'foreign.bank.process',
        string='Bank Process Reference',
        tracking=True,
        help="Related bank process for LC details",
        readonly=True
    )
    shipment_id = fields.Many2one('foreign.shipment', string='Shipment Reference', tracking=True)
    landing_id = fields.Many2one('foreign.landing', string='Landing Reference', tracking=True)
    transit_process_id = fields.Many2one(
        'foreign.transit.process',
        string='Transit Process',
        compute='_compute_related_documents',
        store=True,
        readonly=True
    )

    vat_amount_fx = fields.Float(
        string='VAT Amount',
        digits=(16, 2),
        help="VAT amount from customs, typically from the transit process."
    )

    # LC Details (Computed from bank_process_id)
    lc_number_display = fields.Char(
        string='LC Number',
        compute='_compute_lc_details',
        store=True,
        readonly=True,
        help="LC Number from the linked Bank Process"
    )
    lc_date_of_shipment_display = fields.Date(
        string='LC Date Of Shipment',
        compute='_compute_lc_details',
        store=True,
        readonly=True,
        help="LC Date of Shipment from the linked Bank Process"
    )
    negotiation_expiry_date_display = fields.Date(
        string='Negotiation Expiry Date',
        compute='_compute_lc_details',
        store=True,
        readonly=True,
        help="Negotiation Expiry Date from the linked Bank Process"
    )
    lc_amount_display = fields.Monetary(
        string='LC Amount',
        currency_field='duty_fx',  # Changed from 'currency_id' to 'duty_fx'
        compute='_compute_lc_details',
        store=True,
        readonly=True,
        help="LC Amount from the linked Bank Process"
    )

    # Payment Request Integration
    payment_request_ids = fields.Many2many(
        'foreign.payment.request',
        'foreign_costing_payment_request_rel',
        'foreign_costing_id',
        'payment_request_id',
        string='Payment Requests',
        domain=[('state', '=', 'paid')], # Updated domain to 'paid'
        help="Select paid payment requests to import costs from"
    )

    # Exchange Rates
    exchange_rate_fx = fields.Float(
        string='Exchange Rate 1 (USD to Birr)',
        digits=(16, 6),
        default=1.0,
        help="Exchange rate for converting USD amounts to Birr"
    )
    exchange_rate2_fx = fields.Float(
        string='Exchange Rate 2 (Freight Currency)',
        digits=(16, 6),
        default=1.0,
        help="Exchange rate for freight charges"
    )

    # Base Amounts
    amount_fx = fields.Float(
        string='Ex Works Amount (USD)',
        digits=(16, 2),
        help="Ex Works amount in foreign currency"
    )
    fob_charges_fx = fields.Float(
        string='FOB Charges (USD)',
        digits=(16, 2),
        help="Free on Board charges"
    )
    amount_in_birr_fx = fields.Float(
        string='Invoice Amount (Birr)',
        digits=(16, 2),
        help="Invoice amount in local currency"
    )
    freight_charge_fx = fields.Float(
        string='Freight Charge',
        digits=(16, 2),
        help="Freight charges in foreign currency"
    )

    # Calculated Base Amounts
    ex_works_in_birr_fx = fields.Float(
        string='Ex Works in Birr',
        digits=(16, 2),
        compute='_compute_exchange_calculations',
        store=True,
        help="Ex Works Amount × Exchange Rate 1"
    )
    fob_charge_in_birr_fx = fields.Float(
        string='FOB Charge in Birr',
        digits=(16, 2),
        compute='_compute_exchange_calculations',
        store=True,
        help="FOB Charges × Exchange Rate 1"
    )
    ex_works_amount_fx = fields.Float(
        string='Ex Works Amount (Calculated)',
        digits=(16, 2),
        compute='_compute_exchange_calculations',
        store=True,
        help="Invoice Amount × Exchange Rate 1"
    )
    fright_charge_in_birr_fx = fields.Float(
        string='Freight Charge in Birr',
        digits=(16, 2),
        compute='_compute_freight_calculation',
        store=True,
        help="Freight Charge × Exchange Rate 2"
    )
   
   
    # Banking Charges (Enhanced with Payment Request Integration)
    bank_charge_fx = fields.Float(string='Bank Charge', digits=(16, 2))
    bank_charge_of_eslsc_fx = fields.Float(string='Bank Charge of ESLSC', digits=(16, 2))
    bank_interest_fx = fields.Float(string='Bank Interest', digits=(16, 2))

    # Insurance
    insurance_amount_fx = fields.Float(string='Insurance Amount', digits=(16, 2))
    third_party_fx = fields.Float(string='Third Party Insurance', digits=(16, 2))
    owen_damage_fx = fields.Float(string='Own Damage Insurance', digits=(16, 2))
    work_mens_fx = fields.Float(string='Work Mens Insurance', digits=(16, 2))
    yellow_card_fx = fields.Float(string='Yellow Card', digits=(16, 2))
    insurance_extension_fx = fields.Float(string='Insurance Extension', digits=(16, 2))

    # Cost Additions
    social_welfare_fx = fields.Float(string='Social Welfare', digits=(16, 2))
    insurance_claim_fx = fields.Float(string='Insurance Claim', digits=(16, 2))
    change_warehouse_fx = fields.Float(string='Change Warehouse', digits=(16, 2))

    # Port and Transport Charges
    container_service_char_fx = fields.Float(string='Container Service Charge', digits=(16, 2))
    djibuti_port_expense_fx = fields.Float(string='Djibouti Port Expense', digits=(16, 2))
    local_forward_and_clea_fx = fields.Float(string='Local Forward and Clearing', digits=(16, 2))
    trans_charge_from_dj_t_fx = fields.Float(string='Transport Charge from Djibouti', digits=(16, 2))
    empty_cont_trans_char_fx = fields.Float(string='Empty Container Transport Charge', digits=(16, 2))
    trans_charge_to_wareho_fx = fields.Float(string='Transport Charge to Warehouse', digits=(16, 2))
    miscellaneous_fx = fields.Float(string='Miscellaneous Charges', digits=(16, 2))
    rta_fx = fields.Float(string='RTA Charges', digits=(16, 2))

    # Taxes and Duties
    customes_duty_fx = fields.Float(string='Customs Duty', digits=(16, 2))
    excise_tax_fx = fields.Float(string='Excise Tax', digits=(16, 2))
    sur_tax_fx = fields.Float(string='Sur Tax', digits=(16, 2))
    withholding_tax_fx = fields.Float(string='Withholding Tax', digits=(16, 2))
    scanning_fee_fx = fields.Float(string='Scanning Fee', digits=(16, 2))
    storage_charge_fx = fields.Float(string='Storage Charge', digits=(16, 2))
    custom_bond_fx = fields.Float(string='Custom Bond', digits=(16, 2))

    # Calculated Fields
    total_landed_cost_fx = fields.Float(
        string='Total Landed Cost',
        digits=(16, 2),
        compute='_compute_total_landed_cost',
        store=True,
        help="Sum of all costs and charges"
    )
    cost_rate_fx = fields.Float(
        string='Cost Rate',
        digits=(16, 6),
        compute='_compute_cost_rate_fx',
        store=True,
        readonly=True,
        help="System calculated cost rate based on calculations"
    )
    cost_factor_fx = fields.Float(
        string='Cost Factor',
        digits=(16, 6),
        compute='_compute_cost_factor',
        store=True,
        help="Total Landed Cost ÷ Ex Works in Birr"
    )
    margin_factor_fx = fields.Float(
        string='Margin Factor',
        digits=(16, 4),
        compute='_compute_margin',
        store=True,
        help="Calculated Margin Factor (Optimum Values / Cost Factor)"
    )
    margin_fx = fields.Float(
        string='Margin',
        digits=(16, 4),
        compute='_compute_margin',
        store=True,
        help="Margin % (Margin Factor - 1)"
    )

    @api.depends('total_landed_cost_fx', 'amount_fx', 'amount_in_birr_fx', 'exchange_rate_fx')
    def _compute_cost_rate_fx(self):
        for record in self:
            if record.amount_fx != 0 and record.exchange_rate_fx != 0:
                record.cost_rate_fx = record.total_landed_cost_fx / record.amount_fx
            elif record.amount_in_birr_fx != 0:
                record.cost_rate_fx = record.total_landed_cost_fx / record.amount_in_birr_fx
            else:
                record.cost_rate_fx = 0

            # Handle invalid values
            value = record.cost_rate_fx
            if math.isnan(value) or math.isinf(value):
                record.cost_rate_fx = 0

    # Auto-calculated suggestions (read-only)
    suggested_cost_rate_fx = fields.Float(
        string='Suggested Cost Rate',
        digits=(16, 6),
        compute='_compute_suggested_values',
        help="System suggested cost rate based on calculations"
    )

    # Configuration
    optimum_values_fx = fields.Float(
        string='Optimum Values',
        digits=(16, 4),
        default=1.5,
        help="Target optimum value for margin calculation"
    )
    # Changed duty_fx to Many2one to res.currency
    duty_fx = fields.Many2one(
        'res.currency',
        string='Duty/Currency',
        default=lambda self: self.env.ref('base.USD').id, # Default to USD
        help="Currency for duty calculations and product line pricing"
    )
    
    landed_cost_id = fields.Many2one(
        'stock.landed.cost',
        string='Landed Cost Record',
        readonly=True, copy=False
    )

    # Relations
    product_line_ids = fields.One2many(
        'foreign.costing.product.line',
        'costing_id',
        string='Product Lines (Reference)',
        compute='_compute_product_lines',
        store=True,
        readonly=True,
        help="Auto-computed product lines from Purchase Order - Reference Only"
    )

    payment_cost_line_ids = fields.One2many(
        'foreign.costing.payment.line',
        'costing_id',
        string='Payment Request Costs (Reference)',
        compute='_compute_payment_cost_lines',
        store=True,
        readonly=True,
        help="Auto-computed costs from Payment Requests - Reference Only"
    )
    
    additional_cost_line_ids = fields.One2many(
        'foreign.costing.additional.cost',
        'costing_id',
        string='Additional Manual Costs'
    )

    # Summary fields
    total_products = fields.Integer(
        string='Total Products',
        compute='_compute_summary_fields'
    )
    total_quantity = fields.Float(
        string='Total Quantity',
        compute='_compute_summary_fields'
    )
    # Added base amounts to summary fields
    total_ex_works_usd = fields.Float(
        string='Total Ex Works (USD)',
        compute='_compute_summary_fields',
        digits=(16, 2)
    )
    total_invoice_birr = fields.Float(
        string='Total Invoice (Birr)',
        compute='_compute_summary_fields',
        digits=(16, 2)
    )

    @api.depends('product_line_ids', 'amount_fx', 'amount_in_birr_fx')
    def _compute_summary_fields(self):
        for record in self:
            record.total_products = len(record.product_line_ids)
            record.total_quantity = sum(record.product_line_ids.mapped('total_quantit_imported_fx'))
            record.total_ex_works_usd = record.amount_fx
            record.total_invoice_birr = record.amount_in_birr_fx

    @api.depends('total_landed_cost_fx', 'ex_works_in_birr_fx')
    def _compute_cost_factor(self):
        for record in self:
            if record.ex_works_in_birr_fx != 0:
                record.cost_factor_fx = record.total_landed_cost_fx / record.ex_works_in_birr_fx
            else:
                record.cost_factor_fx = 0

            value = record.cost_factor_fx
            if math.isnan(value) or math.isinf(value):
                record.cost_factor_fx = 0

    @api.depends('cost_factor_fx', 'optimum_values_fx')
    def _compute_margin(self):
        """Dynamic Margin Calculation based on optimum values and cost factor"""
        for record in self:
            if record.cost_factor_fx != 0:
                calc_margin_factor = record.optimum_values_fx / record.cost_factor_fx
                
                # Apply limits: If < 1.25 make it 1.25. If > 2 make it 2.
                if calc_margin_factor <= 1.25:
                    record.margin_factor_fx = 1.25
                elif calc_margin_factor >= 2.0:
                    record.margin_factor_fx = 2.0
                else:
                    record.margin_factor_fx = calc_margin_factor
            else:
                record.margin_factor_fx = 0

            # Margin = Margin factor - 1
            record.margin_fx = max(0, record.margin_factor_fx - 1)

    @api.depends('bank_process_id')
    def _compute_lc_details(self):
        """Compute LC details from the linked bank_process_id."""
        for record in self:
            if record.bank_process_id and record.bank_process_id.lc_tracking_ids:
                lc = record.bank_process_id.lc_tracking_ids[0]  # Take the first LC record
                record.lc_number_display = lc.lc_number
                record.lc_date_of_shipment_display = lc.lc_date_of_shipment
                record.negotiation_expiry_date_display = lc.negotiation_expiry_date
                record.lc_amount_display = lc.lc_amount
            else:
                record.lc_number_display = False
                record.lc_date_of_shipment_display = False
                record.negotiation_expiry_date_display = False
                record.lc_amount_display = 0.0


    @api.depends('exchange_rate_fx', 'amount_fx', 'fob_charges_fx', 'amount_in_birr_fx')
    def _compute_exchange_calculations(self):
        for record in self:
            record.ex_works_in_birr_fx = record.exchange_rate_fx * record.amount_fx
            record.fob_charge_in_birr_fx = record.exchange_rate_fx * record.fob_charges_fx
            record.ex_works_amount_fx = record.exchange_rate_fx * record.amount_in_birr_fx

    @api.depends('exchange_rate2_fx', 'freight_charge_fx')
    def _compute_freight_calculation(self):
        for record in self:
            record.fright_charge_in_birr_fx = record.exchange_rate2_fx * record.freight_charge_fx

    @api.depends(
        'ex_works_in_birr_fx', 'fob_charge_in_birr_fx', 'fright_charge_in_birr_fx',
        'bank_charge_fx', 'bank_charge_of_eslsc_fx', 'bank_interest_fx', 'insurance_amount_fx',
        'third_party_fx', 'owen_damage_fx', 'work_mens_fx', 'yellow_card_fx', 'insurance_extension_fx',
        'social_welfare_fx', 'insurance_claim_fx', 'change_warehouse_fx',
        'container_service_char_fx', 'djibuti_port_expense_fx', 'local_forward_and_clea_fx',
        'trans_charge_from_dj_t_fx', 'empty_cont_trans_char_fx', 'trans_charge_to_wareho_fx',
        'miscellaneous_fx', 'rta_fx', 'customes_duty_fx', 'vat_amount_fx',
        'excise_tax_fx', 'sur_tax_fx', 'scanning_fee_fx', 'storage_charge_fx', 'custom_bond_fx',
        'withholding_tax_fx', 'include_vat', 'include_withholding',
        'payment_cost_line_ids.amount_birr', 'additional_cost_line_ids.amount_birr'
    )
    def _compute_total_landed_cost(self):
        for record in self:
            payment_costs_total = sum(record.payment_cost_line_ids.filtered('applied_to_cost').mapped('amount_birr'))
            additional_costs_total = sum(record.additional_cost_line_ids.mapped('amount_birr'))
            
            withholding_tax = record.withholding_tax_fx if record.include_withholding else 0.0
            vat_tax = record.vat_amount_fx if record.include_vat else 0.0
            
            record.total_landed_cost_fx = sum([
                record.ex_works_in_birr_fx,
                record.fob_charge_in_birr_fx,
                record.fright_charge_in_birr_fx,
                record.bank_charge_fx,
                record.bank_charge_of_eslsc_fx,
                record.bank_interest_fx,
                record.insurance_amount_fx,
                record.third_party_fx,
                record.owen_damage_fx,
                record.work_mens_fx,
                record.yellow_card_fx,
                record.insurance_extension_fx,
                record.social_welfare_fx,
                record.insurance_claim_fx,
                record.change_warehouse_fx,
                record.container_service_char_fx,
                record.djibuti_port_expense_fx,
                record.local_forward_and_clea_fx,
                record.trans_charge_from_dj_t_fx,
                record.empty_cont_trans_char_fx,
                record.trans_charge_to_wareho_fx,
                record.miscellaneous_fx,
                record.rta_fx,
                record.customes_duty_fx,
                record.excise_tax_fx,
                record.sur_tax_fx,
                record.scanning_fee_fx,
                withholding_tax,
                vat_tax,
                record.storage_charge_fx,
                record.custom_bond_fx,
                payment_costs_total,
                additional_costs_total
            ])

    @api.depends('total_landed_cost_fx', 'amount_fx', 'amount_in_birr_fx', 'ex_works_in_birr_fx',
                 'exchange_rate_fx', 'optimum_values_fx', 'cost_factor_fx')
    def _compute_suggested_values(self):
        """Compute suggested values but keep actual values editable"""
        for record in self:
            # Suggested Cost Rate
            if record.amount_fx != 0 and record.exchange_rate_fx != 0:
                record.suggested_cost_rate_fx = record.total_landed_cost_fx / record.amount_fx
            elif record.amount_in_birr_fx != 0:
                record.suggested_cost_rate_fx = record.total_landed_cost_fx / record.amount_in_birr_fx
            else:
                record.suggested_cost_rate_fx = 0

            # Handle invalid values
            value = record.suggested_cost_rate_fx
            if math.isnan(value) or math.isinf(value):
                record.suggested_cost_rate_fx = 0

    @api.depends('purchase_order_id', 'purchase_order_id.order_line')
    def _compute_product_lines(self):
        """Auto-compute product lines from purchase order - for reference display only"""
        for record in self:
            # Clear existing computed lines
            record.product_line_ids = [(5, 0, 0)]
            
            if record.purchase_order_id:
                lines_data = []
                for line in record.purchase_order_id.order_line:
                    lines_data.append((0, 0, {
                        'product_id': line.product_id.id,
                        'part_no_fx': line.product_id.default_code or '',
                        'description_of_goods_fx': line.product_id.name or '',
                        'total_quantit_imported_fx': line.product_qty,
                        'unit_price_fx': line.price_unit,
                        'measurmet_unit_fx': line.product_uom.name,
                        'currency_fx': line.currency_id.id,
                        'cost_rate_fx': record.cost_rate_fx,
                        'margin_fx': record.margin_factor_fx,
                    }))
                record.product_line_ids = lines_data

    @api.depends('payment_request_ids', 'payment_request_ids.payment_line_ids')
    def _compute_payment_cost_lines(self):
        """Auto-compute payment cost lines from payment requests - for reference display only"""
        for record in self:
            # Clear existing computed lines
            record.payment_cost_line_ids = [(5, 0, 0)]
            
            lines_data = []
            for payment_request in record.payment_request_ids:
                for payment_line in payment_request.payment_line_ids:
                    # Convert amount to company currency (Birr)
                    amount_birr = payment_line.amount
                    if payment_line.currency_id and record.env.company.currency_id and \
                       payment_line.currency_id != record.env.company.currency_id:
                        amount_birr = payment_line.currency_id._convert(
                            payment_line.amount,
                            record.env.company.currency_id,
                            record.env.company,
                            fields.Date.today()
                        )
                    
                    # Only include non-'other' payment types in reference display
                    if payment_line.payment_type != 'other':
                        lines_data.append((0, 0, {
                            'payment_request_id': payment_request.id,
                            'payment_line_id': payment_line.id,
                            'payment_type': payment_line.payment_type,
                            'payment_method': payment_line.payment_method,
                            'description': payment_line.description,
                            'amount_original': payment_line.amount,
                            'currency_id': payment_line.currency_id.id,
                            'amount_birr': amount_birr,
                            'applied_to_cost': True,
                        }))
            
            record.payment_cost_line_ids = lines_data

    @api.onchange('purchase_order_id')
    def _onchange_purchase_order_id(self):
        """Auto-populate fields from purchase order and trigger line computation"""
        if self.purchase_order_id:
            po = self.purchase_order_id

            # Set basic amounts from PO
            self.amount_fx = po.amount_untaxed
            self.amount_in_birr_fx = po.amount_untaxed

            # Auto-load related Bank Process (LC details)
            bank_process = self.env['foreign.bank.process'].search([
                ('purchase_order_id', '=', po.id)
            ], limit=1)
            if bank_process:
                self.bank_process_id = bank_process.id

            # Auto-load related Shipment
            shipment = self.env['foreign.shipment'].search([
                ('purchase_order_id', '=', po.id)
            ], limit=1)
            if shipment:
                self.shipment_id = shipment.id

            # Auto-load related Landing reference
            if hasattr(po, 'landing_id') and po.landing_id:
                self.landing_id = po.landing_id.id

            # Trigger computation of reference lines
            self._compute_product_lines()
            self._compute_lc_details()
            
    @api.depends('purchase_order_id')
    def _compute_related_documents(self):
        """Find related documents based on the Purchase Order."""
        for record in self:
            if record.purchase_order_id:
                po_id = record.purchase_order_id.id
                record.bank_process_id = self.env['foreign.bank.process'].search([('purchase_order_id', '=', po_id)], limit=1)
                record.shipment_id = self.env['foreign.shipment'].search([('purchase_order_id', '=', po_id)], limit=1)
                record.landing_id = self.env['foreign.landing'].search([('purchase_order_id', '=', po_id)], limit=1)
                record.transit_process_id = self.env['foreign.transit.process'].search([('purchase_order_id', '=', po_id)], limit=1)
            else:
                record.bank_process_id = False
                record.shipment_id = False
                record.landing_id = False
                record.transit_process_id = False

    @api.onchange('payment_request_ids')
    def _onchange_payment_request_ids(self):
        """
        Auto-populate direct cost fields from payment requests and trigger line computation
        """
        self.bank_charge_fx = 0.0
        self.insurance_amount_fx = 0.0
        self.customes_duty_fx = 0.0
        self.freight_charge_fx = 0.0

        payment_costs_by_type = {
            'freight': 0.0,
            'insurance': 0.0,
            'customs': 0.0,
            'bank_charge': 0.0,
        }

        # Process payment requests and accumulate costs by type
        additional_cost_line_commands = []
        
        # Keep existing manual additional costs
        for line in self.additional_cost_line_ids.filtered(lambda l: not l.name.startswith('Payment Request:')):
            additional_cost_line_commands.append((4, line.id))

        for payment_request in self.payment_request_ids:
            for payment_line in payment_request.payment_line_ids:
                # Convert amount to company currency (Birr)
                amount_birr = payment_line.amount
                if payment_line.currency_id and self.env.company.currency_id and \
                   payment_line.currency_id != self.env.company.currency_id:
                    amount_birr = payment_line.currency_id._convert(
                        payment_line.amount,
                        self.env.company.currency_id,
                        self.env.company,
                        fields.Date.today()
                    )

                if payment_line.payment_type in ['supplier', 'other']:
                    # Add 'other' and 'supplier' payment types as additional manual costs
                    additional_cost_line_commands.append((0, 0, {
                        'cost_category': 'other',
                        'name': f"Payment Request: {payment_request.name} - {payment_line.description or payment_line.payment_type}",
                        'description': payment_line.description,
                        'amount_original': payment_line.amount,
                        'currency_id': payment_line.currency_id.id,
                        'amount_birr': amount_birr,
                        'applied_to_cost': True,
                    }))
                else:
                    # Accumulate for direct cost fields using precise mappings from `foreign.payment.request.line`
                    payment_costs_by_type[payment_line.payment_type] += amount_birr

        # Populate direct cost fields
        self.freight_charge_fx = payment_costs_by_type['freight']
        self.insurance_amount_fx = payment_costs_by_type['insurance']
        self.customes_duty_fx = payment_costs_by_type['customs']
        self.bank_charge_fx = payment_costs_by_type['bank_charge']

        # Update additional costs (keeping manual ones, adding 'other' payment types)
        self.additional_cost_line_ids = [(5, 0, 0)] + additional_cost_line_commands

        # Trigger computation of reference lines
        self._compute_payment_cost_lines()

    def action_calculate_costing(self):
        """Automatic calculation trigger - computes all values and updates reference displays"""
        # Trigger all computations
        self._compute_exchange_calculations()
        self._compute_freight_calculation()
        self._compute_total_landed_cost()
        self._compute_cost_factor()
        self._compute_cost_rate_fx()
        self._compute_suggested_values()

        # Trigger reference line updates with current values
        self._compute_product_lines()
        self._compute_payment_cost_lines()

        self.state = 'calculated'
        self.message_post(body="Costing calculations completed automatically with reference displays updated.")

    @api.onchange('purchase_order_id')
    def _onchange_purchase_order_id(self):
        """Auto-populate fields from purchase order and related documents"""
        if self.purchase_order_id:
            po = self.purchase_order_id
            # Clear existing lines
            self.product_line_ids = [(5, 0, 0)]

            # Create product lines from PO lines
            lines_data = []
            for line in po.order_line:
                lines_data.append((0, 0, {
                    'product_id': line.product_id.id,
                    'part_no_fx': line.product_id.default_code or '',
                    'description_of_goods_fx': line.product_id.name or '',
                    'total_quantit_imported_fx': line.product_qty,
                    'unit_price_fx': line.price_unit,
                    'measurmet_unit_fx': line.product_uom.name,
                    'currency_fx': line.currency_id.id, # Set currency from PO line
                }))
            self.product_line_ids = lines_data

            # Set basic amounts from PO
            self.amount_fx = po.amount_untaxed
            self.amount_in_birr_fx = po.amount_untaxed # Assuming this is the initial Birr amount

            # Auto-load related Bank Process (LC details)
            bank_process = self.env['foreign.bank.process'].search([
                ('purchase_order_id', '=', po.id)
            ], limit=1)
            if bank_process:
                self.bank_process_id = bank_process.id
            else:
                self.bank_process_id = False

            # Auto-load related Shipment from foreign.shipment
            shipment = self.env['foreign.shipment'].search([
                ('purchase_order_id', '=', po.id)
            ], limit=1)
            if shipment:
                self.shipment_id = shipment.id
            else:
                self.shipment_id = False # Clear if no relevant shipment found

            # Auto-load related Landing reference (if it exists on PO or can be found via shipment)
            if hasattr(po, 'landing_id') and po.landing_id:
                self.landing_id = po.landing_id.id
            else:
                self.landing_id = False

            # Auto-load related payment requests and process costs
            self._onchange_payment_request_ids() # Trigger payment request processing
            self._compute_lc_details() # Trigger LC details computation

    @api.onchange('payment_request_ids')
    def _onchange_payment_request_ids(self):
        """
        Automatically import costs from selected approved/paid payment requests
        and populate relevant cost fields.
        """
        # Reset direct cost fields that are populated from payment requests
        self.bank_charge_fx = 0.0
        self.insurance_amount_fx = 0.0
        self.customes_duty_fx = 0.0
        self.freight_charge_fx = 0.0

        payment_costs_by_type = {
            'freight': 0.0,
            'insurance': 0.0,
            'customs': 0.0,
            'bank_charge': 0.0,
            'supplier': 0.0, # For display, not direct cost field
        }

        # Prepare lists for One2many commands
        payment_cost_line_commands = []
        additional_cost_line_commands = []

        # 1. Add existing manual additional costs (those not from previous payment imports)
        # We filter out lines that were previously generated from 'other' payment requests
        for line in self.additional_cost_line_ids.filtered(lambda l: not l.name.startswith('Payment Request:')):
            additional_cost_line_commands.append((0, 0, { # Use 0,0 for new transient records
                'cost_category': line.cost_category,
                'name': line.name,
                'description': line.description,
                'amount_original': line.amount_original,
                'currency_id': line.currency_id.id,
                'applied_to_cost': line.applied_to_cost,
                'amount_birr': line.amount_birr, # Keep computed value if it exists
            }))

        for payment_request in self.payment_request_ids:
            for payment_line in payment_request.payment_line_ids:
                # Convert amount to company currency (Birr)
                amount_birr = payment_line.amount
                if payment_line.currency_id and self.env.company.currency_id and \
                   payment_line.currency_id != self.env.company.currency_id:
                    amount_birr = payment_line.currency_id._convert(
                        payment_line.amount,
                        self.env.company.currency_id,
                        self.env.company,
                        fields.Date.today()
                    )
                else:
                    amount_birr = payment_line.amount

                if payment_line.payment_type in ['supplier', 'other']:
                    # Add new 'supplier', 'other' payment types as additional costs
                    additional_cost_line_commands.append((0, 0, {
                        'cost_category': 'other',
                        'name': f"Payment Request: {payment_request.name} - {payment_line.description or payment_line.payment_type}",
                        'description': payment_line.description,
                        'amount_original': payment_line.amount,
                        'currency_id': payment_line.currency_id.id,
                        'amount_birr': amount_birr,
                        'applied_to_cost': True,
                    }))
                else:
                    # Accumulate for direct cost fields and for display in payment_cost_line_ids
                    payment_costs_by_type[payment_line.payment_type] += amount_birr
                    payment_cost_line_commands.append((0, 0, {
                        'payment_request_id': payment_request.id,
                        'payment_line_id': payment_line.id,
                        'payment_type': payment_line.payment_type,
                        'payment_method': payment_line.payment_method,
                        'description': payment_line.description,
                        'amount_original': payment_line.amount,
                        'currency_id': payment_line.currency_id.id,
                        'amount_birr': amount_birr,
                        'applied_to_cost': True, # Always apply if imported
                    }))

        # Populate direct cost fields
        self.freight_charge_fx = payment_costs_by_type['freight']
        self.insurance_amount_fx = payment_costs_by_type['insurance']
        self.customes_duty_fx = payment_costs_by_type['customs']
        self.bank_charge_fx = payment_costs_by_type['bank_charge']

        # Set the One2many fields by clearing existing and adding new/retained ones
        self.payment_cost_line_ids = [(5, 0, 0)] + payment_cost_line_commands
        self.additional_cost_line_ids = [(5, 0, 0)] + additional_cost_line_commands

        # Recalculate total landed cost after updating direct cost fields and additional costs
        self._compute_total_landed_cost()
        self._compute_cost_factor()
        self._compute_suggested_values()

    @api.onchange('transit_process_id')
    def _onchange_transit_process_id(self):
        """Auto-populate costs from the related transit process."""
        if self.transit_process_id:
            transit = self.transit_process_id
            self.customes_duty_fx += transit.customs_duty
            self.vat_amount_fx += transit.vat_amount
            self.excise_tax_fx += transit.excise_tax
            self.sur_tax_fx += transit.sur_tax
            self.withholding_tax_fx += transit.withholding_tax
            self.storage_charge_fx += transit.storage_charges
            # You can decide if handling_charges should go to miscellaneous_fx or a new field
            self.miscellaneous_fx += transit.handling_charges
            # self.message_post() cannot be used in an onchange method as the record is not yet saved.
            # Instead, we return a warning to the user.
            return {
                'warning': {'title': _("Costs Imported"),
                            'message': _("Costs have been successfully imported from Transit Process %s.") % transit.name}
            }

    def action_calculate_costing(self):
        """Manual calculation trigger"""
        self._compute_exchange_calculations()
        self._compute_freight_calculation()
        self._compute_total_landed_cost()
        self._compute_cost_factor()
        self._compute_cost_rate_fx()
        self._compute_suggested_values()

        # Update product lines with current cost rate
        self._update_product_lines()

        self.state = 'calculated'
        self.message_post(body="Costing calculations completed successfully.")

    def _update_product_lines(self):
        """Update all product lines with current cost rate (margin removed from header)"""
        for line in self.product_line_ids:
            # Ensure currency_fx is set if not already
            if not line.currency_fx:
                line.currency_fx = self.duty_fx or self.env.company.currency_id
            line.cost_rate_fx = self.cost_rate_fx

    @api.onchange('cost_rate_fx')  # removed margin fields from onchange
    def _onchange_editable_values(self):
        """Update product lines when editable cost_rate changes (margin removed)."""
        self._update_product_lines()

    def action_confirm(self):
        """Confirm the costing"""
        if not self.product_line_ids:
            raise UserError("Please add at least one product line before confirming.")

        self.state = 'confirmed'
        self.message_post(body="Costing confirmed and ready for processing.")

    def action_done(self):
        """Mark costing as done"""
        self.state = 'done'
        self.message_post(body="Costing process completed.")

    def action_cancel(self):
        """Cancel the costing"""
        self.state = 'cancelled'
        self.message_post(body="Costing cancelled.")

    def action_reset_to_draft(self):
        """Reset to draft state"""
        self.state = 'draft'
        self.message_post(body="Costing reset to draft.")

    def action_create_new_costing(self):
        self.ensure_one()
        new_costing = self.copy({
            'reference': self.env['ir.sequence'].next_by_code('foreign.costing'),
            'date': fields.Date.context_today(self),
            'state': 'draft'
        })
        if not new_costing:
            raise UserError("Failed to create a new costing record.")
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'foreign.costing',
            'res_id': new_costing.id,
            'view_mode': 'form',
            'target': 'current',
            'context': {'form_view_initial_mode': 'edit'}
        }

    @api.constrains('cost_rate_fx')  # removed 'margin_fx' from constraint decorator
    def _check_editable_values(self):
        """Validation for editable cost rate (margin removed from header)."""
        for record in self:
            if record.cost_rate_fx < 0:
                raise ValidationError("Cost rate cannot be negative.")

    @api.model
    def _get_approval_state_mapping(self):
        """
        Provides a mapping from the approval step's NAME to this model's state.
        This is the single source of truth for state synchronization.

        
        """
        return {
           
            'Procurement Manager': 'waiting_for_manager',
            # 'General Manager Step': 'waiting_for_gm', 
            'Director Step': 'waiting_for_director',
            'Finance Manager Step': 'waiting_for_finance',
            'Final': 'approved',
            '__approved__': 'approved',  
            '__rejected__': 'rejected',  # Special key for final rejected status
        }

    def action_submit_for_approval(self):
        """Submit the costing for approval"""
        self.ensure_one()
        if self.state not in ['calculated']:
            raise UserError("Costing must be in 'Calculated' state to be submitted for approval.")

        flow = self.env['approval.flow'].search([
            ('request_model_id.model', '=', self._name),
            ('active', '=', True),
            ('company_id', '=', self.company_id.id)
        ], limit=1)
        if not flow:
            raise UserError("No approval flow defined for Foreign Costing!")

        first_step = self.env['approval.step'].search([
            ('flow_id', '=', flow.id)
        ], order='sequence asc', limit=1)
        if not first_step:
            raise UserError("No steps defined for this approval flow.")

        approval_req = self.env['approval.request'].create({
            'flow_id': flow.id,
            'res_model': self._name,
            'module_name': 'hagbes_procurement_management',
            'res_id': self.id,
            'current_step_id': first_step.id,
            'branch_id': self.branch_id.id,
            'status': 'pending',
        })

        self.write({
            'approval_request_id': approval_req.id
        })
        # This call processes the first step and finds the approvers.
        approval_req.process_action()
        # The sync must be called *after* process_action to get the correct first step.
        self._sync_state_from_approval()
        self.message_post(body="Costing submitted for approval.")

    def _sync_state_from_approval(self):
        """Syncs the state of this record from its approval request."""
        _logger.info("Starting _sync_state_from_approval for %s records.", len(self))
        for rec in self:
            if not rec.approval_request_id:
                _logger.warning("Record %s has no approval_request_id. Skipping sync.", rec.reference)
                continue

    
            rec.approval_request_id.invalidate_recordset(['status', 'current_step_id'])

         
            approval_req = self.env['approval.request'].browse(rec.approval_request_id.id)

            new_state = None
            mapping = rec._get_approval_state_mapping()

            if approval_req.status == 'approved':
                new_state = mapping.get('__approved__')
                _logger.info("Approval request is fully approved. New state: %s", new_state)
            elif approval_req.status == 'rejected':
                new_state = mapping.get('__rejected__')
                _logger.info("Approval request is rejected. New state: %s", new_state)
            elif approval_req.current_step_id:
               
                step_name = (approval_req.current_step_id.name or '').strip()
                new_state = mapping.get(step_name)

                # Fallback to keyword-based mapping so state sync is resilient to label variations.
                if not new_state:
                    normalized_step_name = step_name.lower()
                    if 'finance' in normalized_step_name:
                        new_state = 'waiting_for_finance'
                    elif 'director' in normalized_step_name:
                        new_state = 'waiting_for_director'
                    elif 'general manager' in normalized_step_name or 'gm' in normalized_step_name:
                        new_state = 'waiting_for_gm'
                    elif 'procurement' in normalized_step_name:
                        new_state = 'waiting_for_manager'
                    elif 'final' in normalized_step_name:
                        new_state = 'approved'

                _logger.info(f"Approval Sync: Current Step Name is '{step_name}'. Mapped to state: '{new_state}'")

            final_state = new_state if new_state else 'waiting_for_approval'
            if rec.state != final_state:
                _logger.info(f"Changing Foreign Costing '{rec.reference}' state from '{rec.state}' to '{final_state}'.")
                rec.message_post(body=_("State changed from %s to %s via Approval Flow.") % (rec.state, final_state))
                rec.state = final_state

    def action_manager_approve(self, comment=''):
        self.ensure_one()
        if not self.approval_request_id:
            raise UserError("No approval request linked to this costing.")
        self.approval_request_id.with_context(action_type='approve', comment=comment).process_action()
        self._sync_state_from_approval()

    def action_gm_approve(self, comment=''):
        self.ensure_one()
        if not self.approval_request_id:
            raise UserError("No approval request linked to this costing.")
        self.approval_request_id.with_context(action_type='approve', comment=comment).process_action()
        self._sync_state_from_approval()

    def action_director_approve(self, comment=''):
        self.ensure_one()
        if not self.approval_request_id:
            raise UserError("No approval request linked to this costing.")
        self.approval_request_id.with_context(action_type='approve', comment=comment).process_action()
        self._sync_state_from_approval()

    def action_finance_confirm(self, comment=''):
        self.ensure_one()
        if not self.approval_request_id:
            raise UserError("No approval request linked to this costing.")
        self.approval_request_id.with_context(action_type='approve', comment=comment).process_action()
        self._sync_state_from_approval()
       
        if self.state == 'approved':
            # --- Create and Validate Landed Cost Record ---
            # This is the robust way to update product costs.
            # It creates the landed cost, validates it, and Odoo handles
            # the cost update and accounting entries automatically.
            landed_cost = self.action_create_landed_cost()
            if landed_cost:
                landed_cost.button_validate()
                
                # --- Update Product Selling Prices (Catalog) ---
                updated_products = []
                for line in self.product_line_ids:
                    if line.product_id and line.product_id.product_tmpl_id:
                        # Set the catalog list price to our dynamically calculated margined sales price
                        line.product_id.product_tmpl_id.sudo().write({
                            'list_price': line.usp_after_vat_in_birr_fx
                        })
                        updated_products.append(line.product_id.name)
                        
                if updated_products:
                    self.message_post(body=_(
                        "Successfully updated Catalog Selling Prices for: %s"
                    ) % (', '.join(filter(None, updated_products))))
                
                # --- Flag products for price update ---
                product_ids = landed_cost.mapped('picking_ids.move_ids.product_id')
                templates_to_update = product_ids.mapped('product_tmpl_id')
                if templates_to_update:
                    templates_to_update.sudo().write({'needs_price_update': True})
                    self.message_post(body=_(
                        "The following product templates have been flagged for a standard price update via Landed Costs: %s"
                    ) % (', '.join(templates_to_update.mapped('name'))))
            
            # --- Lock the Purchase Order ---
            if self.purchase_order_id and self.purchase_order_id.state != 'done':
                try:
                    if self.purchase_order_id.state in ['purchase', 'transit_done']:
                        self.purchase_order_id.button_done()
                        self.message_post(body=_("Related Purchase Order %s has been locked.") % self.purchase_order_id.name)
                except UserError as e:
                    self.message_post(body=_("Could not lock Purchase Order %s: %s") % (self.purchase_order_id.name, e))

    def action_create_landed_cost(self):
        """Creates a Landed Cost record from the foreign costing details."""
        self.ensure_one()
        _logger.info("Attempting to create Landed Cost for Foreign Costing: %s", self.reference)

        if self.landed_cost_id:
            raise UserError(_("A landed cost record has already been created for this costing."))

        if not self.purchase_order_id or not self.purchase_order_id.picking_ids:
            raise UserError(_("There are no receipts (pickings) associated with the purchase order. Cannot create landed costs."))

        # Filter for done receipts
        done_pickings = self.purchase_order_id.picking_ids.filtered(lambda p: p.state == 'done' and p.picking_type_code == 'incoming')
        if not done_pickings:
            raise UserError(_("The receipt for Purchase Order %s must be in the 'Done' state to create landed costs. Please receive the products first.") % self.purchase_order_id.name)

        cost_lines = []
        
        # Define a default expense account for landed costs as a fallback
        all_category = self.env.ref('product.product_category_all', raise_if_not_found=False)
        default_expense_account = all_category.property_account_expense_categ_id if all_category else None
        if not default_expense_account:
            raise UserError(_("Please configure a default Expense Account for Product Category 'All'."))

        # Consolidate all additional costs from various sources into logical lines for the landed cost record.
        # We are adding costs on top of the PO price, so we don't include ex_works_in_birr_fx.
        cost_groups = {
            'Freight Charges': self.fright_charge_in_birr_fx,
            'Insurance Charges': self.insurance_amount_fx + self.third_party_fx + self.owen_damage_fx + self.work_mens_fx + self.yellow_card_fx + self.insurance_extension_fx,
            'Customs & Duties': self.customes_duty_fx + self.excise_tax_fx + self.sur_tax_fx,
            'Bank & Financial Charges': self.bank_charge_fx + self.bank_charge_of_eslsc_fx + self.bank_interest_fx,
            'Port & Local Transport': self.container_service_char_fx + self.djibuti_port_expense_fx + self.local_forward_and_clea_fx + self.trans_charge_from_dj_t_fx + self.empty_cont_trans_char_fx + self.trans_charge_to_wareho_fx,
            'Taxes & Fees': self.withholding_tax_fx + self.scanning_fee_fx + self.custom_bond_fx,
            'Storage & Miscellaneous': self.storage_charge_fx + self.miscellaneous_fx + self.rta_fx,
        }

        # Add costs from the consolidated groups
        for name, amount in cost_groups.items():
            if amount > 0:
                # Find a product that represents this cost type or create one
                product = self.env['product.product'].search([('name', '=', name), ('landed_cost_ok', '=', True)], limit=1)
                if not product:
                    product = self.env['product.product'].create({
                        'name': name,
                        'type': 'service',
                        'landed_cost_ok': True,
                        'property_account_expense_id': default_expense_account.id,
                    })

                cost_lines.append((0, 0, {
                    'product_id': product.id,
                    'name': product.name,
                    'account_id': product.property_account_expense_id.id or default_expense_account.id,
                    'split_method': 'by_quantity',
                    'price_unit': amount,
                }))

        # Add costs from the 'additional_cost_line_ids'
        for add_cost in self.additional_cost_line_ids.filtered(lambda l: l.amount_birr > 0):
            product = self.env['product.product'].search([('name', '=', add_cost.name), ('landed_cost_ok', '=', True)], limit=1)
            if not product:
                product = self.env['product.product'].create({
                    'name': add_cost.name,
                    'type': 'service',
                    'landed_cost_ok': True,
                    'property_account_expense_id': default_expense_account.id,
                })
            cost_lines.append((0, 0, {
                'product_id': product.id,
                'name': add_cost.name,
                'account_id': product.property_account_expense_id.id or default_expense_account.id,
                'split_method': 'by_quantity',
                'price_unit': add_cost.amount_birr,
            }))

        if not cost_lines:
            self.message_post(body=_("No additional costs were found to create a Landed Cost record."))
            return None
            
        if self.is_marketing_costing or self.costing_type == 'tentative':
            self.message_post(body=_("Landed Cost Creation skipped because this is a Marketing or Tentative Costing."))
            return None

        stock_journal = None
        if self.purchase_order_id.order_line:
            for line in self.purchase_order_id.order_line:
                if line.product_id.categ_id.property_stock_journal:
                    stock_journal = line.product_id.categ_id.property_stock_journal
                    break
        
        if not stock_journal:
            stock_journal = self.env['account.journal'].search([('type', '=', 'stock')], limit=1)

        if not stock_journal:
            raise UserError(_("Cannot find a stock journal. Please configure a stock journal on the product categories or create a journal with type 'Stock'."))

        landed_cost = self.env['stock.landed.cost'].create({
            'vendor_bill_id': False,
            'picking_ids': [(6, 0, done_pickings.ids)],
            'cost_lines': cost_lines,
            'account_journal_id': stock_journal.id,
        })

        self.landed_cost_id = landed_cost.id
        self.message_post(body=_("Landed Cost record <a href='#' data-oe-model='stock.landed.cost' data-oe-id='%s'>%s</a> has been created and validated, automatically updating product costs.") % (landed_cost.id, landed_cost.name))
        _logger.info("Successfully created Landed Cost record %s for Foreign Costing %s", landed_cost.name, self.reference)
        return landed_cost

    def action_approve(self, comment=''):
        self.ensure_one()
        if not self.approval_request_id:
            raise UserError("No approval request linked to this costing.")
        self.approval_request_id.with_context(action_type='approve', comment=comment).process_action()
        self._sync_state_from_approval()

    def action_reject(self, comment=''):
        self.ensure_one()
        if not self.approval_request_id:
            raise UserError("No approval request linked to this costing.")
        if self.state == 'waiting_for_finance':
            raise UserError("Finance Manager can only accept/approve Costings. Reject is not allowed at this stage.")
        self.approval_request_id.with_context(action_type='Reject', comment=comment).process_action()
        self._sync_state_from_approval()

    def action_amend(self, comment=''):
        self.ensure_one()
        if not self.approval_request_id:
            raise UserError("No approval request linked to this costing.")
        self.approval_request_id.with_context(action_type='amend', comment=comment).process_action()
        self._sync_state_from_approval()

    def action_revert(self, comment=''):
        self.ensure_one()
        if not self.approval_request_id:
            raise UserError("No approval request linked to this costing.")
        self.approval_request_id.with_context(action_type='revert', comment=comment).process_action()
        self._sync_state_from_approval()

    def action_resubmit(self, comment=''):
        self.ensure_one()
        if not self.approval_request_id:
            raise UserError("No approval request linked to this costing.")
        self.approval_request_id.with_context(action_type='resubmit', comment=comment).process_action()
        self._sync_state_from_approval()

    @api.model
    def create(self, vals):
        """ Generate sequence when branch exists """
        # Check if a purchase order is provided and get the branch from it
        if vals.get('purchase_order_id'):
            po = self.env['purchase.order'].browse(vals['purchase_order_id'])
            # Ensure the branch_id is set in vals before proceeding
            vals['branch_id'] = po.branch_id.id

        # Now check if branch_id is present to generate the sequence
        if vals.get('branch_id') and (not vals.get('reference') or vals.get('reference') == 'New'):
            branch = self.env['account.analytic.account'].browse(vals['branch_id'])
            branch_code = branch.code or '00'
            year = datetime.now().year
            seq = self.env['ir.sequence'].next_by_code('foreign.costing')
            vals['reference'] = f"FC{branch_code}{year}{seq[-5:]}"
        # Always return the created record!
        return super(ForeignCosting, self).create(vals)

    is_current_user_approver = fields.Boolean(
        string="Is Current User Approver",
        compute="_compute_is_current_user_approver"
    )

    approver_ids = fields.Many2many(
        'res.users',
        related='approval_request_id.approver_ids',
        string="Current Approvers",
        readonly=True
    )



    @api.depends('state', 'approver_ids')
    def _compute_is_current_user_approver(self):
        for rec in self:
            if rec.approver_ids:
                if self.env.user in rec.approver_ids:
                    _logger.info("✅ User %s (ID: %s) IS an approver for Foreign Costing %s (Reference: %s)", self.env.user.name, self.env.user.id, rec.id, rec.reference)
                    _logger.info("User %s (ID: %s) IS an approver for Foreign Costing %s (Reference: %s)", self.env.user.name, self.env.user.id, rec.id, rec.reference)
                    rec.is_current_user_approver = True
                else:
                    _logger.info("❌ User %s (ID: %s) is NOT an approver for Foreign Costing %s (Reference: %s)", self.env.user.name, self.env.user.id, rec.id, rec.reference)
                    _logger.info("User %s (ID: %s) is NOT an approver for Foreign Costing %s (Reference: %s)", self.env.user.name, self.env.user.id, rec.id, rec.reference)
                    rec.is_current_user_approver = False
            else:
                _logger.info("⚠️ No approvers set for Foreign Costing %s (Reference: %s)", rec.id, rec.reference)
                _logger.info("No approvers set for Foreign Costing %s (Reference: %s)", rec.id, rec.reference)
                rec.is_current_user_approver = False

    def action_update_real_costs(self):
        """Actually update product costs after landed cost validation."""
        self.ensure_one()

        for product_line in self.product_line_ids:
            product = product_line.product_id

            # Calculate what the cost SHOULD BE based on the product line
            calculated_cost = product_line.unit_cost_in_birr_fx

            # Capture old cost for logging, then update the product cost
            p = product.sudo()
            old_cost = getattr(p, 'standard_price', None)
            p.write({
                'standard_price': calculated_cost
            })

            _logger.info(
                "Updated %s: standard_price = %s (was %s)",
                p.display_name, calculated_cost, old_cost
            )

        # Update selling prices based on the newly applied costs
        self._update_selling_prices()

    def _update_selling_prices(self):
        """Update product selling prices based on new costs."""
        for product_line in self.product_line_ids:
            product = product_line.product_id

            # Get the calculated selling price from the product line
            new_selling_price = product_line.usp_after_vat_in_birr_fx

            p = product.sudo()
            old_list = getattr(p, 'list_price', None)
            p.write({
                'list_price': new_selling_price
            })

            _logger.info(
                "Updated %s: list_price = %s (was %s)",
                p.display_name, new_selling_price, old_list
            )

class ForeignCostingPaymentLine(models.Model):
    _name = 'foreign.costing.payment.line'
    _description = 'Foreign Costing Payment Line (Reference Display)'
    _order = 'cost_category, payment_type, id'

    costing_id = fields.Many2one(
        'foreign.costing',
        string='Costing',
        required=True,
        ondelete='cascade'
    )
    payment_request_id = fields.Many2one(
        'foreign.payment.request',
        string='Payment Request',
        required=True,
        readonly=True
    )
    payment_line_id = fields.Many2one(
        'foreign.payment.request.line',
        string='Payment Line',
        required=True,
        readonly=True
    )
    payment_type = fields.Selection([
        ('supplier', 'Supplier Payment'),
        ('freight', 'Freight'),
        ('insurance', 'Insurance'),
        ('customs', 'Customs & Duties'),
        ('bank_charge', 'Bank Charge'),
    ], string='Payment Type', required=True, readonly=True)

    cost_category = fields.Selection([
        ('banking', 'Banking Charges'),
        ('insurance', 'Insurance'),
        ('port_transport', 'Port & Transport'),
        ('taxes_duties', 'Taxes & Duties'),
        ('other', 'Other Costs'),
    ], string='Cost Category', compute='_compute_cost_category', store=True, readonly=True)

    payment_method = fields.Selection([
        ('lc', 'Letter of Credit (LC)'),
        ('tt', 'Telegraphic Transfer (TT)'),
        ('cad', 'Cash Against Documents (CAD)'),
        ('dp', 'Documents Against Payment (D/P)'),
        ('oa', 'Open Account (OA)'),
        ('da', 'Documents Against Acceptance (D/A)'),
        ('cheque', 'Local Cheque'),
        ('cash', 'Cash Payment'),
        ('transfer', 'Local Bank Transfer'),
        ('bg', 'Bank Guarantee'),
        ('sb', 'Standby Letter of Credit (SBLC)'),
    ], string="Payment Method", required=True, readonly=True)

    description = fields.Text(string='Description', required=True, readonly=True)
    amount_original = fields.Float(string='Original Amount', digits=(16, 2), readonly=True)
    currency_id = fields.Many2one('res.currency', string='Original Currency', readonly=True)
    amount_birr = fields.Float(string='Amount in Birr', digits=(16, 2), readonly=True)

    applied_to_cost = fields.Boolean(
        string='Applied to Cost',
        default=True,
        readonly=True,
        help="Reference display - costs are automatically applied to main calculation"
    )

    @api.depends('payment_type')
    def _compute_cost_category(self):
        """Categorize payment types into cost categories"""
        category_mapping = {
            'bank_charge': 'banking',
            'insurance': 'insurance',
            'freight': 'port_transport',
            'customs': 'taxes_duties',
            'supplier': 'other', # Supplier payments are categorized as 'other' for display
            # 'other' payment type is now handled by additional_cost_line_ids
        }
        for record in self:
            record.cost_category = category_mapping.get(record.payment_type, 'other')

class ForeignCostingProductLine(models.Model):
    _name = 'foreign.costing.product.line'
    _description = 'Foreign Costing Product Line (Reference Display)'
    _rec_name = 'part_no_fx'

    costing_id = fields.Many2one(
        'foreign.costing',
        string='Costing',
        required=True,
        ondelete='cascade'
    )
    product_id = fields.Many2one(
        'product.product',
        string='Product',
        readonly=True,
        help="Product from Purchase Order"
    )
    
    part_no_fx = fields.Char(
        string='Part Number',
        readonly=True,
        help="Product part number from Purchase Order"
    )
    description_of_goods_fx = fields.Text(
        string='Description of Goods',
        readonly=True,
        help="Product description from Purchase Order"
    )
    total_quantit_imported_fx = fields.Float(
        string='Total Quantity Imported',
        digits=(16, 2),
        readonly=True,
        help="Quantity from Purchase Order"
    )
    measurmet_unit_fx = fields.Char(
        string='Measurement Unit',
        size=20,
        readonly=True,
        help="Unit from Purchase Order"
    )
    measurement_per_unit_fx = fields.Float(
        string='Measurement Per Unit',
        digits=(16, 4),
        help="Editable measurement value per unit"
    )
    total_measurement_fx = fields.Char(
        string='Total Measurement',
        compute='_compute_total_measurement',
        store=True,
        readonly=True,
        help="Computed total measurement"
    )
    unit_price_fx = fields.Float(
        string='Unit Price',
        digits=(16, 4),
        readonly=True,
        help="Unit price from Purchase Order"
    )
    currency_fx = fields.Many2one(
        'res.currency',
        string='Currency',
        readonly=True,
        help="Currency from Purchase Order"
    )
    cost_rate_fx = fields.Float(
        string='Cost Rate',
        digits=(16, 6),
        readonly=True,
        help="Cost rate from header calculations"
    )
    margin_fx = fields.Float(
        string='Margin',
        digits=(16, 4),
        readonly=True,
        help="Margin factor from header calculations"
    )
    
    unit_cost_in_birr_fx = fields.Float(
        string='Unit Cost in Birr',
        digits=(16, 4),
        compute='_compute_pricing',
        store=True,
        readonly=True,
        help="Auto-calculated unit cost"
    )
    usp_before_vat_in_birr_fx = fields.Float(
        string='USP Before VAT in Birr',
        digits=(16, 4),
        compute='_compute_pricing',
        store=True,
        readonly=True,
        help="Auto-calculated USP before VAT"
    )
    usp_after_vat_in_birr_fx = fields.Float(
        string='USP After VAT in Birr',
        digits=(16, 4),
        compute='_compute_pricing',
        store=True,
        readonly=True,
        help="Auto-calculated USP after VAT"
    )
    usp_after_vat_app_fx = fields.Float(
        string='USP After VAT Approximated',
        digits=(16, 0),
        compute='_compute_pricing',
        store=True,
        readonly=True,
        help="Auto-calculated approximated USP"
    )
    usp_bfore_vat_app_fx = fields.Float(
        string='USP Before VAT Approximated',
        digits=(16, 4),
        compute='_compute_pricing',
        store=True,
        readonly=True,
        help="Auto-calculated approximated USP before VAT"
    )

    usp_after_vat_manual = fields.Float(
        string='USP After VAT (Manual Override)',
        digits=(16, 4),
        help="Manual override for USP After VAT calculation - only editable field"
    )

    @api.depends('total_quantit_imported_fx', 'measurement_per_unit_fx', 'measurmet_unit_fx')
    def _compute_total_measurement(self):
        for record in self:
            if record.total_quantit_imported_fx and record.measurement_per_unit_fx:
                total = record.total_quantit_imported_fx * record.measurement_per_unit_fx
                unit = record.measurmet_unit_fx or ''
                record.total_measurement_fx = f"{total} {unit}".strip()
            else:
                record.total_measurement_fx = ''

    @api.depends('cost_rate_fx', 'unit_price_fx', 'margin_fx', 'usp_after_vat_manual', 'currency_fx', 'costing_id.duty_fx')
    def _compute_pricing(self):
        """Calculate all pricing fields using margin."""
        for record in self:
            converted_unit_price = record.unit_price_fx
            if record.currency_fx and record.costing_id.duty_fx and record.currency_fx != record.costing_id.duty_fx:
                converted_unit_price = record.currency_fx._convert(
                    record.unit_price_fx,
                    record.costing_id.duty_fx,
                    record.costing_id.company_id,
                    fields.Date.today()
                )

            margin_multiplier = record.margin_fx if record.margin_fx else 1.0

            record.unit_cost_in_birr_fx = record.cost_rate_fx * converted_unit_price
            record.usp_before_vat_in_birr_fx = record.unit_cost_in_birr_fx * margin_multiplier

            calculated_usp_after_vat = round(record.unit_cost_in_birr_fx * 1.15 * margin_multiplier, 2)

            if (record.usp_after_vat_manual and
                round(record.usp_after_vat_manual, 2) != calculated_usp_after_vat):
                record.usp_after_vat_in_birr_fx = record.usp_after_vat_manual
                record.usp_after_vat_app_fx = math.ceil(record.usp_after_vat_manual)
                record.usp_bfore_vat_app_fx = record.usp_after_vat_app_fx / 1.15
            else:
                record.usp_after_vat_in_birr_fx = calculated_usp_after_vat
                record.usp_after_vat_app_fx = math.ceil(calculated_usp_after_vat)
                record.usp_bfore_vat_app_fx = record.usp_after_vat_app_fx / 1.15

    @api.onchange('usp_after_vat_app_fx')
    def _onchange_usp_after_vat_app(self):
        """Recalculate before VAT approximated when after VAT approximated changes"""
        if self.usp_after_vat_app_fx:
            self.usp_bfore_vat_app_fx = self.usp_after_vat_app_fx / 1.15

    @api.onchange('product_id')
    def _onchange_product_id(self):
        """Auto-fill product information when product is selected"""
        if self.product_id:
            self.part_no_fx = self.product_id.default_code or ''
            self.description_of_goods_fx = self.product_id.name or ''
            self.measurmet_unit_fx = self.product_id.uom_id.name or ''
            self.currency_fx = self.product_id.currency_id or self.costing_id.duty_fx or self.env.company.currency_id

    @api.model
    def create(self, vals):
        """Auto-inherit values from costing header on creation (do not inherit header margin)."""
        if vals.get('product_id'):
            product = self.env['product.product'].browse(vals['product_id'])
            vals['part_no_fx'] = product.default_code or ''
            vals['description_of_goods_fx'] = product.name or ''
            vals['measurmet_unit_fx'] = product.uom_id.name or ''
            vals['currency_fx'] = product.currency_id.id if product.currency_id else False

        # Auto-inherit cost rate and margin from header
        if vals.get('costing_id'):
            costing = self.env['foreign.costing'].browse(vals['costing_id'])
            if not vals.get('cost_rate_fx'):
                vals['cost_rate_fx'] = costing.cost_rate_fx
            if not vals.get('margin_fx'):
                vals['margin_fx'] = costing.margin_fx
            if not vals.get('currency_fx'):
                vals['currency_fx'] = costing.duty_fx.id if costing.duty_fx else self.env.company.currency_id.id

        return super().create(vals)

    def write(self, vals):
        """Update product information when product changes"""
        if vals.get('product_id'):
            product = self.env['product.product'].browse(vals['product_id'])
            vals['part_no_fx'] = product.default_code or ''
            vals['description_of_goods_fx'] = product.name or ''
            vals['measurmet_unit_fx'] = product.uom_id.name or ''
            vals['currency_fx'] = product.currency_id.id if product.currency_id else False

        return super().write(vals)

class ForeignCostingAdditionalCost(models.Model):
    _name = 'foreign.costing.additional.cost'
    _description = 'Foreign Costing Additional Manual Cost'
    _order = 'cost_category, sequence, id'

    costing_id = fields.Many2one(
        'foreign.costing',
        string='Costing',
        required=True,
        ondelete='cascade'
    )
    sequence = fields.Integer(string='Sequence', default=10)
    cost_category = fields.Selection([
        ('banking', 'Banking Charges'),
        ('insurance', 'Insurance'),
        ('port_transport', 'Port & Transport'),
        ('taxes_duties', 'Taxes & Duties'),
        ('other', 'Other Costs'),
    ], string='Cost Category', required=True, default='other')

    name = fields.Char(string='Cost Name', required=True)
    description = fields.Text(string='Description')

    amount_original = fields.Float(string='Amount', digits=(16, 2), required=True)
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        required=True,
        default=lambda self: self.env.company.currency_id
    )
    amount_birr = fields.Float(
        string='Amount in Birr',
        digits=(16, 2),
        compute='_compute_amount_birr',
        store=True
    )
    applied_to_cost = fields.Boolean(
        string='Applied to Cost',
        default=True,
        help="Whether this additional cost is applied to the costing calculation"
    )

    @api.depends('amount_original', 'currency_id')
    def _compute_amount_birr(self):
        """Convert amount to company currency (Birr)"""
        for record in self:
            if record.currency_id and record.costing_id.env.company.currency_id and \
               record.currency_id != record.costing_id.env.company.currency_id:
                record.amount_birr = record.currency_id._convert(
                    record.amount_original,
                    record.costing_id.env.company.currency_id,
                    record.costing_id.env.company,
                    fields.Date.today()
                )
            else:
                record.amount_birr = record.amount_original

    @api.constrains('amount_original')
    def _check_amount(self):
        for record in self:
            if record.amount_original <= 0:
                raise ValidationError("Amount must be greater than zero.")

class ForeignCostingProductLine(models.Model):
    _name = 'foreign.costing.product.line'
    _description = 'Foreign Costing Product Line'
    _rec_name = 'part_no_fx'

    costing_id = fields.Many2one(
        'foreign.costing',
        string='Costing',
        required=True,
        ondelete='cascade'
    )
    product_id = fields.Many2one(
        'product.product',
        string='Product',
        help="Select product to auto-fill part number and description"
    )
    # Basic Product Information
    part_no_fx = fields.Char(
        string='Part Number',
        readonly=True,
        help="Product part number (auto-filled from product)"
    )
    description_of_goods_fx = fields.Text(
        string='Description of Goods',
        readonly=True,
        help="Product description (auto-filled from product)"
    )
    # Quantity and Measurement
    total_quantit_imported_fx = fields.Float(
        string='Total Quantity Imported',
        digits=(16, 2),
        help="Total quantity being imported"
    )
    measurmet_unit_fx = fields.Char(
        string='Measurement Unit',
        size=20,
        help="Unit of measurement (kg, pcs, etc.)"
    )
    measurement_per_unit_fx = fields.Float(
        string='Measurement Per Unit',
        digits=(16, 4),
        help="Measurement value per unit"
    )
    total_measurement_fx = fields.Char(
        string='Total Measurement',
        compute='_compute_total_measurement',
        store=True,
        help="Total Quantity × Measurement Per Unit + Unit"
    )
    # Pricing
    unit_price_fx = fields.Float(
        string='Unit Price',
        digits=(16, 4),
        help="Unit price in foreign currency"
    )
    # Changed currency_fx to Many2one
    currency_fx = fields.Many2one(
        'res.currency',
        string='Currency',
        help="Currency code (USD, EUR, etc.) for the unit price"
    )
    cost_rate_fx = fields.Float(
        string='Cost Rate',
        digits=(16, 6),
        help="Cost rate from header calculations"
    )
    margin_fx = fields.Float(
        string='Margin',
        digits=(16, 4),
        help="Margin factor from header calculations"
    )
    # Calculated Pricing Fields
    unit_cost_in_birr_fx = fields.Float(
        string='Unit Cost in Birr',
        digits=(16, 4),
        compute='_compute_pricing',
        store=True,
        help="Cost Rate × Unit Price (converted to main foreign currency)"
    )
    usp_before_vat_in_birr_fx = fields.Float(
        string='USP Before VAT in Birr',
        digits=(16, 4),
        compute='_compute_pricing',
        store=True,
        help="Unit Cost in Birr × Margin"
    )
    usp_after_vat_in_birr_fx = fields.Float(
        string='USP After VAT in Birr',
        digits=(16, 4),
        compute='_compute_pricing',
        store=True,
        help="Unit Cost in Birr × Margin × 1.15"
    )
    usp_after_vat_app_fx = fields.Float(
        string='USP After VAT Approximated',
        digits=(16, 0),
        compute='_compute_pricing',
        store=True,
        help="Ceiling of USP After VAT"
    )
    usp_bfore_vat_app_fx = fields.Float(
        string='USP Before VAT Approximated',
        digits=(16, 4),
        compute='_compute_pricing',
        store=True,
        help="USP After VAT Approximated ÷ 1.15"
    )
    # Manual override
    usp_after_vat_manual = fields.Float(
        string='USP After VAT (Manual)',
        digits=(16, 4),
        help="Manual override for USP After VAT calculation"
    )

    @api.depends('total_quantit_imported_fx', 'measurement_per_unit_fx', 'measurmet_unit_fx')
    def _compute_total_measurement(self):
        for record in self:
            if record.total_quantit_imported_fx and record.measurement_per_unit_fx:
                total = record.total_quantit_imported_fx * record.measurement_per_unit_fx
                unit = record.measurmet_unit_fx or ''
                record.total_measurement_fx = f"{total} {unit}".strip()
            else:
                record.total_measurement_fx = ''

    @api.depends('cost_rate_fx', 'unit_price_fx', 'usp_after_vat_manual', 'currency_fx', 'costing_id.duty_fx')
    def _compute_pricing(self):
        """Calculate all pricing fields without using margin (margin removed)."""
        for record in self:
            converted_unit_price = record.unit_price_fx
            if record.currency_fx and record.costing_id.duty_fx and record.currency_fx != record.costing_id.duty_fx:
                converted_unit_price = record.currency_fx._convert(
                    record.unit_price_fx,
                    record.costing_id.duty_fx,
                    record.costing_id.company_id,
                    fields.Date.today()
                )

            # No margin factor: assume 1.0
            margin_factor = 1.0

            record.unit_cost_in_birr_fx = record.cost_rate_fx * converted_unit_price
            record.usp_before_vat_in_birr_fx = record.unit_cost_in_birr_fx * margin_factor

            calculated_usp_after_vat = round(record.unit_cost_in_birr_fx * 1.15 * margin_factor, 2)

            if (record.usp_after_vat_manual and
                round(record.usp_after_vat_manual, 2) != calculated_usp_after_vat):
                record.usp_after_vat_in_birr_fx = record.usp_after_vat_manual
                record.usp_after_vat_app_fx = math.ceil(record.usp_after_vat_manual)
                record.usp_bfore_vat_app_fx = record.usp_after_vat_app_fx / 1.15
            else:
                record.usp_after_vat_in_birr_fx = calculated_usp_after_vat
                record.usp_after_vat_app_fx = math.ceil(calculated_usp_after_vat)
                record.usp_bfore_vat_app_fx = record.usp_after_vat_app_fx / 1.15

    @api.onchange('usp_after_vat_app_fx')
    def _onchange_usp_after_vat_app(self):
        """Recalculate before VAT approximated when after VAT approximated changes"""
        if self.usp_after_vat_app_fx:
            self.usp_bfore_vat_app_fx = self.usp_after_vat_app_fx / 1.15

    def action_view_cost_history(self):
        """Open a view showing historical costings for this product."""
        self.ensure_one()
        return {
            'name': 'Cost History for %s' % self.product_id.display_name,
            'type': 'ir.actions.act_window',
            'res_model': 'foreign.costing.product.line',
            'view_mode': 'list,form',
            'domain': [
                ('product_id', '=', self.product_id.id),
                ('costing_id.state', 'in', ['approved', 'confirmed', 'done']),
                ('id', '!=', self.id)
            ],
            'context': {
                'create': False,
                'edit': False,
                'delete': False
            }
        }

    @api.onchange('product_id')
    def _onchange_product_id(self):
        """Auto-fill product information when product is selected"""
        if self.product_id:
            self.part_no_fx = self.product_id.default_code or ''
            self.description_of_goods_fx = self.product_id.name or ''
            self.measurmet_unit_fx = self.product_id.uom_id.name or ''
            self.currency_fx = self.product_id.currency_id or self.costing_id.duty_fx or self.env.company.currency_id

    @api.model
    def create(self, vals):
        """Auto-inherit values from costing header on creation (do not inherit header margin)."""
        if vals.get('product_id'):
            product = self.env['product.product'].browse(vals['product_id'])
            vals['part_no_fx'] = product.default_code or ''
            vals['description_of_goods_fx'] = product.name or ''
            vals['measurmet_unit_fx'] = product.uom_id.name or ''
            vals['currency_fx'] = product.currency_id.id if product.currency_id else False

        # Auto-inherit cost rate from header only (do not inherit header margin)
        if vals.get('costing_id'):
            costing = self.env['foreign.costing'].browse(vals['costing_id'])
            if not vals.get('cost_rate_fx'):
                vals['cost_rate_fx'] = costing.cost_rate_fx
            # removed: vals['margin_fx'] = costing.margin_factor_fx
            if not vals.get('currency_fx'):
                vals['currency_fx'] = costing.duty_fx.id if costing.duty_fx else self.env.company.currency_id.id

        return super().create(vals)

    def write(self, vals):
        """Update product information when product changes"""
        if vals.get('product_id'):
            product = self.env['product.product'].browse(vals['product_id'])
            vals['part_no_fx'] = product.default_code or ''
            vals['description_of_goods_fx'] = product.name or ''
            vals['measurmet_unit_fx'] = product.uom_id.name or ''
            vals['currency_fx'] = product.currency_id.id if product.currency_id else False

        return super().write(vals)

class ForeignCostingAdditionalCost(models.Model):
    _name = 'foreign.costing.additional.cost'
    _description = 'Foreign Costing Additional Manual Cost'
    _order = 'cost_category, sequence, id'

    costing_id = fields.Many2one(
        'foreign.costing',
        string='Costing',
        required=True,
        ondelete='cascade'
    )
    sequence = fields.Integer(string='Sequence', default=10)
    cost_category = fields.Selection([
        ('banking', 'Banking Charges'),
        ('insurance', 'Insurance'),
        ('port_transport', 'Port & Transport'),
        ('taxes_duties', 'Taxes & Duties'),
        ('other', 'Other Costs'),
    ], string='Cost Category', required=True, default='other')

    name = fields.Char(string='Cost Name', required=True)
    description = fields.Text(string='Description')

    amount_original = fields.Float(string='Amount', digits=(16, 2), required=True)
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        required=True,
        default=lambda self: self.env.company.currency_id
    )
    amount_birr = fields.Float(
        string='Amount in Birr',
        digits=(16, 2),
        compute='_compute_amount_birr',
        store=True
    )
    applied_to_cost = fields.Boolean(
        string='Applied to Cost',
        default=True,
        help="Whether this additional cost is applied to the costing calculation"
    )

    @api.depends('amount_original', 'currency_id')
    def _compute_amount_birr(self):
        """Convert amount to company currency (Birr)"""
        for record in self:
            if record.currency_id and record.costing_id.env.company.currency_id and \
               record.currency_id != record.costing_id.env.company.currency_id:
                record.amount_birr = record.currency_id._convert(
                    record.amount_original,
                    record.costing_id.env.company.currency_id,
                    record.costing_id.env.company,
                    fields.Date.today()
                )
            else:
                record.amount_birr = record.amount_original

    @api.constrains('amount_original')
    def _check_amount(self):
        for record in self:
            if record.amount_original <= 0:
                raise ValidationError("Amount must be greater than zero.")
