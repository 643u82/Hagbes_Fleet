from odoo import models, fields, api
from odoo.exceptions import UserError,ValidationError
import logging
_logger = logging.getLogger(__name__)

class MRCVHeader(models.Model):
    _name = 'mrcv.header'
    _description = 'Material Received Confirmation Voucher'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    name = fields.Char(string="MRCV Reference", required=True, default='New', copy=False, readonly=True)
    workshop_order_id = fields.Many2one(
        'workshop.order',
        string="Workshop Job Order",
        help="Link this MRCV to the related workshop job order.",
        tracking=True
    )
    job_status = fields.Selection(
        related='workshop_order_id.status',
        string="Job Status"
    )
    date = fields.Date(string="Date", default=fields.Date.today,tracking=True)
    partner_id = fields.Many2one('res.partner', string="Customer Name",tracking=True)
    # approval_status = fields.Selection(
    #     related='approval_request_id.status', string="Approval Status", store=True, readonly=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('pending','Pending'),
        ('approved', 'Approved'),
        ('issued', 'Issued'),
        ('rejected', 'Rejected')
    ], default='draft', string='Status',tracking=True)
    line_ids = fields.One2many('mrcv.line', 'mrcv_id', string="Items",tracking=True)
    approval_request_id = fields.Many2one('approval.request', string="Approval Request", readonly=True,tracking=True)
    feeding_picking_id = fields.Many2one('stock.picking', string="Feeding Picking",tracking=True)
    requester_branch_id=fields.Many2one(
        'account.analytic.account',
        string='Branch',
        domain=[('plan_id', '=', 'Branch')],
        default=lambda self: self.env.user.default_branch_id,
        tracking=True
    )

    issuer_warehouse = fields.Many2one('stock.warehouse', string="Warehouse",required=True,tracking=True)

    company_id = fields.Many2one(
        'res.company', string='Company',
        default=lambda self: self.env.company,
        tracking=True
    )
    step_progress = fields.Html(string="Approval Progress", compute='_compute_step_progress',tracking=True)
    is_approver = fields.Boolean(string="Is Approver", compute='_compute_is_approver')

    def _compute_is_approver(self):
        for rec in self:
            rec.is_approver = self.env.user in rec.approval_request_id.approver_ids

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if self.env.context.get('active_model') == 'workshop.order':
            res['workshop_order_id'] = self.env.context.get('active_id')
        return res

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('mrcv.header') or 'MRCV-00001'
        return super().create(vals)

    def action_submit(self):
        self.ensure_one()

        if self.state == 'submitted' and self.approval_request_id:
            raise UserError("This record has already been submitted for approval.")

        flow = self.env['approval.flow'].search([
            ('request_model_id.model', '=', 'mrcv.header'),
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
            'module_name': 'hagbes_workshop_management',
            'res_id': self.id,
            'current_step_id': first_step.id,
            'status': 'pending',
        })

        self.write({
            'state': 'pending',
            'approval_request_id': approval_req.id
        })

        approval_req.process_action()

    def _sync_state_from_approval(self):
        if not self.approval_request_id:
            return
        status = self.approval_request_id.status
        if status == 'approved':
            self.state = 'approved'
            self._create_feeding_transfer()
        elif status == 'rejected':
            self.state = 'rejected'
        elif status == 'pending':
            self.state = 'pending'
        else:
            self.state = 'draft'

    def action_approve(self, comment=''):
        self.ensure_one()
        if not self.approval_request_id:
            raise UserError("No approval request linked to this MRCV.")
        self.approval_request_id.with_context(action_type='approve', comment=comment).process_action()
        self._sync_state_from_approval()

    def action_reject(self, comment=''):
        self.ensure_one()
        if not self.approval_request_id:
            raise UserError("No approval request linked to this MRCV.")
        self.approval_request_id.with_context(action_type='reject', comment=comment).process_action()
        self._sync_state_from_approval()

    def _compute_step_progress(self):
        for rec in self:
            rec.step_progress = rec.approval_request_id.step_progress if rec.approval_request_id else "<span>No approval steps yet.</span>"

    def _create_feeding_transfer(self):
        """Create delivery order for internal issue, sending products to a dedicated virtual location."""
        self.ensure_one()

        picking_type = self.env['stock.picking.type'].sudo().search([
            ('code', '=', 'mrcv'),
            ('warehouse_id', '=', self.requester_branch_id.id)
        ], limit=1)

        # If not found, create a new exhibition picking type for this warehouse
        if not picking_type:
            # print(self.env['stock.picking.type'].fields_get()['code']['selection'])
            picking_type = self.env['stock.picking.type'].sudo().create({
                'name': f'MRCV Operation - {self.issuer_warehouse.name}',
                'code': 'mrcv',
                'sequence_code': self.name,
                'warehouse_id': self.issuer_warehouse.id,
                'company_id': self.company_id.id,
            })
            _logger.info(
                "New mrcv Picking Type created for warehouse %s: %s",
                self.issuer_warehouse.name,
                picking_type.name
            )

        destination_location = self.env['stock.location'].search([
            ('usage', '=', 'transit'),
            ('name', '=', 'MRCV')
        ], limit=1)
        if not destination_location:
            destination_location = self.env['stock.location'].sudo().create({
                'name': 'MRCV',
                'usage': 'transit',
                'company_id': self.company_id.id,
            })

        picking = self.env['stock.picking'].create({
            'picking_type_id': picking_type.id,
            'origin': self.name,
            'internal_issue': True,
            'location_id': self.issuer_warehouse.lot_stock_id.id,  # Source = warehouse stock
            'location_dest_id': destination_location.id,  # Destination = Internal Issue virtual
            'company_id': self.company_id.id,
            'scheduled_date': fields.Datetime.now(),
            'move_ids_without_package': [
                (0, 0, {
                    'product_id': line.product_id.id,
                    'name': line.product_id.display_name,
                    'product_uom': line.uom_id.id,
                    'product_uom_qty': line.quantity,
                    'location_id': self.issuer_warehouse.lot_stock_id.id,
                    'location_dest_id': destination_location.id,
                })
                for line in self.line_ids
            ],
        })
        picking.action_confirm()
        self.feeding_picking_id = picking
        _logger.info("Internal Issue delivery order created: %s", picking.name)
    # def write(self, vals):
    #     if any(rec.state in ['pending', 'approved'] for rec in self):
    #         blocked_fields = set(vals.keys()) - {'state'}
    #         if blocked_fields:
    #             raise ValidationError(
    #                 "You cannot edit this document once it is pending or approved."
    #             )
    #     return super().write(vals)
    def action_create_mrv(self):
        self.ensure_one()

        # Create MRV header
        mrv = self.env['mrv.header'].create({
            'mrcv_id': self.id,
            'receiver_id': self.env.user.id,
            'requester_branch_id': self.requester_branch_id.id,
            'issuer_warehouse':self.issuer_warehouse.id,
            'company_id': self.company_id.id,
        })

        # Copy line items
        for line in self.line_ids:
            self.env['mrv.line'].create({
                'mrv_id': mrv.id,
                'mrcv_line_id': line.id,
                'product_id': line.product_id.id,
                'quantity': line.quantity,
                'uom_id': line.uom_id.id,
            })

        return {
            'name': "MRV",
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'mrv.header',
            'res_id': mrv.id,
            'target': 'current',
        }
class MRCVLine(models.Model):
    _name = 'mrcv.line'
    _description = 'MRCV Line'

    mrcv_id = fields.Many2one('mrcv.header', string="MRCV")
    product_id = fields.Many2one('product.product', string="Product", required=True)
    quantity = fields.Float(string="Quantity", required=True)
    issued_qty = fields.Float(string="Issued Qty", default=0)
    uom_id = fields.Many2one(
        'uom.uom',
        string="UoM",
        required=True,
        domain="[('category_id', '=', product_id.uom_id.category_id)]"
    )

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.uom_id = self.product_id.uom_id