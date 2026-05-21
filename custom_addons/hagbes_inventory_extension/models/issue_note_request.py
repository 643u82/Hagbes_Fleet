from odoo import models, fields, api
from odoo.exceptions import UserError
from odoo.exceptions import ValidationError
import logging
_logger = logging.getLogger(__name__)
from datetime import date
class IssuesRequest(models.Model):
    _name = 'issue.requests'
    _description = 'Internal Issue Request'

    name = fields.Char(string='Reference', required=True, copy=False, readonly=True, default='New')
    requested_by = fields.Many2one('res.users', string="Requested By", required=True,default=lambda self: self.env.user)
    company_id = fields.Many2one('res.company', string='Company',default=lambda self: self.env.company)
    requester_branch_id = fields.Many2one('account.analytic.account', string='Requester Company Branch',default=lambda self: self.env.user.default_branch_id)
    issuer_company = fields.Many2one('account.analytic.account', string='Issuing Company Branch',default=lambda self: self.env.user.default_branch_id)
    issuer_department = fields.Many2one('hr.department',string="Issuing Department",required=True,default=lambda self: self.env.user.sudo().department_id)
    issuer_warehouse = fields.Many2one('stock.warehouse', string="Issuing Warehouse",required=True)
    subject = fields.Char(string='Subject', required=True, store=True)
    issue_description = fields.Char(string='Reason for Issue', required=True, store=True)
    items_requested = fields.One2many('issue.requests.items', 'issued_id', string="Requested Items")
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('done', 'Done'),
    ], default='draft', string="Status", tracking=True)
    # approval customization
    step_progress = fields.Html(string="Approval Progress", compute='_compute_step_progress')
    approval_request_id = fields.Many2one('approval.request', string="Approval Request", readonly=True)
    feeding_picking_id = fields.Many2one('stock.picking', string="Receiving Picking")

    def create(self, vals):
        record = super(IssuesRequest, self).create(vals)
        if record.name == 'New':
            current_year = date.today().year
            branch_code = record.requester_branch_id.code or 'LOC'  # default fallback
            seq_number = self.env['ir.sequence'].next_by_code('issue.requests') or '0000'
            seq_number = seq_number.replace('ISN', '').zfill(4)
            record.name = f'ISN{branch_code}{current_year}{seq_number}'
        return record

    @api.onchange('issuer_company','issuer_department')
    def _onchange_issuer_company(self):
        self.issuer_warehouse = False
        domain = {}
        if self.issuer_company:
            return {
                'domain': {
                'issuer_warehouse': [('branch_id', '=', self. issuer_company.id)]
                }
            }
        else:
            domain['issuer_warehouse'] = []
        return {'domain': domain}
    def action_submit(self):
        self.ensure_one()
        print("company",self.company_id.name)
        flow = self.env['approval.flow'].search([
            ('request_model_id.model', '=', 'issue.requests'),
            ('active', '=', True),
            ('company_id', '=', self.company_id.id)
        ], limit=1)
        if not flow:
            raise UserError("No approval flow defined for Internal Issue Request!")

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
            'branch_id': self.requester_branch_id.id,
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

    def action_approve(self, comment=''):
        self.ensure_one()
        if not self.approval_request_id:
            raise UserError("No approval flow defined for Internal Issue Request!.")
        self.approval_request_id.with_context(action_type='approve', comment=comment).process_action()
        self._sync_state_from_approval()
    def action_reject(self, comment=''):
        self.ensure_one()
        if not self.approval_request_id:
            raise UserError("No approval request linked to this MRCV.")
        self.approval_request_id.with_context(action_type='reject', comment=comment).process_action()
        self._sync_state_from_approval()

    def action_amend(self, comment=''):
        self.ensure_one()
        if not self.approval_request_id:
            raise UserError("No approval request linked to this inter store transfer.")
        self.approval_request_id.with_context(action_type='pending', comment=comment).process_action()
        self._sync_state_from_approval()

    def action_revert(self, comment=''):
        self.ensure_one()
        if not self.approval_request_id:
            raise UserError("No approval request linked to this inter store transfer.")
        self.approval_request_id.with_context(action_type='pending', comment=comment).process_action()
        self._sync_state_from_approval()

    def action_resubmit(self, comment=''):
        self.ensure_one()
        if not self.approval_request_id:
            raise UserError("No approval request linked to this inter store transfer.")
        self.approval_request_id.with_context(action_type='pending', comment=comment).process_action()
        self._sync_state_from_approval()

    def _sync_state_from_approval(self):
        if not self.approval_request_id:
            return
        status = self.approval_request_id.status
        print("status",status)
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

    def _create_feeding_transfer(self):
        """Create delivery order for internal issue, sending products to a dedicated virtual location."""
        self.ensure_one()
        # Validate there are requested items
        if not self.items_requested:
            raise UserError("No items found to create a delivery order.")

        # Validate issuer warehouse
        if not self.issuer_warehouse or not self.issuer_warehouse.lot_stock_id:
            raise UserError("Issuer warehouse or its stock location is not properly configured.")

        picking_type = self.env['stock.picking.type'].sudo().search([
            ('code', '=', 'internal_issue'),
            ('warehouse_id', '=', self.issuer_warehouse.id)
        ], limit=1)

        # If not found, create a new exhibition picking type for this warehouse
        if not picking_type:
            # print(self.env['stock.picking.type'].fields_get()['code']['selection'])
            picking_type = self.env['stock.picking.type'].sudo().create({
                'name': f'Internal Issue Operation - {self.issuer_warehouse.name}',
                'code': 'internal_issue',
                'sequence_code': 'ISSUEREQ',
                'warehouse_id': self.issuer_warehouse.id,
                'company_id': self.company_id.id,
            })
            _logger.info(
                "New Exhibition Picking Type created for warehouse %s: %s",
                self.issuer_warehouse.name,
                picking_type.name
            )

        picking_type.write({
            'new_count_exhibition_issue': picking_type.new_count_exhibition_issue + 1
        })


        destination_location = self.env['stock.location'].search([
            ('usage', '=', 'transit'),
            ('name', '=', 'Internal Issue')
        ], limit=1)
        if not destination_location:
            destination_location = self.env['stock.location'].create({
                'name': 'Internal Issue',
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
                for line in self.items_requested
            ],
        })
        picking.action_confirm()
        self.feeding_picking_id = picking
        _logger.info("Internal Issue delivery order created: %s", picking.name)

    def _compute_step_progress(self):
        for rec in self:
            rec.step_progress = rec.approval_request_id.step_progress if rec.approval_request_id else "<span>No approval steps yet.</span>"