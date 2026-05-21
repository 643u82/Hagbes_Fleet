from odoo import models, fields, api
from odoo.exceptions import UserError
from odoo.exceptions import ValidationError
from datetime import date
import logging
_logger = logging.getLogger(__name__)

class InterstockTransfer(models.Model):
    _name = 'interstock.transfer'
    _description = 'Inter-Stock Transfer Request'
    name = fields.Char(string='Reference', required=True, copy=False, readonly=True, default='New')
    Requested_by = fields.Many2one('res.users', string="Requested By", required=True, default=lambda self: self.env.user)
    Issued_by = fields.Many2one('res.users', string="Issued By")
    items_summary = fields.Char(string='Requested Products', compute='_compute_items_summary', store=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('finance_checked', 'Finance Checked'),
        ('submitted', 'Submitted'),
        ('ready', 'Ready'),
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('done', 'Done'),
    ], default='draft', string="Status", tracking=True)
    company_id = fields.Many2one('res.company', string='Company',
        default=lambda self: self.env.company
    )
    finance_checker = fields.Many2one('res.users', string="Finance Checker")
    items_requested = fields.One2many('request.items', 'transfer_id', string="Requested Items")
    requester_branch_id = fields.Many2one('account.analytic.account', string='Company Branch',domain=[('plan_id', '=', 'Branch')],default=lambda self: self.env.user.default_branch_id)
    issuer_branch_id = fields.Many2one('account.analytic.account', string='Company Branch',domain=lambda self: [('plan_id.name', '=', 'Branch'),('id', '!=', self.env.user.default_branch_id.id)])
    requester_location_id = fields.Many2one('stock.location', string="Requester Location", required=True,domain=lambda self: [('warehouse_id.branch_id', '=', self.env.user.default_branch_id.id)])
    issuer_warehouse_id = fields.Many2one('stock.warehouse', string="Issuer Warehouse", required=True,domain="[('branch_id', '=', issuer_branch_id)]")
    requester_warehouse_id = fields.Many2one('stock.warehouse', string="Requester warehouse", required=True, domain=lambda self: [('branch_id', '=', self.env.user.default_branch_id.id)])
    approval_request_id = fields.Many2one('approval.request', string="Approval Request", readonly=True)
    step_progress = fields.Html(string="Approval Progress", compute='_compute_step_progress')
    feeding_picking_id = fields.Many2one('stock.picking', string="Feeding Picking")
    receiving_picking_id = fields.Many2one('stock.picking', string="Receiving Picking")
    @api.model
    def create(self, vals):
        record = super(InterstockTransfer, self).create(vals)
        if record.name == 'New':
            current_year = date.today().year
            print(current_year, "current year")
            branch_id = vals.get('requester_branch_id')
            print(branch_id, "warehouse")
            branch_code = record.requester_branch_id.code or 'LOC'  # default fallback
            seq_number = self.env['ir.sequence'].next_by_code('interstock.transfer') or '0000'
            seq_number = seq_number.replace('TRF', '').zfill(4)
            record.name = f'TRF{branch_code}{current_year}{seq_number}'
        return record

    @api.depends('items_requested.product_id', 'items_requested.quantity', 'items_requested.uom_id')
    def _compute_items_summary(self):
        for rec in self:
            summary = []
            for line in rec.items_requested:
                if line.product_id:
                    summary.append(f"{line.product_id.name} ({line.quantity} {line.uom_id.name})")
            rec.items_summary = ", ".join(summary)

    @api.onchange('issuer_branch_id')
    def _onchange_issuer_branch(self):
        self.issuer_warehouse_id = False
        return {
            'domain': {
                'issuer_warehouse_id': [('branch_id', '=', self.issuer_branch_id.id)]
            }
        }

    def _create_feeding_transfer(self):
        self.ensure_one()
        print(self.issuer_warehouse_id, "issuer warehouse")
        company = self.company_id or self.env.company

        picking_type = (
        self.env['stock.picking.type']
        .with_company(company)
        .sudo()
        .search([
            ('code', '=', 'internal'),
            ('warehouse_id', '=', self.issuer_warehouse_id.id),
        ], limit=1)
         )
        
        if not picking_type:
            raise UserError("No internal picking type found for issuer branch.")

        if not self.issuer_warehouse_id or not self.issuer_warehouse_id.lot_stock_id:
            raise UserError("Issuer warehouse stock location is missing.")

        valid_lines = self.items_requested.filtered(lambda l: l.location_id)

        if not valid_lines:
            raise UserError("All requested items must have a source location.")

        transit_location = self._get_or_create_transit_location(company)
        print(transit_location, "transit location") 
        picking = self.env['stock.picking'].sudo().create({
            'picking_type_id': picking_type.id,
            'origin': self.name,
            'inter_store_issue': True,
            'location_id': self.issuer_warehouse_id.lot_stock_id.id,
            'location_dest_id': transit_location.id,
            'company_id': company.id,
            'scheduled_date': fields.Datetime.now(),
            'move_ids_without_package': [
                (0, 0, {
                    'product_id': line.product_id.id,
                    'name': line.product_id.display_name,
                    'product_uom': line.uom_id.id,
                    'product_uom_qty': line.quantity,
                    'location_id': line.location_id.id,
                    'location_dest_id': transit_location.id,
                }) for line in valid_lines
            ],
        })

        picking.action_confirm()

        self.write({
            'feeding_picking_id': picking.id,
            'state': 'done',
        })

    def _create_receiving_transfer(self):
        self.ensure_one()
        self = self.sudo()

        company = self.company_id or self.env.company

        picking_type = self.env['stock.picking.type'].search([
            ('code', '=', 'internal'),
            ('warehouse_id.branch_id', '=', self.requester_branch_id.id),
        ], limit=1)

        if not picking_type:
            raise UserError(
                "No internal picking type found for branch %s"
                % self.requester_branch_id.display_name
            )

        if not self.requester_location_id:
            raise UserError("Requester Location must be set before receiving transfer.")

        if not self.items_requested:
            raise UserError("No items available to receive.")

        transit_location = self._get_or_create_transit_location(company)

        picking = self.env['stock.picking'].create({
            'picking_type_id': picking_type.id,
            'origin': self.name,
            'location_id': transit_location.id,
            'location_dest_id': self.requester_location_id.id,
            'company_id': company.id,
            'scheduled_date': fields.Datetime.now(),
            'move_ids_without_package': [
                (0, 0, {
                    'product_id': line.product_id.id,
                    'name': line.product_id.display_name,
                    'product_uom': line.uom_id.id,
                    'product_uom_qty': line.quantity,
                    'location_id': transit_location.id,
                    'location_dest_id': self.requester_location_id.id,
                }) for line in self.items_requested
            ],
        })

        picking.action_confirm()
        self.receiving_picking_id = picking.id

    def _compute_step_progress(self):
        for rec in self:
            rec.step_progress = rec.approval_request_id.step_progress if rec.approval_request_id else "<span>No approval steps yet.</span>"
    def action_submit(self):
        self.ensure_one()
        flow = self.env['approval.flow'].search([
            ('request_model_id.model', '=', 'interstock.transfer'),
            ('active', '=', True),
            ('company_id', '=', self.company_id.id)
        ], limit=1)
        if not flow:
            raise UserError("No approval flow defined for MRCV!")

        first_step = self.env['approval.step'].search([
            ('flow_id', '=', flow.id)
        ], order='sequence asc', limit=1)
        if not first_step:
            raise UserError("No steps defined for this approval flow.")
        approval_req = self.env['approval.request'].create({
            'flow_id': flow.id,
            'res_model': self._name,
            'module_name': 'hagbes_inventory_extension',
            'res_id': self.id,
            'current_step_id': first_step.id,
            'branch_id': self.issuer_branch_id.id,
            'status': 'pending',
        })

        _logger.info("Approval request created: %s", approval_req)
        if  approval_req:
            _logger.info("Approval Flow: %s", approval_req.flow_id.name)
        self.write({
            'state': 'submitted',
            'approval_request_id': approval_req.id
        })

        approval_req.process_action()

    def _sync_state_from_approval(self):
        if not self.approval_request_id:
            return
        status = self.approval_request_id.status
        if status == 'approved':
            self.state = 'approved'
            transfers = self.search([
                ('state', '=', 'approved'),
                ('feeding_picking_id', '=', False),
            ])
            for transfer in transfers:
                transfer._create_feeding_transfer()
        elif status == 'rejected':
            self.state = 'rejected'
        elif status == 'pending':
            self.state = 'submitted'
        else:
            self.state = 'draft'
    def action_finance_checker(self):
        """Mark as Finance Checked"""

        self.ensure_one()
        self.write({
            'finance_checker': self.env.user.id,
            'state': 'finance_checked',
        })
        self._create_receiving_transfer()

    def action_approve(self, comment=''):
        self.ensure_one()
        if not self.approval_request_id:
            raise UserError("No approval request linked to this inter store transfer.")
        self.approval_request_id.with_context(action_type='approve', comment=comment).process_action()
        self._sync_state_from_approval()

    def action_reject(self, comment=''):
        self.ensure_one()
        if not self.approval_request_id:
            raise UserError("No approval request linked to this inter store transfer.")
        self.approval_request_id.with_context(action_type='reject', comment=comment).process_action()
        self._sync_state_from_approval()

    def action_amend(self, comment=''):
        self.ensure_one()
        if not self.approval_request_id:
            raise UserError("No approval request linked to this inter store transfer.")
        self.approval_request_id.with_context(action_type='amend', comment=comment).process_action()
        self._sync_state_from_approval()

    def action_revert(self, comment=''):
        self.ensure_one()
        if not self.approval_request_id:
            raise UserError("No approval request linked to this inter store transfer.")
        self.approval_request_id.with_context(action_type='revert', comment=comment).process_action()
        self._sync_state_from_approval()

    def action_resubmit(self, comment=''):
        self.ensure_one()
        if not self.approval_request_id:
            raise UserError("No approval request linked to this inter store transfer.")
        self.approval_request_id.with_context(action_type='resubmit', comment=comment).process_action()
        self._sync_state_from_approval()

    @api.onchange('requester_warehouse_id')
    def _onchange_requester_warehouse_id(self):
        if self.requester_warehouse_id:
            self.requester_location_id = self.requester_warehouse_id.lot_stock_id
            return {
                'domain': {
                    'requester_location_id': [('location_id', 'child_of', self.requester_warehouse_id.lot_stock_id.id)]
                }
            }
        else:
            self.requester_location_id = False
            return {
                'domain': {
                    'requester_location_id': []
                }
            }
    @api.constrains('items_requested')
    def _check_items_requested_not_empty(self):
        for rec in self:
            if not rec.items_requested:
                raise ValidationError("At least one product must be added before saving.")

    def _get_or_create_transit_location(self, company):
        transit_location = self.env['stock.location'].search([
            ('usage', '=', 'transit'),
            ('company_id', '=', company.id),
        ], limit=1)

        if transit_location:
            return transit_location

        parent_location = self.env.ref('stock.stock_location_locations')

        return self.env['stock.location'].create({
            'name': 'Inter-Branch Transit',
            'usage': 'transit',
            'location_id': parent_location.id,
            'company_id': company.id,
            'active': True,
        })
