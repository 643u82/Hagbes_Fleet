from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging
from datetime import datetime, timedelta
_logger = logging.getLogger(__name__)

class PurchaseRequest(models.Model):
    _name = 'purchase.request'
    _description = 'Purchase Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc, id desc'
    _rec_name = 'name'

    # Basic Information
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
        tracking=True,
        readonly=True
    )
    requested_by = fields.Many2one(
        'res.users',
        string='Requested By',
        required=True,
        default=lambda self: self.env.user,
        tracking=True,
        readonly=True
    )
    department_id = fields.Many2one(
        'hr.department',
        string='Department',
        compute='_compute_department_and_branch',
        store=True,
        readonly=True,
        tracking=True
    )
    branch_id = fields.Many2one(
        'account.analytic.account',
        string='Branch',
        domain="[('plan_id.name', '=', 'Branch'), ('company_id', '=', company_id)]",
        required=False,
        compute='_compute_department_and_branch',
        store=True,
        readonly=True
    )

    state = fields.Selection([
        ('draft', 'Draft'),
        ('rfq_sent', 'RFQ Sent'),
        ('pfi_received', 'PFI Received'),
        ('waiting_for_dept_manager', 'Waiting for Department Manager'),
        ('waiting_for_gm', 'Waiting for General Manager'),
        ('waiting_for_director', 'Waiting for Director'),
        ('waiting_for_procurement_manager', 'Waiting for Procurement Manager'),
        ('pending', 'Pending Approval'), # Generic pending state
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
        ('converted_to_rfq', 'RFQ Created'),
        ('in_bank_process', 'In Bank Process'),
        ('converted_to_po', 'Converted to PO'),
    ], string='Status', default='draft', tracking=True, required=True)

    can_reject = fields.Boolean(
        string='Can Reject',
        compute='_compute_button_visibility',
        store=False
    )
    
    can_approve = fields.Boolean(
        string='Can Approve', 
        compute='_compute_button_visibility',
        search='_search_can_approve',   
        store=False
    )
    
    is_current_approver = fields.Boolean(
        string='Is Current Approver',
        compute='_compute_button_visibility',
        store=False
    )

    approval_request_id = fields.Many2one(
        'approval.request',
        string="Approval Request",
        readonly=True
    )
    
    current_step_name = fields.Char(
        string='Current Step Name', 
        compute='_compute_current_step_info',
        store=False
    )
    
    current_approver_name = fields.Char(
        string='Current Approver',
        compute='_compute_current_step_info',
        store=False
    )

    step_progress = fields.Html(
        string="Approval Progress",
        compute='_compute_step_progress',
        store=False
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



    # Request Details
    request_type = fields.Selection([
        ('local', 'Local Purchase'),
        ('foreign', 'Foreign Purchase'),
    ], string='Request Type', required=True, default='foreign', tracking=True, readonly=True)

    vendor_id = fields.Many2one(
        'res.partner',
        string='Vendor',
        required=True,
        domain="[('supplier_rank','>',0)]"
    )
    vendor_ref = fields.Char(string='Vendor Reference')
    priority = fields.Selection([
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ], string='Priority', default='medium', tracking=True)
    justification = fields.Text(string='Justification', required=True)

    pfi_attachment = fields.Binary(string='PFI Attachment', attachment=True)
    pfi_attachment_name = fields.Char(string='PFI Attachment Name')

    # Budget Information
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        required=True,
        default=lambda self: self.env.company.currency_id
    )

    # Request Lines
    request_line_ids = fields.One2many(
        'purchase.request.line',
        'request_id',
        string='Request Lines'
    )

    # Related Records
    rfq_ids = fields.One2many('purchase.order', 'purchase_request_id', string='RFQs')
    po_ids = fields.One2many('purchase.order', 'purchase_request_id', string='Purchase Orders')
    bank_process_ids = fields.One2many('foreign.bank.process', 'purchase_request_id', string='Bank Processes')
    rfq_count = fields.Integer(compute='_compute_related_counts', string='RFQ Count')
    po_count = fields.Integer(compute='_compute_related_counts', string='PO Count')

    # Delivery Information
    required_date = fields.Date(string='Required Date', tracking=True)
    delivery_address = fields.Text(string='Delivery Address')

    picking_type_id = fields.Many2one(
        'stock.picking.type',
        string='Deliver To',
        required=True,
        domain="[('code', '=', 'incoming'), ('warehouse_id.branch_id', '=', branch_id)]",
        help="Warehouse operation type for delivery (e.g. Receipts)"
    )

    # Foreign Procurement Details
    incoterm_id = fields.Many2one('account.incoterms', string='Incoterm', tracking=True)
    insurance = fields.Char(string='Insurance', tracking=True)
    major_conditions = fields.Text(string='Major Conditions')
    delivery_date = fields.Date(string='Delivery Date', tracking=True)
    validity_period = fields.Char(string='Validity', tracking=True)
    origin_id = fields.Many2one('res.country', string='Origin', tracking=True)

    # Additional Information
    notes = fields.Text(string='Additional Notes')
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True
    )

    amount_total = fields.Float(
        string='Total Amount',
        compute='_compute_amount_total',
        store=True,
        help='Total estimated amount for approval workflow conditions'
    )

    overall_status = fields.Char(
        string='Overall Status',
        compute='_compute_overall_status',
        store=False,
        help="Shows the current stage of the request in the entire procurement lifecycle."
    )

    @api.depends('state', 'po_ids.state', 'po_ids.costing_state', 'po_ids.transit_state', 'po_ids.bank_process_state')
    def _compute_overall_status(self):
        for request in self:
            # Default to the request's own state
            request.overall_status = dict(request._fields['state'].selection).get(request.state)

            if request.state in ['converted_to_po', 'converted_to_rfq', 'approved']:
                # Find the most relevant active PO (ignoring cancelled ones)
                active_pos = request.po_ids.filtered(lambda po: po.state != 'cancel')
                if not active_pos:
                    continue

                # Take the most recent active PO
                po = active_pos[0]

                # Determine status based on the most advanced downstream process, ignoring draft/initial states.
                # Precedence: Costing -> Transit -> Bank -> PO/RFQ
                if po.costing_state and po.costing_state not in ['Draft', 'Cancelled', 'Rejected']:
                    request.overall_status = f"Costing: {po.costing_state}"
                elif po.transit_state and po.transit_state not in ['Draft', 'Cancelled']:
                    request.overall_status = f"Transit: {po.transit_state}"
                elif po.bank_process_state and po.bank_process_state not in ['Order Information', 'Cancelled']:
                    request.overall_status = f"Bank: {po.bank_process_state}"
                elif po.state not in ['draft', 'sent']:
                    po_state_label = dict(po._fields['state'].selection).get(po.state)
                    request.overall_status = f"PO: {po_state_label}"
                elif po.state in ['draft', 'sent']:
                    # If it's a draft or sent PO, it's considered an RFQ
                    po_state_label = dict(po._fields['state'].selection).get(po.state)
                    request.overall_status = f"RFQ: {po_state_label}"

            elif request.state == 'in_bank_process' and request.bank_process_ids:
                bank_process = request.bank_process_ids[0]
                state_label = dict(bank_process._fields['state'].selection).get(bank_process.state)
                request.overall_status = f"Bank: {state_label}"

    # Removed _check_pfi_attachment constrain to allow printing RFQ without PFI

   
    @api.model
    def create(self, vals_list):
        """Generate sequence when creating a purchase request."""
        if not isinstance(vals_list, list):
            vals_list = [vals_list]
    
        for vals in vals_list:
            # Default name check
            if vals.get('name', _('New')) == _('New'):
                user_id = vals.get('requested_by') or self.env.uid
                company_id = vals.get('company_id', self.env.company.id)
    
                # Try to find the employee to determine branch & dept if they are not already set
                if not vals.get('branch_id') or not vals.get('department_id'):
                    employee = self.env['hr.employee'].search([
                        ('user_id', '=', user_id),
                        ('company_id', '=', company_id)
                    ], limit=1)
    
                    # Derive branch if missing
                    if not vals.get('branch_id'):
                        if employee and employee.job_id and employee.job_id.analytic_account_id:
                            vals['branch_id'] = employee.job_id.analytic_account_id.id
    
                    # Derive department if missing
                    if not vals.get('department_id') and employee and employee.department_id:
                        vals['department_id'] = employee.department_id.id
                
                # Now generate sequence safely
                branch_id = vals.get('branch_id')
                branch_code = '00'
                if branch_id:
                    branch = self.env['account.analytic.account'].browse(branch_id)
                    branch_code = branch.code or '00'
    
                year = datetime.now().year
                seq = self.env['ir.sequence'].next_by_code('purchase.request') or '00000'
                vals['name'] = f"PR{branch_code}{year}{seq.zfill(5)}"
    
        return super().create(vals_list)

    @api.depends('rfq_ids', 'po_ids')
    def _compute_related_counts(self):
        for request in self:
            request.rfq_count = len(request.rfq_ids)
            request.po_count = len(request.po_ids)

    @api.depends('requested_by')
    def _compute_department_and_branch(self):
        """Compute department and branch based on the requesting user's employee job position"""
        for rec in self:
            if (rec.requested_by):
                employee = self.env['hr.employee'].search([
                    ('user_id', '=', rec.requested_by.id),
                    ('company_id', '=', rec.company_id.id)
                ], limit=1)
                if employee:
                    rec.department_id = employee.department_id.id if employee.department_id else False
                    if employee.job_id and employee.job_id.analytic_account_id:
                        rec.branch_id = employee.job_id.analytic_account_id.id
                    else:
                        rec.branch_id = False
                else:
                    rec.department_id = False
                    rec.branch_id = False
            else:
                rec.department_id = False
                rec.branch_id = False

    @api.onchange('requested_by')
    def _onchange_requested_by(self):
        """Update department and branch when requested_by changes"""
        if self.requested_by:
            employee = self.env['hr.employee'].search([
                ('user_id', '=', self.requested_by.id),
                ('company_id', '=', self.company_id.id)
            ], limit=1)
            if employee:
                if employee.department_id:
                    self.department_id = employee.department_id.id
                if employee.job_id and employee.job_id.analytic_account_id:
                    self.branch_id = employee.job_id.analytic_account_id.id

    @api.depends('state', 'approver_ids')
    def _compute_is_current_user_approver(self):
        for rec in self:
            rec.is_current_user_approver = self.env.user in (rec.approver_ids or self.env['res.users'])


    @api.depends('state', 'approval_request_id.approver_ids')
    def _compute_button_visibility(self):
        """Compute button visibility based on central approval system"""
        for rec in self:
            rec.can_reject = False
            rec.can_approve = False
            rec.is_current_approver = False
            
            current_user = self.env.user
            is_approver = current_user in (rec.approval_request_id.approver_ids or self.env['res.users'])

            if is_approver and rec.state in ['waiting_for_dept_manager', 'waiting_for_gm', 'waiting_for_director', 'waiting_for_procurement_manager', 'pending']:
                rec.can_approve = True
                rec.can_reject = True
                rec.is_current_approver = True

    def _search_can_approve(self, operator, value):
        """Search method for can_approve field"""
        if operator not in ('=', '!=') or not isinstance(value, bool):
            return []

        current_user = self.env.user
        # Find approval requests where the current user is an approver
        approval_requests = self.env['approval.request'].search([
            ('approver_ids', 'in', current_user.id),
            ('res_model', '=', self._name),
            ('status', '=', 'pending')
        ])

        request_ids = approval_requests.mapped('res_id')

        if (operator == '=' and value) or (operator == '!=' and not value):
            return [('id', 'in', request_ids)]
        else:
            return [('id', 'not in', request_ids)]

    @api.model
    def _get_approval_state_mapping(self):
        """
        Provides a mapping from the approval step's NAME to this model's state.
        This is the single source of truth for state synchronization.
        """
        return {
            'Manager Purchase Approval': 'waiting_for_dept_manager',
            'General Purchase Manager': 'waiting_for_gm',
            'Director Purchase Approval': 'waiting_for_director',
            'Procurement Purchase Officer': 'waiting_for_procurement_manager',
            '__approved__': 'approved',
            '__rejected__': 'rejected',
        }

    @api.depends('approval_request_id', 'approval_request_id.current_step_id')
    def _compute_current_step_info(self):
        """Get current step information from central approval system"""
        for rec in self:
            rec.current_step_name = ''
            rec.current_approver_name = ''
            
            if rec.approval_request_id and rec.approval_request_id.current_step_id:
                current_step = rec.approval_request_id.current_step_id
                rec.current_step_name = current_step.name
                rec.current_approver_name = ', '.join(rec.approval_request_id.approver_ids.mapped('name'))

    @api.depends('approval_request_id')
    def _compute_step_progress(self):
        """Get approval progress from central approval system"""
        for rec in self:
            if rec.approval_request_id:
                rec.step_progress = rec.approval_request_id.step_progress or "<span>No progress available.</span>"
            else:
                rec.step_progress = "<span>Not submitted for approval yet.</span>"

    @api.depends('request_line_ids.estimated_total')
    def _compute_amount_total(self):
        """Compute total estimated amount"""
        for rec in self:
            rec.amount_total = sum(line.estimated_total for line in self.request_line_ids)

    def action_submit(self):
        """Submit for centralized approval"""
        self.ensure_one()
        if not self.request_line_ids:
            raise UserError(_('Please add at least one request line before submitting.'))

        # Check PFI before submitting
        if self.request_type == 'foreign' and getattr(self, 'state', '') != 'pfi_received':
            if not getattr(self, 'pfi_attachment', False):
                raise UserError(_('Please attach the Proforma Invoice (PFI) and click "PFI Received" before submitting the Foreign Purchase Request.'))

         
        flow = self.env['approval.flow'].search([
            ('request_model_id.model', '=', 'purchase.request'),
            ('active', '=', True),
            ('company_id', '=', self.company_id.id)
        ], limit=1)

        if not flow:
            raise UserError(_("No approval flow defined for Purchase Requests!"))

        first_step = self.env['approval.step'].search([
            ('flow_id', '=', flow.id)
        ], order='sequence asc', limit=1)

        if not first_step:
            raise UserError(_("No steps defined for this approval flow."))

        
        approval_req = self.env['approval.request'].create({
            'flow_id': flow.id,
            'res_model': self._name,
            'module_name': 'hagbes_procurement_management',
            'res_id': self.id,
            'current_step_id': first_step.id,
            'branch_id': self.branch_id.id if self.branch_id else False,
            'status': 'pending',
        })

        self.write({
           # 'state': 'pending', # A generic state while the first step is processed
            'approval_request_id': approval_req.id
        })
        
         
        approval_req.process_action()
        self._sync_state_from_approval()
        
        self.message_post(body=_('Purchase request submitted for approval.'))

    def _sync_state_from_approval(self):
        """Sync state from centralized approval system"""
        if not self.approval_request_id:
            _logger.warning("Record %s has no approval_request_id. Skipping sync.", self.name)
            return

        approval_req = self.approval_request_id
        new_state = None
        mapping = self._get_approval_state_mapping()

        if approval_req.status == 'approved':
            new_state = mapping.get('__approved__')
        elif approval_req.status == 'rejected':
            new_state = mapping.get('__rejected__')
        elif approval_req.current_step_id:
            step_name = (approval_req.current_step_id.name or '').strip()
            new_state = mapping.get(step_name)

        final_state = new_state if new_state else 'pending'
        if self.state != final_state:
            _logger.info(f"Changing Purchase Request '{self.name}' state from '{self.state}' to '{final_state}'.")
            self.state = final_state

    def action_print_rfq(self):
        """Print RFQ / Change state to RFQ Sent"""
        self.ensure_one()
        self.state = 'rfq_sent'
        self.message_post(body=_('RFQ Sent/Printed.'))
        # Odoo's standard PO print action, we will create a custom one if missing
        report = self.env.ref('hagbes_procurement_management.action_report_purchase_request', raise_if_not_found=False)
        if report:
            return report.report_action(self)
        return True

    def action_pfi_received(self):
        self.ensure_one()
        if not self.pfi_attachment:
            raise UserError(_("Please attach the PFI document before confirming PFI received."))
        self.state = 'pfi_received'
        self.message_post(body=_('PFI Received.'))

    def action_approve(self, comment=''):
        """Triggers the 'approve' action in the central approval system."""
        self.ensure_one()
        if not self.is_current_user_approver:
            raise UserError(_("You are not the current approver for this request or the action has already been processed."))

        if not self.approval_request_id:
            raise UserError(_("No approval request linked to this record."))
        self.approval_request_id.with_context(action_type='approve', comment=comment).process_action()
        self._sync_state_from_approval()
        self.message_post(body=_('Approved by %s.') % self.env.user.name)

    def action_reject(self, comment=''):
        """Triggers the 'reject' action in the central approval system."""
        self.ensure_one()
        if not self.approval_request_id:
            raise UserError(_("No approval request linked to this record."))
        self.approval_request_id.with_context(action_type='reject', comment=comment).process_action()
        self._sync_state_from_approval()
        self.message_post(body=_('Rejected by %s.') % self.env.user.name)

    # Specific approval actions to be called from buttons
    def action_dept_manager_approve(self, comment=''):
        """Specific approval action for Department Manager."""
        self.action_approve(comment=comment)

    def action_gm_approve(self, comment=''):
        """Specific approval action for General Manager."""
        self.action_approve(comment=comment)

    def action_director_approve(self, comment=''):
        """Specific approval action for Director."""
        self.action_approve(comment=comment)

    def action_procurement_manager_approve(self, comment=''):
        """Specific approval action for Procurement Manager."""
        self.action_approve(comment=comment)




    def action_cancel(self):
        """Cancel the request - only available in draft"""
        if self.state not in ['draft', 'rejected']:
            raise UserError(_('You can only cancel requests in draft or rejected state.'))
        self.state = 'cancelled'
        self.message_post(body=_('Purchase request cancelled.'))

    def action_create_bank_process(self):
        """Convert approved request Bank Process (PO is created during allocation)"""
        if self.state not in ['approved', 'in_bank_process']:
            raise UserError(_('Only approved requests can be converted to Bank Process.'))

        # Check if active Bank Process already exists
        active_bps = self.bank_process_ids.filtered(lambda bp: bp.state != 'cancelled')
        
        if active_bps:
            bank_process = active_bps[0]
        else:
            bank_vals = {
                'purchase_request_id': self.id,
                'currency_id': self.currency_id.id,
                'amount': self.amount_total,
                'branch_id': self.branch_id.id,
            }
            bank_process = self.env['foreign.bank.process'].create(bank_vals)
            
            # Attach the PFI if present
            if self.pfi_attachment:
                self.env['ir.attachment'].create({
                    'name': self.pfi_attachment_name or 'PFI Attachment',
                    'type': 'binary',
                    'datas': self.pfi_attachment,
                    'res_model': 'foreign.bank.process',
                    'res_id': bank_process.id,
                })

        self.state = 'in_bank_process'

        return {
            'name': _('Bank Process'),
            'type': 'ir.actions.act_window',
            'res_model': 'foreign.bank.process',
            'res_id': bank_process.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_view_rfqs(self):
        """View related RFQs"""
        return {
            'name': _('Request for Quotations'),
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order',
            'view_mode': 'list,form',
            'domain': [('purchase_request_id', '=', self.id)],
            'context': {'default_purchase_request_id': self.id}
        }

    def action_view_pos(self):
        """View related Purchase Orders"""
        return {
            'name': _('Purchase Orders'),
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order',
            'view_mode': 'list,form',
            'domain': [('purchase_request_id', '=', self.id), ('state', 'in', ['purchase', 'done'])],
            'context': {'default_purchase_request_id': self.id}
        }

    @api.constrains('request_line_ids')
    def _check_request_lines_estimated_price(self):
        """Ensure every request line has a positive estimated_price when the request is saved."""
        for rec in self:
            for line in rec.request_line_ids:
                if float(line.estimated_price or 0.0) <= 0.0:
                    prod = line.product_id.display_name if line.product_id else _('(no product)')
                    raise ValidationError(_(
                        "Estimated Unit Price must be greater than zero for product %s on the request."
                    ) % prod)

class PurchaseRequestLine(models.Model):
    _name = 'purchase.request.line'
    _description = 'Purchase Request Line'
    _order = 'sequence, id'

    sequence = fields.Integer(string='Sequence', default=10)
    request_id = fields.Many2one(
        'purchase.request',
        string='Purchase Request',
        required=True,
        ondelete='cascade'
    )
    product_id = fields.Many2one(
        'product.product',
        string='Product',
        required=True
    )
    description = fields.Text(string='Description', required=True)
    quantity = fields.Float(
        string='Quantity',
        required=True,
        default=1.0
    )
    uom_id = fields.Many2one(
        'uom.uom',
        string='Unit of Measure',
        required=True
    )
    hs_code = fields.Char(string='HS Code')
    estimated_price = fields.Float(
        string='FOB Price',
        help='Estimated price per unit (FOB)',
       # required=True
    )
    estimated_total = fields.Float(
        string='Estimated Total',
        compute='_compute_estimated_total',
        store=True
    )
    specifications = fields.Text(string='Technical Specifications')
    required_date = fields.Date(string='Required Date')
    notes = fields.Text(string='Notes')

    @api.depends('quantity', 'estimated_price')
    def _compute_estimated_total(self):
        for line in self:
            line.estimated_total = line.quantity * line.estimated_price

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            name = self.product_id.display_name
            if self.product_id.description_purchase:
                name += '\n' + self.product_id.description_purchase
            self.description = name
            self.uom_id = self.product_id.uom_id
            self.estimated_price = self.product_id.standard_price
            # warn user if the computed price is zero or not positive
            if float(self.estimated_price or 0.0) <= 0.0:
                return {
                    'warning': {
                        'title': _('Estimated price missing'),
                        'message': _('Computed estimated price is zero. Please enter a positive Estimated Unit Price.')
                    }
                }

    @api.constrains('estimated_price')
    def _check_estimated_price(self):
        for rec in self:
            if rec.estimated_price <= 0:
                raise ValidationError("Estimated Unit Price must be greater than zero.")
    @api.model
    def create(self, vals):
        # Prevent saving a line with zero or missing estimated_price (shows error on Save & Close)
        if float(vals.get('estimated_price') or 0.0) <= 0.0:
            raise ValidationError(_("Estimated Unit Price must be greater than zero. Please enter a valid price."))
        return super(PurchaseRequestLine, self).create(vals)

    def write(self, vals):
        # Prevent updating a line to zero estimated_price (also covers Save & Close edit)
        if 'estimated_price' in vals and float(vals.get('estimated_price') or 0.0) <= 0.0:
            raise ValidationError(_("Estimated Unit Price must be greater than zero. Please enter a valid price."))
        return super(PurchaseRequestLine, self).write(vals)
