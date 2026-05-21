from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging
from datetime import datetime
_logger = logging.getLogger(__name__)


class LocalPurchaseRequest(models.Model):
    _name = 'local.purchase.request'
    _description = 'Local Purchase Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc, id desc'
    _rec_name = 'name'

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
        ('waiting_for_dept_manager', 'Waiting for Department Manager'),
        ('waiting_for_gm', 'Waiting for General Manager'),
        ('waiting_for_director', 'Waiting for Director'),
        ('waiting_for_procurement_manager', 'Waiting for Procurement Manager'),
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
        ('converted_to_rfq', 'RFQ Created'),
        ('converted_to_po', 'Converted to PO'),
    ], string='Status', default='draft', tracking=True, required=True)

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
    ], string='Request Type', required=True, default='local', tracking=True, readonly=True)

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

    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        required=True,
        default=lambda self: self.env.company.currency_id
    )

    request_line_ids = fields.One2many(
        'local.purchase.request.line',
        'request_id',
        string='Request Lines'
    )

    # Additional/legacy fields requested for parity with existing system
    request_for_partner = fields.Many2one('res.partner', string='Request For')
    customer_id = fields.Many2one('res.partner', string='Customer')
    request_kind = fields.Char(string='Type')
    to_replace = fields.Boolean(string='To Replace')
    remark = fields.Text(string='Remark')
    header_description = fields.Text(string='Description (Header)')
    manager_description = fields.Text(string='Manager Description')
    specification = fields.Text(string='Specification')
    spec_dep = fields.Many2one('hr.department', string='Spec Dept')
    stock_info = fields.Text(string='Stock Info')
    current_km = fields.Float(string='Current KM')
    prev_request_id = fields.Many2one('local.purchase.request', string='Previous Request')

    manager_user_id = fields.Many2one('res.users', string='Manager')
    gm_user_id = fields.Many2one('res.users', string='General Manager')
    director_user_id = fields.Many2one('res.users', string='Director')
    owner_id = fields.Many2one('res.users', string='Owner')
    property_name = fields.Char(string='Property')
    received = fields.Boolean(string='Received')

    processing_company_id = fields.Many2one('res.company', string='Processing Company')
    property_company_id = fields.Many2one('res.company', string='Property Company')
    procurement_company_id = fields.Many2one('res.company', string='Procurement Company')
    finance_company_id = fields.Many2one('res.company', string='Finance Company')

    next_step = fields.Char(string='Next Step')
    reason_instock = fields.Text(string='Reason In Stock')
    reason_purchased = fields.Text(string='Reason Purchased')
    purchased_amount = fields.Monetary(string='Purchased Amount', currency_field='currency_id')
    additional = fields.Text(string='Additional')
    mode = fields.Char(string='Mode')
    replaced_items = fields.Text(string='Replaced Items')
    flag = fields.Boolean(string='Flag')
    directors = fields.Many2many('res.users', string='Directors')
    phase_one = fields.Boolean(string='Phase One')
    phase_two = fields.Boolean(string='Phase Two')
    phase_three = fields.Boolean(string='Phase Three')
    phase_four = fields.Boolean(string='Phase Four')

    rfq_ids = fields.One2many('purchase.order', 'local_purchase_request_id', string='RFQs')
    po_ids = fields.One2many('purchase.order', 'local_purchase_request_id', string='Purchase Orders')
    rfq_count = fields.Integer(compute='_compute_related_counts', string='RFQ Count')
    po_count = fields.Integer(compute='_compute_related_counts', string='PO Count')

    required_date = fields.Date(string='Required Date', tracking=True)
    delivery_address = fields.Text(string='Delivery Address')

    picking_type_id = fields.Many2one(
        'stock.picking.type',
        string='Deliver To',
        required=True,
        domain="[('code', '=', 'incoming'), ('warehouse_id.branch_id', '=', branch_id)]",
        help="Warehouse operation type for delivery (e.g. Receipts)"
    )

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

    @api.model
    def create(self, vals_list):
        if not isinstance(vals_list, list):
            vals_list = [vals_list]

        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                user_id = vals.get('requested_by') or self.env.uid
                company_id = vals.get('company_id', self.env.company.id)

                if not vals.get('branch_id') or not vals.get('department_id'):
                    employee = self.env['hr.employee'].search([
                        ('user_id', '=', user_id),
                        ('company_id', '=', company_id)
                    ], limit=1)

                    if not vals.get('branch_id'):
                        if employee and employee.job_id and employee.job_id.analytic_account_id:
                            vals['branch_id'] = employee.job_id.analytic_account_id.id

                    if not vals.get('department_id') and employee and employee.department_id:
                        vals['department_id'] = employee.department_id.id

                branch_id = vals.get('branch_id')
                branch_code = '00'
                if branch_id:
                    branch = self.env['account.analytic.account'].browse(branch_id)
                    branch_code = branch.code or '00'

                year = datetime.now().year
                seq = self.env['ir.sequence'].next_by_code('local.purchase.request') or '00000'
                vals['name'] = f"LPR{branch_code}{year}{seq.zfill(5)}"

        return super().create(vals_list)

    @api.depends('rfq_ids', 'po_ids')
    def _compute_related_counts(self):
        for request in self:
            request.rfq_count = len(request.rfq_ids)
            request.po_count = len(request.po_ids)

    @api.depends('requested_by')
    def _compute_department_and_branch(self):
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

    @api.depends('state', 'approval_request_id.approver_ids')
    def _compute_is_current_user_approver(self):
        for rec in self:
            rec.is_current_user_approver = self.env.user in (rec.approval_request_id.approver_ids or self.env['res.users'])

    @api.depends('approval_request_id', 'approval_request_id.current_step_id')
    def _compute_current_step_info(self):
        for rec in self:
            rec.current_step_name = ''
            rec.current_approver_name = ''
            if rec.approval_request_id and rec.approval_request_id.current_step_id:
                current_step = rec.approval_request_id.current_step_id
                rec.current_step_name = current_step.name
                rec.current_approver_name = ', '.join(rec.approval_request_id.approver_ids.mapped('name'))

    @api.depends('approval_request_id')
    def _compute_step_progress(self):
        for rec in self:
            if rec.approval_request_id:
                rec.step_progress = rec.approval_request_id.step_progress or "<span>No progress available.</span>"
            else:
                rec.step_progress = "<span>Not submitted for approval yet.</span>"

    @api.depends('request_line_ids.estimated_total')
    def _compute_amount_total(self):
        for rec in self:
            rec.amount_total = sum(line.estimated_total for line in rec.request_line_ids)

    def action_submit(self):
        self.ensure_one()
        if not self.request_line_ids:
            raise UserError(_('Please add at least one request line before submitting.'))

        flow = self.env['approval.flow'].search([
            ('request_model_id.model', '=', 'local.purchase.request'),
            ('active', '=', True),
            ('company_id', '=', self.company_id.id)
        ], limit=1)

        if not flow:
            raise UserError(_("No approval flow defined for Local Purchase Requests!"))

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
            'state': 'pending',
            'approval_request_id': approval_req.id
        })

        approval_req.process_action()
        self._sync_state_from_approval()
        self.message_post(body=_('Local purchase request submitted for approval.'))

    def _sync_state_from_approval(self):
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
            _logger.info(f"Changing Local Purchase Request '%s' state from '%s' to '%s'.", self.name, self.state, final_state)
            self.state = final_state

    def _get_approval_state_mapping(self):
        return {
            'Manager Purchase Approval': 'waiting_for_dept_manager',
            'General Purchase Manager': 'waiting_for_gm',
            'Director Purchase Approval': 'waiting_for_director',
            'Procurement Purchase Officer': 'waiting_for_procurement_manager',
            '__approved__': 'approved',
            '__rejected__': 'rejected',
        }

    def action_approve(self, comment=''):
        self.ensure_one()
        if not self.is_current_user_approver:
            raise UserError(_("You are not the current approver for this request or the action has already been processed."))

        if not self.approval_request_id:
            raise UserError(_("No approval request linked to this record."))
        self.approval_request_id.with_context(action_type='approve', comment=comment).process_action()
        self._sync_state_from_approval()
        self.message_post(body=_('Approved by %s.') % self.env.user.name)

    def action_reject(self, comment=''):
        self.ensure_one()
        if not self.approval_request_id:
            raise UserError(_("No approval request linked to this record."))
        self.approval_request_id.with_context(action_type='reject', comment=comment).process_action()
        self._sync_state_from_approval()
        self.message_post(body=_('Rejected by %s.') % self.env.user.name)

    def action_dept_manager_approve(self, comment=''):
        self.action_approve(comment=comment)

    def action_gm_approve(self, comment=''):
        self.action_approve(comment=comment)

    def action_director_approve(self, comment=''):
        self.action_approve(comment=comment)

    def action_procurement_manager_approve(self, comment=''):
        self.action_approve(comment=comment)

    def action_view_rfqs(self):
        return {
            'name': _('Request for Quotations'),
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order',
            'view_mode': 'list,form',
            'domain': [('local_purchase_request_id', '=', self.id)],
            'context': {'default_local_purchase_request_id': self.id}
        }

    def action_view_pos(self):
        return {
            'name': _('Purchase Orders'),
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order',
            'view_mode': 'list,form',
            'domain': [('local_purchase_request_id', '=', self.id), ('state', 'in', ['purchase', 'done'])],
            'context': {'default_local_purchase_request_id': self.id}
        }

    def action_cancel(self):
        """Cancel the request - only available in draft"""
        if self.state not in ['draft', 'rejected']:
            raise UserError(_('You can only cancel requests in draft or rejected state.'))
        self.state = 'cancelled'
        self.message_post(body=_('Local purchase request cancelled.'))

    def action_convert_to_rfq(self):
        """Convert approved request to RFQ"""
        if self.state != 'approved':
            raise UserError(_('Only approved requests can be converted to RFQ.'))

        rfq_vals = {
            'local_purchase_request_id': self.id,
            'partner_id': self.vendor_id.id,
            'partner_ref': self.vendor_ref,
            'branch_id': self.branch_id.id if self.branch_id else False,
            'order_type': self.request_type,
            'state': 'draft',
            'picking_type_id': self.picking_type_id.id,
            'order_line': [(0, 0, {
                'product_id': line.product_id.id,
                'name': line.description,
                'product_qty': line.quantity,
                'product_uom': line.uom_id.id,
                'price_unit': line.estimated_price,
                'date_planned': self.required_date or fields.Date.context_today(self),
            }) for line in self.request_line_ids]
        }

        rfq = self.env['purchase.order'].create(rfq_vals)
        self.state = 'converted_to_rfq'

        return {
            'name': _('Request for Quotation'),
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order',
            'res_id': rfq.id,
            'view_mode': 'form',
            'target': 'current',
        }

    @api.constrains('request_line_ids')
    def _check_request_lines_estimated_price(self):
        for rec in self:
            for line in rec.request_line_ids:
                if float(line.estimated_price or 0.0) <= 0.0:
                    prod = line.product_id.display_name if line.product_id else _('(no product)')
                    raise ValidationError(_(
                        "Estimated Unit Price must be greater than zero for product %s on the request."
                    ) % prod)


class LocalPurchaseRequestLine(models.Model):
    _name = 'local.purchase.request.line'
    _description = 'Local Purchase Request Line'
    _order = 'sequence, id'

    sequence = fields.Integer(string='Sequence', default=10)
    request_id = fields.Many2one(
        'local.purchase.request',
        string='Purchase Request',
        required=True,
        ondelete='cascade'
    )
    product_id = fields.Many2one('product.product', string='Product', required=True)
    description = fields.Text(string='Description', required=True)
    quantity = fields.Float(string='Quantity', required=True, default=1.0)
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure', required=True)
    to_replace = fields.Boolean(string='To Replace')
    estimated_price = fields.Float(string='Estimated Unit Price')
    estimated_total = fields.Float(string='Estimated Total', compute='_compute_estimated_total', store=True)
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
            self.description = self.product_id.display_name
            self.uom_id = self.product_id.uom_id
            self.estimated_price = self.product_id.standard_price
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
        if float(vals.get('estimated_price') or 0.0) <= 0.0:
            raise ValidationError(_('Estimated Unit Price must be greater than zero. Please enter a valid price.'))
        return super(LocalPurchaseRequestLine, self).create(vals)

    def write(self, vals):
        if 'estimated_price' in vals and float(vals.get('estimated_price') or 0.0) <= 0.0:
            raise ValidationError(_('Estimated Unit Price must be greater than zero. Please enter a valid price.'))
        return super(LocalPurchaseRequestLine, self).write(vals)
