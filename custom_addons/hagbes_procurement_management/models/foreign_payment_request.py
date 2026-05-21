from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import timedelta
import logging

_logger = logging.getLogger(__name__)

class ForeignPaymentRequest(models.Model):
    _name = 'foreign.payment.request'
    _description = 'Foreign Payment Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'request_date desc, id desc'
    _rec_name = 'name'
    
# ========== Lc  margin  ==========
    lc_amount = fields.Monetary(
        string="LC Amount",
        compute="_compute_lc_amount",
        store=True,
        currency_field="currency_id",
    )
    lc_margin = fields.Float(string="Request Percentage (%)")
    request_amount = fields.Monetary(
        string="Request Amount",
        compute="_compute_request_amount",
        store=True,
        currency_field="currency_id"
    )
    show_lc_details = fields.Boolean(
        string="Show LC Details",
        compute="_compute_show_lc_details"
    )

    # ========== BASIC INFORMATION ==========
    name = fields.Char(
        string='Request Number',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New')
    )
    
    request_date = fields.Date(
        string='Request Date',
        required=True,
        default=fields.Date.context_today,
        tracking=True
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        required=True, tracking=True)
    branch_id = fields.Many2one('account.analytic.account', 
        string='Branch',
        tracking=True, 
        readonly=True)
    
    required_date = fields.Date(
        string='Required Date',
        required=True,
        tracking=True
    )
    
    # ========== RELATIONS ==========
    purchase_order_id = fields.Many2one(
        'purchase.order',
        string='Purchase Order',
        domain=[('order_type', '=', 'foreign')], # Assuming 'order_type' exists on purchase.order
        required=True,
        tracking=True
    )

    product_line_ids = fields.One2many(
        'foreign.payment.product.line',
        'payment_request_id',
        string='Products Being Purchased',
        compute='_compute_product_lines',
        store=True
    )

    supplier_id = fields.Many2one(
        'res.partner',
        string='Supplier',
        compute='_compute_supplier_from_po',
        store=True,
        readonly=True,
        tracking=True
    )
    
    # ========== CURRENCY & AMOUNT ==========
    company_currency_id = fields.Many2one(
        'res.currency',
        string='Company Currency',
        related='company_id.currency_id',
        default=lambda self: self.env.company.currency_id,
        readonly=True
    )
    
    total_amount = fields.Monetary(
        string='Total Amount (Company Currency)',
        currency_field='company_currency_id',
        compute='_compute_total_amount',
        store=True,
        help="Total converted to company's default currency"
    )
    


    # ========== APPROVAL FIELDS ==========
    approval_request_id = fields.Many2one('approval.request', string="Approval Request", readonly=True)
    step_progress = fields.Html(string="Approval Progress", compute='_compute_step_progress')
    status_info = fields.Char(string='Approval Status Info', compute='_compute_status_info')
    
    # ========== STATE & WORKFLOW ==========
    state = fields.Selection([
        ('draft', 'Draft'),
        ('waiting_for_procurement_manager', 'Waiting for Procurement Manager'),
        ('waiting_for_finance_manager', 'Waiting for Finance Manager'),
        ('approved', 'Approved'),
        ('paid', 'Paid'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True, required=True)
    
    requested_by = fields.Many2one(
        'res.users',
        string='Requested By',
        default=lambda self: self.env.user,
        readonly=True
    )
    
    approved_by = fields.Many2one(
        'res.users',
        string='Approved By',
        readonly=True
    )
    
    approved_date = fields.Datetime(
        string='Approved Date',
        readonly=True
    )
    
    # ========== ADDITIONAL FIELDS ==========
    notes = fields.Text(string='Notes')
    rejection_reason = fields.Text(string='Rejection Reason')
    
    payment_line_ids = fields.One2many(
        'foreign.payment.request.line',
        'payment_request_id',
        string='Payment Lines'
    )
    
    bank_process_ids = fields.One2many(
        'foreign.bank.process',
        'payment_request_id',
        string='Bank Processes'
    )
    
    lc_id = fields.Many2one(
        'foreign.lc', # Assuming 'foreign.lc' model exists for Letter of Credit
        string='Letter of Credit',
        tracking=True
    )
    
    days_pending = fields.Integer(
        string='Days Pending',
        compute='_compute_days_pending'
    )
    
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True
    )
    related_request_ids = fields.Many2many(
        'foreign.payment.request',
        compute='_compute_related_requests',
        string='Previous Requests'
    )

    journal_id = fields.Many2one(
        'account.journal',
        string='Payment Journal',
        domain="[('company_id', '=', company_id)]",
        tracking=True
    )
    journal_visible = fields.Boolean(compute='_compute_journal_visible')

    previous_payment_line_ids = fields.One2many(
        'foreign.payment.request.line',
        compute='_compute_previous_payment_lines',
        string='Previous Payment Lines'
    )

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

    # ========== COMPUTE METHODS ==========
    @api.depends('approval_request_id')
    def _compute_step_progress(self):
        for rec in self:
            rec.step_progress = rec.approval_request_id.step_progress if rec.approval_request_id else "<span>No approval yet</span>"

    @api.depends('state')
    def _compute_status_info(self):
        for rec in self:
            stages = ['Draft', 'Submitted', 'Pending Approval', 'Approved', 'Paid']
            pos = {
                'draft': 0,
                'submitted': 1,
                'pending': 2,
                'approved': 3,
                'paid': 4,
            }.get(rec.state, 0)
            rec.status_info = ' → '.join([f"[{s}]" if i == pos else s for i, s in enumerate(stages)])

    @api.depends('payment_line_ids.amount', 'payment_line_ids.currency_id')
    def _compute_total_amount(self):
        """Convert all payment lines to company currency and sum them up."""
        for record in self:
            total = 0.0
            company_currency = record.company_currency_id
            for line in record.payment_line_ids:
                line_currency = line.currency_id
                amount = line.amount
                if line_currency and company_currency and line_currency != company_currency:
                    amount = line_currency._convert(
                        amount,
                        company_currency,
                        record.company_id,
                        fields.Date.today()
                    )
                total += amount
            record.total_amount = total

    @api.depends('request_date', 'state')
    def _compute_days_pending(self):
        today = fields.Date.context_today(self)
        for record in self:
            if record.state in ['paid', 'cancelled', 'rejected']:
                record.days_pending = 0
            else:
                record.days_pending = (today - record.request_date).days if record.request_date else 0

    @api.depends('purchase_order_id')
    def _compute_supplier_from_po(self):
        for record in self:
            record.supplier_id = record.purchase_order_id.partner_id if record.purchase_order_id else False

    @api.depends('state')
    def _compute_journal_visible(self):
        for rec in self:
            rec.journal_visible = rec.state in ['waiting_for_finance_manager', 'approved', 'paid']

    @api.depends('purchase_order_id')
    def _compute_related_requests(self):
        for rec in self:
            if rec.purchase_order_id:
                related = self.env['foreign.payment.request'].search([
                    ('purchase_order_id', '=', rec.purchase_order_id.id),
                    ('id', '!=', rec.id)
                ])
                rec.related_request_ids = related
            else:
                rec.related_request_ids = False

    @api.depends('purchase_order_id')
    def _compute_previous_payment_lines(self):
        for record in self:
            if record.purchase_order_id:
                related_requests = self.env['foreign.payment.request'].search([
                    ('purchase_order_id', '=', record.purchase_order_id.id),
                    ('id', '!=', record.id)
                ])
                all_lines = related_requests.mapped('payment_line_ids')
                record.previous_payment_line_ids = all_lines
            else:
                record.previous_payment_line_ids = False

    @api.depends('purchase_order_id.order_line')
    def _compute_product_lines(self):
        for record in self:
            record.product_line_ids = False # Clear existing lines first
            if record.purchase_order_id and record.purchase_order_id.order_line:
                lines = []
                for line in record.purchase_order_id.order_line:
                    lines.append((0, 0, {
                        'product_id': line.product_id.id,
                        'quantity': line.product_qty,
                        'uom_id': line.product_uom.id,
                        'unit_price': line.price_unit,
                        'currency_id': line.currency_id.id,
                        'description': line.name,
                    }))
                record.product_line_ids = lines

    @api.depends('payment_line_ids.payment_method', 'payment_line_ids.amount')
    def _compute_lc_amount(self):
        for rec in self:
            lc_lines = rec.payment_line_ids.filtered(lambda l: l.payment_method == 'lc')
            rec.lc_amount = sum(lc_lines.mapped('amount'))

    @api.depends('lc_amount', 'lc_margin')
    def _compute_request_amount(self):
        for rec in self:
            if rec.lc_margin:
                rec.request_amount = rec.lc_amount * rec.lc_margin / 100
            else:
                rec.request_amount = 0.0

    @api.depends('payment_line_ids.payment_method')
    def _compute_show_lc_details(self):
        for rec in self:
            rec.show_lc_details = any(line.payment_method == 'lc' for line in rec.payment_line_ids)
    @api.depends('payment_line_ids.payment_method', 'payment_line_ids.amount', 'payment_line_ids.payment_type')
    def _compute_is_current_user_approver(self):
        for rec in self:
            if rec.approver_ids and self.env.user in rec.approver_ids:
                rec.is_current_user_approver = True
            else:
                rec.is_current_user_approver = False
    def _compute_lc_amount(self):
        for rec in self:
         lc_lines = rec.payment_line_ids.filtered(lambda l: l.payment_method == 'lc' and l.payment_type == 'supplier')
        rec.lc_amount = sum(lc_lines.mapped('amount'))

    # ========== ACTION METHODS ==========
    def action_submit(self):
        self.ensure_one()
        if not self.payment_line_ids:
            raise UserError(_('Please add at least one payment line.'))

        flow = self.env['approval.flow'].search([
            ('request_model_id.model', '=', 'foreign.payment.request'),
            ('active', '=', True),
            ('company_id', '=', self.company_id.id)
        ], limit=1)

        if not flow:
            raise UserError(_("No approval flow configured for Foreign Payment Request."))

        first_step = self.env['approval.step'].search([
            ('flow_id', '=', flow.id)
        ], order='sequence asc', limit=1)

        if not first_step:
            raise UserError(_("No steps defined in the approval flow for this flow."))

        branch_id_val = self.branch_id.id if self.branch_id else False
        approval_req = self.env['approval.request'].create({
            'flow_id': flow.id,
            'res_model': self._name,
            'res_id': self.id,
            'module_name': 'hagbes_procurement_management',
            'current_step_id': first_step.id,
            'branch_id': branch_id_val, 
            'status': 'pending',
        })

        self.write({
            'approval_request_id': approval_req.id,
            'state': 'waiting_for_procurement_manager' # Explicitly set the first state
        })

        self.message_post(body=_("Submitted for approval."))
        # These calls will then sync to the correct subsequent state
        approval_req.process_action()
        self._sync_state_from_approval()

    @api.model
    def _get_approval_state_mapping(self):
        """
        Provides a mapping from the approval step's NAME to this model's state.
        """
        return {
            'submit': 'waiting_for_procurement_manager',
            'procurement approval': 'waiting_for_procurement_manager',
            'procurement manager approval': 'waiting_for_procurement_manager',
            'finance approval': 'waiting_for_finance_manager',
            'finance manager approval': 'waiting_for_finance_manager',
            '__approved__': 'approved',
            '__rejected__': 'rejected',
        }

    def action_procurement_manager_approve(self, comment=''):
        self.action_approve(comment)

    def action_finance_manager_approve(self, comment=''):
        self.action_approve(comment)

    def action_approve(self, comment=''):
        self.ensure_one()
        if not self.approval_request_id:
            raise UserError(_("No approval request linked to this payment request."))
        
        ctx = dict(self.env.context)
        ctx.update({
            'action_type': 'approve',
            'comment': comment,
        })
        
        result = self.approval_request_id.with_context(ctx).process_action()
        self._sync_state_from_approval()
        return result 
        
    def action_reject(self, comment=''):
        self.ensure_one()
        if not self.approval_request_id:
            raise UserError(_("No approval request linked to this payment request."))
        
        ctx = dict(self.env.context)
        ctx.update({
            'action_type': 'reject',
            'comment': comment,
        })
        
        result = self.approval_request_id.with_context(ctx).process_action()
        self._sync_state_from_approval()
        return result

    def _sync_state_from_approval(self):
        """Syncs the state of this record from its approval request."""
        for rec in self:
            if not rec.approval_request_id:
                continue

            approval_req = rec.approval_request_id
            new_state = None
            mapping = rec._get_approval_state_mapping()

            if approval_req.status == 'approved':
                new_state = mapping.get('__approved__')
                if rec.state != 'approved':
                    rec.approved_by = self.env.user
                    rec.approved_date = fields.Datetime.now()
                    rec.message_post(body=_("Payment request approved."))
                    
            elif approval_req.status == 'rejected':
                new_state = mapping.get('__rejected__')
            elif approval_req.current_step_id:
                step_name = (approval_req.current_step_id.name or '').strip()
                normalized_step_name = step_name.lower()
                new_state = mapping.get(normalized_step_name) or mapping.get(step_name)

                # Fallback to keyword-based mapping so state sync is resilient to label variations.
                if not new_state:
                    if 'finance' in normalized_step_name:
                        new_state = 'waiting_for_finance_manager'
                    elif 'procurement' in normalized_step_name:
                        new_state = 'waiting_for_procurement_manager'

            if new_state and rec.state != new_state:
                rec.state = new_state

    def action_mark_as_paid(self):
        self.ensure_one()
        if self.state != 'approved':
            raise UserError(_("Only approved payment requests can be marked as paid."))
        self.state = 'paid'
        self.message_post(body=_('Payment completed.'))
        self._create_account_move()
        # self._create_bank_process()
        self._create_lc_if_needed()

    def action_set_to_draft(self):
        self.ensure_one()
        if self.state not in ['waiting_for_procurement_manager', 'waiting_for_finance_manager', 'rejected', 'cancelled']:
            raise UserError(_("Payment request can only be reset to Draft from Submitted, Pending, Rejected, or Cancelled states."))
            
        self.state = 'draft'
        self.approved_by = False
        self.approved_date = False
        self.rejection_reason = False
        if self.approval_request_id:
            self.approval_request_id.unlink()
            self.approval_request_id = False
        self.message_post(body=_('Payment request reset to Draft.'))

    def action_cancel(self):
        self.ensure_one()
        if self.state in ['approved', 'paid']:
            raise UserError(_("Approved or Paid requests cannot be cancelled directly. Please contact administrator."))
        self.state = 'cancelled'
        self.message_post(body=_('Payment request cancelled.'))
        if self.approval_request_id:
            self.approval_request_id.unlink() 
            self.approval_request_id = False

    # ========== BUSINESS METHODS ==========
    def _create_bank_process(self):
        self.ensure_one()
        payment_method = self.payment_line_ids[0].payment_method if self.payment_line_ids else False

        if not payment_method:
            _logger.warning("No payment method found on payment lines for %s. Bank Process not created.", self.name)
            return False

        self.env['foreign.bank.process'].create({
            'name': f"BP/{self.name}",
            'payment_request_id': self.id,
            'purchase_order_id': self.purchase_order_id.id,
            'supplier_id': self.supplier_id.id,
            'currency_id': self.company_currency_id.id,
            'amount': self.total_amount,
            'payment_method': payment_method,
            'state': 'waiting_currency',
        })
        self.message_post(body=_('Bank Process created for this payment request.'))


    def _create_account_move(self):
        for rec in self:
            if not rec.journal_id:
                raise UserError(_("Please select a Payment Journal to create the accounting entry."))
            
            if not rec.supplier_id.property_account_payable_id:
                raise UserError(_("The supplier '%s' does not have a default payable account configured. Please set one.") % rec.supplier_id.display_name)
            
            if not rec.journal_id.default_account_id:
                raise UserError(_("The payment journal '%s' does not have a default account configured. Please set one.") % rec.journal_id.display_name)

            move_lines = []
            
            move_lines.append((0, 0, {
                'account_id': rec.journal_id.default_account_id.id, 
                'partner_id': rec.supplier_id.id,
                'debit': 0.0,
                'credit': rec.total_amount,
                'name': _('Payment for %s') % rec.name,
            }))
            
            move_lines.append((0, 0, {
                'account_id': rec.supplier_id.property_account_payable_id.id,
                'partner_id': rec.supplier_id.id,
                'debit': rec.total_amount,
                'credit': 0.0,
                'name': _('Payment Request %s to %s') % (rec.name, rec.supplier_id.display_name),
            }))

            move_vals = {
                'journal_id': rec.journal_id.id,
                'ref': rec.name,
                'date': fields.Date.context_today(self),
                'line_ids': move_lines,
                'move_type': 'entry',
                'company_id': rec.company_id.id,
            }
            try:
                move = self.env['account.move'].create(move_vals)
                move.action_post()
                self.message_post(body=_('Accounting entry %s created and posted.') % move.name)
            except Exception as e:
                _logger.error("Error creating or posting accounting move for %s: %s", rec.name, str(e))
                raise UserError(_("Failed to create or post accounting entry: %s") % str(e))

    def _create_lc_if_needed(self):
        self.ensure_one()
        
        lc_lines = self.payment_line_ids.filtered(lambda l: l.payment_method == 'lc' and l.payment_type == 'supplier')
        if not lc_lines:
            return False
        
        issuing_bank = self.journal_id.bank_id
        if not issuing_bank and self.company_id.partner_id.bank_ids:
            issuing_bank = self.company_id.partner_id.bank_ids[0]
        
        if not issuing_bank:
            raise UserError(_("No issuing bank configured. Please set a bank on the selected Payment Journal or on your Company's partner record."))
        
        lc_amount = sum(lc_lines.mapped('amount'))
        
        lc_currency = lc_lines[0].currency_id if lc_lines else self.currency_id

        lc_vals = {
            'purchase_order_id': self.purchase_order_id.id,
            'supplier_id': self.supplier_id.id,
            'lc_type': 'sight',
            'currency_id': lc_currency.id,
            'lc_amount': lc_amount,
            'lc_date': fields.Date.context_today(self),
            'expiry_date': fields.Date.context_today(self) + timedelta(days=90),
            'issuing_bank_id': issuing_bank.id,
            'payment_terms': 'Payment against documents',
            'state': 'draft',
            'notes': _('Automatically created from Payment Request %s') % self.name,
        }
        
        try:
            lc = self.env['foreign.lc'].create(lc_vals)
            self.lc_id = lc.id
            self.message_post(body=_("Draft Letter of Credit %s created") % lc.name)
            
            self._add_products_to_lc(lc) 
            
            return lc
        except Exception as e:
            _logger.error("Error creating Letter of Credit for %s: %s", self.name, str(e))
            raise UserError(_("Failed to create Letter of Credit: %s") % str(e))

    def _add_products_to_lc(self, lc):
        if 'product_line_ids' not in self.env['foreign.lc']._fields:
            _logger.warning("The 'foreign.lc' model does not have a 'product_line_ids' field. Products from Payment Request %s cannot be added to LC %s.", self.name, lc.name)
            return

        for product_line in self.product_line_ids:
            lc.write({
                'product_line_ids': [(0, 0, {
                    'product_id': product_line.product_id.id,
                    'quantity': product_line.quantity,
                    'uom_id': product_line.uom_id.id,
                    'unit_price': product_line.unit_price,
                    'currency_id': product_line.currency_id.id,
                    'description': product_line.description,
                })]
            })

    @api.model
    def create(self, vals):
        if vals.get('purchase_order_id') and not vals.get('branch_id'):
            po = self.env['purchase.order'].browse(vals['purchase_order_id'])
            if po.branch_id:
                vals['branch_id'] = po.branch_id.id

        if vals.get('name', _('New')) == _('New'):
            branch_identifier = '00'
            if vals.get('branch_id'):
                branch = self.env['account.analytic.account'].browse(vals['branch_id'])
                if hasattr(branch, 'code') and branch.code:
                    branch_identifier = branch.code.strip()[-2:].zfill(2)
                else:
                    branch_identifier = str(branch.id).zfill(2)[-2:]

            year_suffix = fields.Date.today().strftime('%y')
            seq_number = self.env['ir.sequence'].next_by_code('foreign.payment.request.new_sequence_code') or '00001'
            vals['name'] = f'FPR{branch_identifier}{year_suffix}{seq_number}'
        return super(ForeignPaymentRequest, self).create(vals)

    @api.constrains('state', 'journal_id')
    def _check_journal_required(self):
        for rec in self:
            if rec.state == 'paid' and not rec.journal_id:
                raise ValidationError(_("You must select a Payment Journal before marking the request as paid."))


class ForeignPaymentRequestLine(models.Model):
    _name = 'foreign.payment.request.line'
    _description = 'Foreign Payment Request Line'
    _order = 'sequence, id'

    # ========== BASIC FIELDS ==========
    sequence = fields.Integer(string='Sequence', default=10)
    payment_request_id = fields.Many2one(
        'foreign.payment.request',
        string='Payment Request',
        required=True,
        ondelete='cascade'
    )
    
    # ========== PAYMENT DETAILS ==========
    payment_type = fields.Selection([
        ('supplier', 'Supplier Payment'),
        ('freight', 'Freight'),
        ('insurance', 'Insurance'),
        ('customs', 'Customs & Duties'),
        ('bank_charge', 'Bank Charge'),
        ('other', 'Other'),
    ], string='Payment Type', required=True)

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
    ], string="Payment Method", required=True)
      
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        required=True,
        default=lambda self: self.env.company.currency_id
    )
    
    amount = fields.Monetary(
        string='Amount',
        currency_field='currency_id',
        required=True
    )

    # ========== ADDITIONAL INFO ==========
    description = fields.Text(string='Description', required=True)
    beneficiary = fields.Char(string='Beneficiary')
    due_date = fields.Date(string='Due Date')
    reference = fields.Char(string='Reference')
    notes = fields.Text(string='Notes')

    # ========== ONCHANGE METHOD TO AUTOMATICALLY SET LC AMOUNT ==========


    # ========== VALIDATION ==========
    @api.constrains('amount')
    def _check_amount(self):
        for record in self:
            if record.amount <= 0:
                raise ValidationError(_('Amount must be greater than zero.'))

    @api.constrains('payment_method', 'currency_id')
    def _check_line_fields(self):
        for record in self:
            if not record.payment_method:
                raise ValidationError(_('Payment Method is required.'))
            if not record.currency_id:
                raise ValidationError(_('Currency is required.'))

class ForeignPaymentProductLine(models.Model):
    _name = 'foreign.payment.product.line'
    _description = 'Foreign Payment Product Line'
    _order = 'sequence, id'

    payment_request_id = fields.Many2one(
        'foreign.payment.request',
        string='Payment Request',
        required=True,
        ondelete='cascade'
    )
    product_id = fields.Many2one(
        'product.product',
        string='Product',
        required=True
    )
    quantity = fields.Float(
        string='Quantity',
        digits='Product Unit of Measure',
        required=True
    )
    uom_id = fields.Many2one(
        'uom.uom',
        string='Unit of Measure',
        required=True
    )
    unit_price = fields.Monetary(
        string='Unit Price',
        currency_field='currency_id',
        required=True
    )
    total_price = fields.Monetary(
        string='Total Price',
        currency_field='currency_id',
        compute='_compute_total_price',
        store=True
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        required=True
    )
    description = fields.Text(string='Description')
    sequence = fields.Integer(string='Sequence', default=10)
    
    @api.depends('quantity', 'unit_price')
    def _compute_total_price(self):
        for line in self:
            line.total_price = line.quantity * line.unit_price
