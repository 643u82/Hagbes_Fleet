# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import AccessError, ValidationError, UserError
import logging

_logger = logging.getLogger(__name__)


class FleetRequisition(models.Model):
    """
    FIXED Fleet Requisition Model - Corrected group references
    
    Fixes: Changed group_fleet_operator to group_fmo (actual group name)
    """
    
    _name = 'fleet.requisition'
    _description = 'Vehicle Requisition Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_of_request desc, id desc'

    # ─── Core Identification ─────────────────────────────────────────────────────
    name = fields.Char(
        string='Reference',
        required=True,
        readonly=True,
        default='New',
        index=True,
    )
    date_of_request = fields.Datetime(
        string='Request Date',
        required=True,
        default=fields.Datetime.now,
        tracking=True,
    )

    # ─── Request Details (PURE business data) ─────────────────────────────────────
    request_by = fields.Many2one(
        'res.users',
        string='Requested By',
        required=True,
        tracking=True,
        help='User who created this requisition'
    )
    department_id = fields.Many2one(
        'hr.department',
        string='Department',
        required=True,
        tracking=True,
        help='Department making the request'
    )
    purpose = fields.Text(
        string='Purpose',
        required=True,
        tracking=True,
        help='Purpose of the vehicle request'
    )
    destination = fields.Char(
        string='Destination',
        required=True,
        tracking=True,
        help='Travel destination'
    )
    date_from = fields.Datetime(
        string='Start Date',
        required=True,
        tracking=True,
        help='Trip start date and time'
    )
    date_to = fields.Datetime(
        string='End Date',
        required=True,
        tracking=True,
        help='Trip end date and time'
    )
    traveller_names = fields.Char(
        string='Traveller Names',
        tracking=True,
        help='Names of all travellers'
    )
    traveller_count = fields.Integer(
        string='Number of Travellers',
        default=1,
        tracking=True,
    )
    notes = fields.Text(
        string='Additional Notes',
        tracking=True,
        help='Any additional information or requirements'
    )

    # ─── Approval Workflow (PURE business approval states) ───────────────────────
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True, copy=False)

    # ─── Approval Tracking ─────────────────────────────────────────────────────
    approved_by = fields.Many2one(
        'res.users',
        string='Approved By',
        readonly=True,
        copy=False,
        help='Department Manager who approved this requisition'
    )
    approved_date = fields.Datetime(
        string='Approval Date',
        readonly=True,
        copy=False,
        help='Date when requisition was approved'
    )
    rejection_reason = fields.Text(
        string='Rejection Reason',
        readonly=True,
        copy=False,
        help='Reason for rejecting this requisition'
    )
    rejected_by = fields.Many2one(
        'res.users',
        string='Rejected By',
        readonly=True,
        copy=False,
        help='User who rejected this requisition'
    )
    rejected_date = fields.Datetime(
        string='Rejection Date',
        readonly=True,
        copy=False,
        help='Date when requisition was rejected'
    )

    # ─── Execution Bridge (link to execution layer) ───────────────────────────────
    trip_ids = fields.One2many(
        'fleet.trip',
        'requisition_id',
        string='Related Trips',
        help='Trips created from this requisition'
    )
    has_trip = fields.Boolean(
        string='Has Trip',
        compute='_compute_has_trip',
        store=True,
        help='Whether this requisition has an associated trip'
    )

    @api.depends('trip_ids')
    def _compute_has_trip(self):
        for requisition in self:
            requisition.has_trip = bool(requisition.trip_ids)

    # ─── Permission Fields (Computed) ─────────────────────────────────────────────
    can_submit = fields.Boolean(
        compute='_compute_permissions',
        help='Whether user can submit this requisition'
    )
    can_approve = fields.Boolean(
        compute='_compute_permissions',
        help='Whether user can approve this requisition'
    )
    can_reject = fields.Boolean(
        compute='_compute_permissions',
        help='Whether user can reject this requisition'
    )
    can_cancel = fields.Boolean(
        compute='_compute_permissions',
        help='Whether user can cancel this requisition'
    )
    can_edit = fields.Boolean(
        compute='_compute_permissions',
        help='Whether user can edit this requisition'
    )

    @api.depends('state', 'request_by')
    @api.depends_context('uid')
    def _compute_permissions(self):
        """Compute user permissions based on state and role"""
        user = self.env.user
        is_requester = user == self.request_by
        is_dept_manager = user.has_group('hagbes_fleet.group_dept_manager')
        is_admin = user.has_group('hagbes_fleet.group_fleet_admin') or user.has_group('base.group_system')
        
        for requisition in self:
            # Requester permissions
            requisition.can_submit = requisition.state == 'draft' and (is_requester or is_admin)
            requisition.can_cancel = requisition.state in ['draft', 'submitted'] and (is_requester or is_admin)
            requisition.can_edit = requisition.state == 'draft' and (is_requester or is_admin)
            
            # Department Manager permissions
            requisition.can_approve = requisition.state == 'submitted' and (is_dept_manager or is_admin)
            requisition.can_reject = requisition.state == 'submitted' and (is_dept_manager or is_admin)

    # ─── Default Methods ───────────────────────────────────────────────────────
    @api.model
    def create(self, vals):
        """Create requisition with automatic reference and user assignment"""
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('fleet.requisition') or 'New'
        
        # Auto-assign requester if not specified
        if not vals.get('request_by'):
            vals['request_by'] = self.env.user.id
        
        # Auto-assign department from requester
        if vals.get('request_by') and not vals.get('department_id'):
            employee = self.env['hr.employee'].search([('user_id', '=', vals['request_by'])], limit=1)
            if employee and employee.department_id:
                vals['department_id'] = employee.department_id.id
        
        return super().create(vals)

    # ─── Constraints ─────────────────────────────────────────────────────────--
    @api.constrains('date_from', 'date_to')
    def _check_date_logic(self):
        """Validate date logic"""
        for requisition in self:
            if requisition.date_from and requisition.date_to:
                if requisition.date_from >= requisition.date_to:
                    raise ValidationError(_('Start date must be before end date'))
                
                if requisition.date_from < fields.Datetime.now():
                    raise ValidationError(_('Start date cannot be in the past'))

    @api.constrains('traveller_count')
    def _check_traveller_count(self):
        """Validate traveller count"""
        for requisition in self:
            if requisition.traveller_count <= 0:
                raise ValidationError(_('Number of travellers must be greater than 0'))

    # ─── Business Logic Methods (PURE business workflow) ───────────────────────
    def action_submit(self):
        """Submit requisition for approval"""
        self.ensure_one()
        
        # State validation
        if self.state != 'draft':
            raise ValidationError(_('Only draft requisitions can be submitted'))
        
        # Permission validation
        if not self.can_submit:
            raise AccessError(_('You do not have permission to submit this requisition'))
        
        # Perform submission
        self.write({'state': 'submitted'})
        
        # Send notification to department manager
        if self.department_id.manager_id:
            self.message_post(
                body=_('Requisition submitted for approval'),
                partner_ids=[self.department_id.manager_id.user_id.partner_id.id]
            )
        else:
            self.message_post(body=_('Requisition submitted for approval'))
        
        # Log activity
        self.message_post(body=_('Requisition submitted by %s') % self.env.user.name)

    def action_approve(self):
        """Approve requisition and create trip"""
        self.ensure_one()
        
        # State validation
        if self.state != 'submitted':
            raise ValidationError(_('Only submitted requisitions can be approved'))
        
        # Permission validation
        if not self.can_approve:
            raise AccessError(_('You do not have permission to approve this requisition'))
        
        # Perform approval
        self.write({
            'state': 'approved',
            'approved_by': self.env.user.id,
            'approved_date': fields.Datetime.now(),
        })
        
        # Create trip for execution
        self._create_trip()
        
        # Log activity
        self.message_post(body=_('Requisition approved by %s') % self.env.user.name)

    def action_reject(self, reason=None):
        """Reject requisition with reason"""
        self.ensure_one()
        
        # State validation
        if self.state != 'submitted':
            raise ValidationError(_('Only submitted requisitions can be rejected'))
        
        # Permission validation
        if not self.can_reject:
            raise AccessError(_('You do not have permission to reject this requisition'))
        
        # Reason validation
        if not reason or not reason.strip():
            raise ValidationError(_('Rejection reason is required'))
        
        if len(reason.strip()) < 10:
            raise ValidationError(_('Please provide a more detailed rejection reason (minimum 10 characters)'))
        
        # Perform rejection
        self.write({
            'state': 'rejected',
            'rejected_by': self.env.user.id,
            'rejected_date': fields.Datetime.now(),
            'rejection_reason': reason.strip(),
        })
        
        # Log activity
        rejection_msg = _(
            'Requisition rejected by %s\nReason: %s'
        ) % (self.env.user.name, reason.strip())
        self.message_post(body=rejection_msg)

    def action_cancel(self):
        """Cancel requisition"""
        self.ensure_one()
        
        # State validation
        if self.state in ['approved', 'completed']:
            raise ValidationError(_('Cannot cancel approved requisitions'))
        
        # Permission validation
        if not self.can_cancel:
            raise AccessError(_('You do not have permission to cancel this requisition'))
        
        # Check if trip exists and is active
        if self.trip_ids.filtered(lambda t: t.state in ['assigned', 'active']):
            raise ValidationError(_('Cannot cancel requisition with active trips'))
        
        # Perform cancellation
        self.write({'state': 'cancelled'})
        
        # Cancel associated trips
        self.trip_ids.filtered(lambda t: t.state not in ['completed']).action_cancel()
        
        # Log activity
        self.message_post(body=_('Requisition cancelled by %s') % self.env.user.name)

    # ─── Bridge Methods (to execution layer) ───────────────────────────────────────
    def _create_trip(self):
        """Create trip record for execution (bridge to execution layer)"""
        self.ensure_one()
        
        # Check if trip already exists
        if self.trip_ids:
            existing_trip = self.trip_ids[0]
            if existing_trip.state in ['planned', 'assigned', 'active']:
                raise ValidationError(_('Trip already exists for this requisition'))
        
        # Create trip record
        trip_vals = {
            'requisition_id': self.id,
            'purpose': self.purpose,
            'destination': self.destination,
            'date_from': self.date_from,
            'date_to': self.date_to,
            'company_id': self.company_id.id if hasattr(self, 'company_id') else self.env.company.id,
        }
        
        trip = self.env['fleet.trip'].create(trip_vals)
        
        return trip

    # ─── Helper Methods ───────────────────────────────────────────────────────
    def get_requisition_summary(self):
        """Get requisition summary for reporting"""
        self.ensure_one()
        return {
            'name': self.name,
            'requester': self.request_by.name,
            'department': self.department_id.name,
            'purpose': self.purpose,
            'destination': self.destination,
            'date_from': self.date_from,
            'date_to': self.date_to,
            'state': self.state,
            'has_trip': self.has_trip,
            'trip_count': len(self.trip_ids),
            'approved_by': self.approved_by.name if self.approved_by else None,
            'approved_date': self.approved_date,
        }

    @api.model
    def get_user_requisitions(self):
        """Get requisitions accessible to current user"""
        domain = []
        
        # Requesters see their own requisitions
        if self.env.user.has_group('hagbes_fleet.group_fleet_requester'):
            domain.append(('request_by', '=', self.env.user.id))
        
        # Department managers see department requisitions
        elif self.env.user.has_group('hagbes_fleet.group_dept_manager'):
            employee = self.env['hr.employee'].search([('user_id', '=', self.env.user.id)], limit=1)
            if employee and employee.department_id:
                domain.append(('department_id', '=', employee.department_id.id))
        
        # FIXED: Use correct group reference
        # Fleet operators see all approved requisitions
        elif self.env.user.has_group('hagbes_fleet.group_fmo'):
            domain.append(('state', 'in', ['approved', 'completed']))
        
        return self.search(domain)
