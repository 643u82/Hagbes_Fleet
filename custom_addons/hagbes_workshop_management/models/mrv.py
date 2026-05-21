from odoo import models, fields, api
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class MRVHeader(models.Model):
    _name = 'mrv.header'
    _description = 'Material Receiving Voucher'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string="MRV Reference",
        required=True,
        default='New',
        copy=False,
        readonly=True,
        tracking=True
    )
    date = fields.Date(string="Date", default=fields.Date.today, tracking=True)
    mrcv_id = fields.Many2one('mrcv.header', string="Related MRCV", tracking=True)
    receiver_id = fields.Many2one('res.users', string="Received By", default=lambda self: self.env.user, tracking=True)
    requester_branch_id = fields.Many2one(
        'account.analytic.account',
        string='Branch',
        domain=[('plan_id', '=', 'Branch')],
        default=lambda self: self.env.user.default_branch_id,
        tracking=True
    )
    job_id = fields.Many2one('workshop.order', string='Job')
    receiving_picking_id = fields.Many2one('stock.picking', string="Receiving Picking", tracking=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('pending','Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], default='draft', string='Status', tracking=True)
    line_ids = fields.One2many('mrv.line', 'mrv_id', string="Items", tracking=False)
    issuer_warehouse = fields.Many2one('stock.warehouse', string="Issuing Warehouse", tracking=True)
    company_id = fields.Many2one('res.company', string="Company", default=lambda self: self.env.company, tracking=True)
    approval_request_id = fields.Many2one('approval.request', string="Approval Request", readonly=True, tracking=True)
    step_progress = fields.Html(string="Approval Progress", compute='_compute_step_progress', store=False)
    is_approver = fields.Boolean(string="Is Approver", compute='_compute_is_approver')

    def _compute_is_approver(self):
        for rec in self:
            rec.is_approver = self.env.user in rec.approval_request_id.approver_ids

    @api.model
    def create(self, vals):
        # Auto-generate name
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('mrv.header') or 'MRV-00001'

        # If an MRCV is linked, use its job_id
        if vals.get('mrcv_id'):
            mrcv = self.env['mrcv.header'].browse(vals['mrcv_id'])
            if mrcv and mrcv.workshop_order_id:
                vals['job_id'] = mrcv.workshop_order_id.id

        rec = super().create(vals)
        rec.message_post(body="MRV created.")
        return rec

    def action_submit(self):
        """Submit MRV for approval."""
        self.ensure_one()
        self._check_mrcv_quantities()
        if self.state in ('submitted', 'pending') and self.approval_request_id:
            raise UserError("This MRV has already been submitted for approval.")
        flow = self.env['approval.flow'].search([
            ('request_model_id.model', '=', 'mrv.header'),
            ('active', '=', True),
            ('company_id', '=', self.company_id.id)
        ], limit=1)
        if not flow:
            raise UserError("No approval flow defined for MRV!")
        first_step = self.env['approval.step'].search([('flow_id', '=', flow.id)], order='sequence asc', limit=1)
        if not first_step:
            raise UserError("No steps defined for this approval flow.")

        approval_req = self.env['approval.request'].create({
            'flow_id': flow.id,
            'res_model': self._name,
            'module_name': 'hagbes_workshop_management',
            'res_id': self.id,
            'current_step_id': first_step.id,
            'status': 'pending',
        })

        self.write({'state': 'pending', 'approval_request_id': approval_req.id})
        approval_req.process_action()
        self.message_post(body="MRV submitted for approval.")

    def action_approve(self, comment=''):
        self.ensure_one()
        if not self.approval_request_id:
            raise UserError("No approval request linked to this MRV.")
        self.approval_request_id.with_context(action_type='approve', comment=comment).process_action()
        self._sync_state_from_approval()
        self.message_post(body=f"MRV approved. {comment or ''}")

    def action_reject(self, comment=''):
        self.ensure_one()
        if not self.approval_request_id:
            raise UserError("No approval request linked to this MRV.")
        self.approval_request_id.with_context(action_type='reject', comment=comment).process_action()
        self._sync_state_from_approval()
        self.message_post(body=f"MRV rejected. {comment or ''}")

    def _check_mrcv_quantities(self):
        """Stop creating MRV if full quantity is already received."""
        for rec in self:
            if not rec.mrcv_id:
                continue

            # Total quantity on MRCV
            total_mrcv_qty = sum(rec.mrcv_id.line_ids.mapped('quantity'))

            # Total quantity already covered by previous MRVs
            existing_mrvs = self.env['mrv.header'].search([
                ('mrcv_id', '=', rec.mrcv_id.id),
                ('state', '!=', 'rejected'),
                ('id', '!=', rec.id)
            ])

            received_qty = 0
            for mrv in existing_mrvs:
                received_qty += sum(mrv.line_ids.mapped('quantity'))

            # Incoming MRV quantity
            incoming_qty = sum(rec.line_ids.mapped('quantity'))

            if received_qty + incoming_qty > total_mrcv_qty:
                raise UserError(
                    "The quantities for this MRCV are already fully received. "
                    "You cannot create more MRVs for this MRCV."
                )

    def _sync_state_from_approval(self):
        """Sync MRV state with approval and create picking if approved."""
        for rec in self:
            if not rec.approval_request_id:
                continue
            status = rec.approval_request_id.status
            if status == 'approved':
                rec.state = 'approved'
                if not rec.receiving_picking_id:
                    try:
                        rec._create_receiving_transfer()
                    except Exception as e:
                        _logger.exception("Failed to create receiving transfer after approval: %s", e)
                        rec.message_post(body=f"Approval succeeded but creating receiving transfer failed: {e}")
            elif status == 'rejected':
                rec.state = 'rejected'
            elif status == 'pending':
                rec.state = 'submitted'
            else:
                rec.state = 'draft'

    @api.depends('approval_request_id')
    def _compute_step_progress(self):
        for rec in self:
            rec.step_progress = rec.approval_request_id.step_progress if rec.approval_request_id else "<span>No approval steps yet.</span>"

    def _create_receiving_transfer(self):
        """Create stock picking and validate to update inventory."""
        self = self.sudo()
        if not self.issuer_warehouse:
            raise UserError("Missing Issuer Warehouse on MRV.")
        picking_type = self.env['stock.picking.type'].sudo().search([
            ('code', '=', 'mrv'),
            ('warehouse_id', '=', self.issuer_warehouse.id)
        ], limit=1)
        if not picking_type:
            picking_type = self.env['stock.picking.type'].sudo().create({
                'name': f'MRV Operation - {self.requester_branch_id.name if self.requester_branch_id else "Default"}',
                'code': 'mrv',
                'sequence_code': 'MRV',
                'warehouse_id': self.issuer_warehouse.id,
                'company_id': self.company_id.id,
            })

        dest_location = self.env['stock.location'].sudo().search([('usage', '=', 'internal'), ('name', '=', 'MRV')], limit=1)
        if not dest_location:
            dest_location = self.env['stock.location'].sudo().create({
                'name': 'MRV',
                'usage': 'internal',
                'company_id': self.company_id.id
            })

        moves = []
        for line in self.line_ids:
            if not line.product_id or not line.quantity:
                continue
            moves.append((0, 0, {
                'product_id': line.product_id.id,
                'name': line.product_id.display_name,
                'product_uom': line.uom_id.id or line.product_id.uom_id.id,
                'product_uom_qty': line.quantity,
                'location_id': dest_location.id,
                'location_dest_id': self.issuer_warehouse.lot_stock_id.id,
            }))

        if not moves:
            raise UserError("No valid MRV lines to create receiving transfer.")

        picking_vals = {
            'picking_type_id': picking_type.id,
            'origin': self.name,
            'location_id': dest_location.id,
            'location_dest_id': self.issuer_warehouse.lot_stock_id.id,
            'company_id': self.company_id.id,
            'scheduled_date': fields.Datetime.now(),
            'move_ids_without_package': moves,
        }

        picking = self.env['stock.picking'].sudo().create(picking_vals)
        picking.action_confirm()
        picking.action_assign()
        picking.button_validate()  # moves items into inventory
        self.receiving_picking_id = picking
        self.message_post(body=f"Receiving Picking <b>{picking.name}</b> created and inventory updated.")
        _logger.info("MRV receiving picking created: %s", picking.name)
        return picking


class MRVLine(models.Model):
    _name = 'mrv.line'
    _description = 'MRV Line'
    _inherit = ['mail.thread']

    mrv_id = fields.Many2one('mrv.header', string="MRV", ondelete='cascade', tracking=False)
    product_id = fields.Many2one('product.product', string="Product", required=True, tracking=True)
    quantity = fields.Float(string="Quantity", required=True, tracking=True)
    uom_id = fields.Many2one('uom.uom', string="UoM", tracking=True)
    mrcv_line_id = fields.Many2one('mrcv.line', string="Related MRCV Line")
    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id and self.product_id.uom_id:
            self.uom_id = self.product_id.uom_id.id
        else:
            self.uom_id = False
