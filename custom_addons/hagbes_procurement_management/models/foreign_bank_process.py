from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime
class ForeignBankProcess(models.Model):
    _name = 'foreign.bank.process'
    _description = 'Foreign Bank Process'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc, id desc'
    _rec_name = 'name'

    # Basic Information
    name = fields.Char(
        string='Process Number',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New')
    )
    
    process_date = fields.Date(
        string='Process Date',
        required=True,
        default=fields.Date.context_today,
        tracking=True
    )

    # Relations
    payment_request_id = fields.Many2one(
        'foreign.payment.request',
        string='Payment Request',
        tracking=True
    )
    
    purchase_request_id = fields.Many2one(
        'purchase.request',
        string='Purchase Request',
        required=True,
        tracking=True
    )
    
    purchase_order_id = fields.Many2one(
        'purchase.order',
        string='Purchase Order',
        domain=[('order_type', '=', 'foreign'), ('purchase_request_id', '=', purchase_request_id)],
        required=False,
        tracking=True
    )
    
    supplier_id = fields.Many2one(
        'res.partner',
        string='Supplier',
        compute='_compute_supplier_from_pr',
        store=True,
        readonly=True,
        tracking=True
    )

    # Payment Method
    payment_method = fields.Selection([
        ('tt', 'TT (Telegraphic Transfer)'),
        ('cad', 'CAD (Cash Against Documents)'),
        ('lc', 'LC (Letter of Credit)'),
        ('oa', 'OA (Open Account)'), 
    ], string='Payment Method', required=False, tracking=True)

    # Currency and Amount
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        required=True,
        tracking=True
    )
    
    amount = fields.Monetary(
        string='Currency Amount',
        currency_field='currency_id',
        required=True,
        tracking=True
    )
    branch_id = fields.Many2one(
        'account.analytic.account',
        string='Branch',
        compute='_compute_branch_from_pr',
        store=True,
        tracking=True,
        readonly=True
    )


    # Bank Process States
    state = fields.Selection([
        ('order_info', 'Order Information'),
        ('waiting_currency', 'Waiting for Foreign Currency'),
        ('under_bank_process', 'Under Bank Process'),
        ('waiting_shipment', 'Waiting for Shipment'),
        ('document_handover', 'Document Hand Over'),
        ('documents_at_bank', 'Documents at Bank'),
        ('under_customs', 'Under Customs Process'),
        ('cleared_delivered', 'Cleared and Delivered'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='order_info', tracking=True, required=True)

    # Order Information Fields
    delivery_method = fields.Selection([
        ('sea', 'Sea Transport'),
        ('air', 'Air Transport'),
        ('land', 'Land Transport'),
    ], string='Delivery Method', tracking=True)
    
    payment_term = fields.Selection([
        ('tt', 'Telegraphic Transfer'),
        ('cad', 'Cash Against Documents'),
        ('lc', 'Letter of Credit)'),
    ], string='Payment Term', required=False, tracking=True)
    
    mode_of_transport = fields.Selection([
        ('sea', 'Sea Transport'),
        ('air', 'Air Transport'),
        ('land', 'Land Transport'),
        ('multi_modal', 'Multi Modal'),
        ('uni_modal', 'Uni Modal'),
    ], string='Mode of Transport', tracking=True)
    
    order_for = fields.Char(string='Order For', tracking=True)

    # Under Bank Process Fields
    fc_allocation_date = fields.Date(string='F/C Allocation Date', tracking=True)
    bank_name = fields.Char(string='Bank Name', tracking=True)
    bank_remark = fields.Text(string='Remark', tracking=True)

    # Waiting for Shipment Fields
    lc_cad_tt_date = fields.Date(string='LC/CAD/TT Date', tracking=True)
    lc_cad_tt_no = fields.Char(string='LC/CAD/TT No', tracking=True)
    shipment_remark = fields.Text(string='Remark', tracking=True)

    # Goods in Transit Fields
    bl_awb_dhl_no = fields.Char(string='BL/AWB/DHL No', tracking=True)
    bl_awb_dhl_date = fields.Date(string='BL/AWB/DHL Date', tracking=True)
    copy_docu_deli_to_tf = fields.Date(string='Copy Docu. Deli. To TF', tracking=True)
    gross_weight = fields.Float(string='Gross Weight', tracking=True)
    no_of_package_container = fields.Integer(string='No. Of Package/Container', tracking=True)
    transit_remark = fields.Text(string='Remark', tracking=True)

    # Documents at Bank Fields
    document_arrival_date = fields.Date(string='Document Arrival Date', tracking=True)
    freight_invoice_settled_on = fields.Date(string='Freight Invoice Settled on', tracking=True)
    document_bank_remark = fields.Text(string='Remark', tracking=True)
    document_type_received = fields.Selection([
        ('tt_docs', 'TT Documents'),
        ('lc_docs', 'LC Documents'),
        ('cad_docs', 'CAD Documents'),
    ], string='Received Document Type', tracking=True)

    # Under Customs / Settlement Fields
    doc_collected_from_bank = fields.Date(string='Doc Collected From Bank', tracking=True)
    original_doc_deli_to_tf = fields.Date(string='Original Doc Deli. To TF', tracking=True)
    customs_remark = fields.Text(string='Remark', tracking=True)
    
    settlement_date = fields.Date(string='Settlement Date', tracking=True)
    settlement_rate = fields.Float(string='Settlement Rate', digits=(16, 6), tracking=True)
    freight_amount = fields.Monetary(string='Freight Amount', currency_field='currency_id', tracking=True)
    customs_amount = fields.Monetary(string='Customs Amount', currency_field='currency_id', tracking=True)

    # Process Dates
    currency_received_date = fields.Date(string='Currency Received Date', tracking=True)
    bank_process_start_date = fields.Date(string='Bank Process Start Date', tracking=True)
    completion_date = fields.Date(string='Completion Date', tracking=True)

    # Additional Information
    notes = fields.Text(string='Notes', tracking=True)

    # Computed Fields
    days_in_process = fields.Integer(
        string='Days in Process',
        compute='_compute_days_in_process'
    )
    
    transit_process_count = fields.Integer(
        string='Transit Process Count',
        compute='_compute_transit_process_count'
    )


    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True
    )

    # One2many fields for related data
    pfi_ids = fields.One2many(
        'foreign.bank.process.pfi',
        'bank_process_id',
        string='PFI Details'
    )

    lc_tracking_ids = fields.One2many(
        'foreign.bank.process.lc.tracking',
        'bank_process_id',
        string='LC Tracking'
    )

    shipment_id = fields.Many2one(
        'foreign.shipment',
        string="Shipment Record",
        help="Link to the main shipment tracking record for this process."
    )
    customer_ids = fields.One2many(
        'foreign.bank.process.customer',
        'bank_process_id',
        string='Customers'
    )

    container_ids = fields.One2many(
        'foreign.bank.process.container',
        'bank_process_id',
        string='Containers'
    )

    transit_process_ids = fields.One2many(
        'foreign.transit.process',
        'bank_process_id',
        string='Transit Processes'
    )
    
    bank_allocation_ids = fields.One2many(
        'foreign.bank.allocation',
        'bank_process_id',
        string='Bank Allocations'
    )

  
    @api.onchange('purchase_request_id')
    def _onchange_purchase_request_id(self):
        """Auto-populate fields from Purchase Request"""
        if self.purchase_request_id:
            self.currency_id = self.purchase_request_id.currency_id
            self.amount = self.purchase_request_id.amount_total
            self.branch_id = self.purchase_request_id.branch_id.id
            
            # Find related Payment Request if any
            payment_request = self.env['foreign.payment.request'].search([
                ('purchase_order_id.purchase_request_id', '=', self.purchase_request_id.id)
            ], limit=1)

            if payment_request:
                methods = payment_request.payment_line_ids.mapped('payment_method')
                self.payment_method = methods[0] if methods else False  
            else:
                self.payment_method = False

    @api.onchange('purchase_order_id')
    def _onchange_purchase_order_id(self):
        if self.purchase_order_id:
             self.delivery_method = getattr(self.purchase_order_id, 'delivery_method', False)


    @api.depends('purchase_request_id')
    def _compute_branch_from_pr(self):
        for record in self:
            if record.purchase_request_id:
                record.branch_id = record.purchase_request_id.branch_id
            else:
                record.branch_id = False

    @api.depends('purchase_request_id')
    def _compute_supplier_from_pr(self):
        for record in self:
            if record.purchase_request_id:
                record.supplier_id = record.purchase_request_id.vendor_id
            else:
                record.supplier_id = False

    @api.depends('transit_process_ids')
    def _compute_transit_process_count(self):
        for record in self:
            record.transit_process_count = len(record.transit_process_ids)


    @api.depends('process_date', 'state')
    def _compute_days_in_process(self):
        today = fields.Date.context_today(self)
        for record in self:
            if record.state in ['completed', 'cancelled']:
                if record.completion_date:
                    record.days_in_process = (record.completion_date - record.process_date).days
                else:
                    record.days_in_process = 0
            else:
                record.days_in_process = (today - record.process_date).days

                 # Generate unique process number
    @api.model
    def create(self, vals):
        """ Generate sequence when branch exists """
        # Check if a purchase request is provided and get the branch from it
        if vals.get('purchase_request_id'):
            pr = self.env['purchase.request'].browse(vals['purchase_request_id'])
            # Ensure the branch_id is set in vals before proceeding
            vals['branch_id'] = pr.branch_id.id

        # Now check if branch_id is present to generate the sequence
        if vals.get('branch_id') and (not vals.get('name') or vals.get('name') == 'New'):
            branch = self.env['account.analytic.account'].browse(vals['branch_id'])
            branch_code = branch.code or '00'
            year = datetime.now().year
            seq = self.env['ir.sequence'].next_by_code('foreign.bank.process')
            vals['name'] = f"BF{branch_code}{year}{seq[-5:]}"
        
        return super().create(vals)

    # --- State Transition Methods with Validations ---

    def action_waiting_currency(self):
        self.ensure_one()
        if not self.pfi_ids:
            raise UserError(_('Please add at least one PFI detail before moving to Waiting for Foreign Currency.'))
        for pfi in self.pfi_ids:
            if not pfi.pfi_number or not pfi.pfi_date_submit_to_bank:
                raise UserError(_('Please ensure all PFI lines have a PFI Number and a Submission Date to the bank.'))

        self.state = 'waiting_currency'
        self.message_post(body=_('Moved to waiting for foreign currency.'))

    def action_under_bank_process(self):
        self.ensure_one()
        if not self.fc_allocation_date or not self.bank_name:
            raise UserError(_('Please provide the F/C Allocation Date and Bank Name before starting the bank process.'))

        self.state = 'under_bank_process'
        self.bank_process_start_date = fields.Date.context_today(self)
        self.message_post(body=_('Bank process started.'))

    def action_waiting_shipment(self):
        self.ensure_one()
        if not self.lc_cad_tt_no or not self.lc_cad_tt_date:
            raise UserError(_('Please provide the LC/CAD/TT Number and Date before proceeding.'))
        if self.payment_method == 'lc' and not self.lc_tracking_ids:
            raise UserError(_('For LC payments, please add at least one LC Tracking record.'))

        # Check if we need to create the Purchase Order from the Request
        if not self.purchase_order_id and self.purchase_request_id:
            pr = self.purchase_request_id
            
            po_lines = []
            for line in pr.request_line_ids:
                po_lines.append((0, 0, {
                    'product_id': line.product_id.id,
                    'name': line.description or line.product_id.name,
                    'product_qty': line.quantity,
                    'product_uom': line.product_id.uom_po_id.id or line.product_id.uom_id.id,
                    'price_unit': line.estimated_price,
                    'date_planned': pr.required_date or fields.Date.context_today(self),
                }))
                
            po_vals = {
                'partner_id': pr.vendor_id.id if pr.vendor_id else self.env.company.partner_id.id,
                'order_type': 'foreign',
                'purchase_request_id': pr.id,
                'currency_id': pr.currency_id.id,
                'branch_id': pr.branch_id.id,
                'order_line': po_lines,
                'document_order_number': f"DOC-{self.name}",
            }
            
            new_po = self.env['purchase.order'].create(po_vals)
            self.purchase_order_id = new_po.id
            self.message_post(body=_('Purchase Order %s generated from Request.') % new_po.name)

      
        if self.purchase_order_id and self.purchase_order_id.state in ['draft', 'sent']:
           
            if not self.purchase_order_id.document_order_number:
                self.purchase_order_id.document_order_number = f"DOC-{self.name}"

        self.state = 'waiting_shipment'
        self.message_post(body=_('Waiting for shipment. Purchase Order ready for manual confirmation.'))

    def action_document_handover(self):
        self.ensure_one()
        # Auto-populate from related tracking records if empty
        if not self.bl_awb_dhl_no:
            if self.shipment_id and self.shipment_id.tracking_number:
                self.bl_awb_dhl_no = self.shipment_id.tracking_number
            elif self.container_ids:
                self.bl_awb_dhl_no = self.container_ids[0].bl_number

        if not self.gross_weight and self.container_ids:
            self.gross_weight = sum(self.container_ids.mapped('gross_weight'))

        if not self.bl_awb_dhl_date:
            self.bl_awb_dhl_date = fields.Date.context_today(self)

        self.state = 'document_handover'
        self.message_post(body=_('Documents handed over to transit.'))

    def action_documents_at_bank(self):
        self.ensure_one()
        if not self.document_arrival_date:
            raise UserError(_('Please specify the Document Arrival Date.'))

        self.state = 'documents_at_bank'
        self.message_post(body=_('Documents received at bank.'))

    def action_under_customs(self):
        self.ensure_one()
        if not self.doc_collected_from_bank:
            raise UserError(_('Please specify the date documents were collected from the bank.'))

        self.state = 'under_customs'
        self.message_post(body=_('Under customs process.'))

    def action_cleared_delivered(self):
        self.ensure_one()
        self.state = 'cleared_delivered'
        self.message_post(body=_('Goods cleared and delivered.'))

    def action_complete(self):
        self.ensure_one()
        self.state = 'completed'
        self.completion_date = fields.Date.context_today(self)
        self.message_post(body=_('Bank process completed.'))

    def action_cancel(self):
        self.ensure_one()
        self.state = 'cancelled'
        self.message_post(body=_('Bank process cancelled.'))

    def action_view_transit_processes(self):
        self.ensure_one()
        return {
            'name': _('Transit Processes'),
            'type': 'ir.actions.act_window',
            'res_model': 'foreign.transit.process',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.transit_process_ids.ids)],
            'context': {'default_bank_process_id': self.id}
        }

    def action_open_transit_live_tracking(self):
        """
        Finds the related transit process and calls its live tracking action.
        This acts as a bridge from the bank process to the transit tracking.
        """
        self.ensure_one()
        # Find the first transit process linked to this bank process
        transit_process = self.transit_process_ids and self.transit_process_ids[0]
        if not transit_process:
            raise UserError(_("No related Transit Process found. Tracking is managed from the transit record."))
        return transit_process.action_open_live_tracking()


# Related models for One2many relationships
class ForeignBankProcessPFI(models.Model):
    """
    Represents a Proforma Invoice (PFI) submitted to a bank as part of the foreign bank process.
    This model holds details about the PFI number, dates, and the bank it was submitted to.
    """
    _name = 'foreign.bank.process.pfi'
    _description = 'PFI Details for Bank Process'
    _rec_name = 'pfi_number'

    bank_process_id = fields.Many2one('foreign.bank.process', string='Bank Process', ondelete='cascade')
    pfi_number = fields.Char(string='PFI Number', required=True)
    pfi_date = fields.Date(string='PFI Date')
    pfi_date_submit_to_bank = fields.Date(string='PFI date submit. to bank')
    date_sub_to_bank = fields.Date(string='Date Sub TO bank')
    bank = fields.Char(string='Bank')
    bank_req_no = fields.Char(string='Bank req No')
    remark = fields.Text(string='Remark')


class ForeignBankProcessLCTracking(models.Model):
    """
    Tracks the status and details of a Letter of Credit (LC) associated with a foreign bank process.
    It includes information like LC number, dates, amounts, and the banks involved.
    """
    _name = 'foreign.bank.process.lc.tracking'
    _description = 'LC Tracking for Bank Process'
    _rec_name = 'lc_number'

    bank_process_id = fields.Many2one('foreign.bank.process', string='Bank Process', ondelete='cascade')
    lc_number = fields.Char(string='LC Number', required=True)
    lc_date_of_shipment = fields.Date(string='LC Date Of Shipment')
    negotiation_expiry_date = fields.Date(string='Negotiation Expiry Date')
    lc_amount = fields.Monetary(string='LC Amount', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', string='Currency')
    issuing_bank = fields.Char(string='Issuing Bank')
    advising_bank = fields.Char(string='Advising Bank')
    lc_status = fields.Selection([
        ('draft', 'Draft'),
        ('issued', 'Issued'),
        ('advised', 'Advised'),
        ('documents_presented', 'Documents Presented'),
        ('negotiated', 'Negotiated'),
        ('settled', 'Settled'),
    ], string='LC Status', default='draft')
    remarks = fields.Text(string='Remarks')

    lc_issue_date = fields.Date(string='LC Issue Date')
    insurance_before_lc = fields.Boolean(string='Insurance Before LC')
    
class ForeignBankAllocation(models.Model):
    _name = 'foreign.bank.allocation'
    _description = 'Bank Allocation'
    
    bank_process_id = fields.Many2one('foreign.bank.process', string='Bank Process', ondelete='cascade')
    bank_id = fields.Many2one('res.bank', string='Bank', required=True)
    currency_id = fields.Many2one('res.currency', string='Currency', related='bank_process_id.currency_id')
    allocated_amount = fields.Monetary(string='Allocated Amount', currency_field='currency_id')
    currency_value = fields.Float(string='Currency Value (Rate)', digits=(16, 6))
    status = fields.Selection([
        ('pending', 'Pending / Hold'),
        ('allocated', 'Allocated'),
        ('used', 'Used'),
    ], string='Status', default='pending')
    remark = fields.Text(string='Remark')


class ForeignBankProcessContainer(models.Model):
    """
    Manages a list of containers related to a foreign bank process.
    This model stores detailed information for each container, including its number, type, size, weight, status, and transport details.
    """
    _name = 'foreign.bank.process.container'
    _description = 'Container List for Bank Process'
    _rec_name = 'container_number'

    bank_process_id = fields.Many2one('foreign.bank.process', string='Bank Process', ondelete='cascade')
    
    # Container Basic Info
    container_number = fields.Char(string='Container Number', required=True)
    container_size = fields.Selection([
        ('20ft', '20 ft'),
        ('40ft', '40 ft'),
        ('40hc', '40 ft HC'),
        ('45ft', '45 ft'),
    ], string='Container Size')
    container_type = fields.Selection([
        ('dry', 'Dry Container'),
        ('reefer', 'Reefer Container'),
        ('open_top', 'Open Top'),
        ('flat_rack', 'Flat Rack'),
        ('tank', 'Tank Container'),
    ], string='Container Type', default='dry')
    
    # Shipping Details
    vessel_name = fields.Char(string='Vessel Name')
    voyage_number = fields.Char(string='Voyage Number')
    
    # Destination & Discharge
    port_of_loading = fields.Char(string='Port of Loading')
    port_of_discharge = fields.Char(string='Port of Discharge')
    final_destination = fields.Char(string='Final Destination')
    
    # Dates
    stuffing_date = fields.Date(string='Stuffing Date')
    departure_date = fields.Date(string='Departure Date')
    eta_discharge_port = fields.Date(string='ETA Discharge Port')
    ata_discharge_port = fields.Date(string='ATA Discharge Port')
    
    # Container Status
    container_status = fields.Selection([
        ('stuffed', 'Stuffed'),
        ('departed', 'Departed'),
        ('in_transit', 'In Transit'),
        ('arrived_discharge', 'Arrived at Discharge Port'),
        ('customs_clearance', 'Under Customs Clearance'),
        ('delivered', 'Delivered'),
    ], string='Container Status', default='stuffed')
    
    # Weight & Measurements
    gross_weight = fields.Float(string='Gross Weight (KG)')
    net_weight = fields.Float(string='Net Weight (KG)')
    cbm = fields.Float(string='CBM (Cubic Meters)')
    
    # Seal & Security
    seal_number = fields.Char(string='Seal Number')
    
    # Tracking & Documents
    bl_number = fields.Char(string='B/L Number')
    tracking_reference = fields.Char(string='Tracking Reference')
    
    # Additional Info
    remarks = fields.Text(string='Remarks')


class ForeignBankProcessCustomer(models.Model):
    """
    Lists the end customers for whom the goods in the foreign bank process are intended.
    This helps in tracking orders against specific customer contracts and deadlines.
    """
    _name = 'foreign.bank.process.customer'
    _description = 'Customer Details for Bank Process'
    _rec_name = 'customer'

    bank_process_id = fields.Many2one('foreign.bank.process', string='Bank Process', ondelete='cascade')
    customer = fields.Char(string='Customer', required=True)
    contract_no = fields.Char(string='Contract No')
    deadline_date = fields.Date(string='Deadline date')
