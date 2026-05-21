from odoo import models, fields, api
from odoo.exceptions import UserError
from collections import defaultdict

class ResPartner(models.Model):
    _inherit = 'res.partner'

    def action_create_workshop_job(self):
        """Open a new workshop order form with this customer pre-filled."""
        return {
            'name': 'New Workshop Job',
            'type': 'ir.actions.act_window',
            'res_model': 'workshop.order',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_customer_id': self.id,
            }
        }

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    workshop_order_id = fields.Many2one(
        'workshop.order',
        string="Source Job Order",
        copy=False
    )

    def action_confirm(self):
        """Prevent confirmation if the related Workshop Job is not closed."""
        for order in self:
            if order.workshop_order_id and order.workshop_order_id.status != 'closed':
                raise UserError(
                    "You cannot confirm this quotation because the related Workshop Job (%s) is not yet closed. "
                    "Please close the job in the Workshop module first." % order.workshop_order_id.name
                )
        return super(SaleOrder, self).action_confirm()

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    is_workshop_line = fields.Boolean("From Workshop", default=False, readonly=True)

    def _action_launch_stock_rule(self, **kwargs):
        """Skip delivery creation for orders originating from Workshop Jobs."""
        if self.order_id.workshop_order_id:
            return True
        return super(SaleOrderLine, self)._action_launch_stock_rule(**kwargs)

    def unlink(self):
        """Prevent manual deletion of lines sourced from Workshop MRCVs."""
        for line in self:
            if line.is_workshop_line and not self._context.get('force_workshop_sync'):
                raise UserError(
                    "You cannot manually delete the product '%s' because it was synchronized from a Workshop Job. "
                    "Please update the materials in the Workshop module if changes are needed." % line.product_id.name
                )
        return super(SaleOrderLine, self).unlink()

class WorkshopModel(models.Model):
    _name = 'workshop.model'
    _description = 'Vehicle Model'
    category_id = fields.Many2one('workshop.vehicle.category', string="Category")
    name = fields.Char(string="Model Name", required=True)
    manufacturer = fields.Char(string="Manufacturer")
    description = fields.Text(string="Description")
    company_id = fields.Many2one('res.company', string="Company", default=lambda self: self.env.company)
    branch_id = fields.Many2one(
        'account.analytic.account',
         string='Branch'
    )
class WorkshopVehicle(models.Model):
    _name = 'workshop.vehicle'
    _description = 'Customer Vehicle'

    name = fields.Char(string="Plate Number")
    category_id = fields.Many2one(
        'workshop.vehicle.category',
        string="Vehicle Category"
    )
    chassis_number = fields.Char("Chassis Number")
    model_id = fields.Many2one('workshop.model', string="Model", ondelete='set null')
    make_id = fields.Many2one('workshop.vehicle.make', string="Vehicle Make")
    customer_id = fields.Many2one('res.partner', string="Customer", ondelete='set null')
    image = fields.Binary("Vehicle Photo")
    company_id = fields.Many2one('res.company', string="Company", default=lambda self: self.env.company)
    branch_id = fields.Many2one(
        'account.analytic.account',
        string='Branch'
    )

    # Engine Information
    engine_make = fields.Char(string="Engine Make")
    engine_model = fields.Char(string="Engine Model")
    engine_serial = fields.Char(string="Engine Serial Number")

    # Mounted Equipment Information
    mounted_type = fields.Char(string="Mounted Equipment Type")
    mounted_make = fields.Char(string="Mounted Make")
    mounted_model = fields.Char(string="Mounted Model")
    mounted_serial = fields.Char(string="Mounted Serial Number")

class WorkshopOrder(models.Model):
    _name = 'workshop.order'
    _description = 'Workshop Job Order'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    name = fields.Char(default="New", required=True,tracking=True)
    customer_id = fields.Many2one('res.partner', string="Customer",tracking=True)
    vehicle_id = fields.Many2one('workshop.vehicle', string="Vehicle",tracking=True)
    job_open_date = fields.Date(string="Job Open Date")
    job_close_date = fields.Date(string="Job Close Date")
    vehicle_driver_name = fields.Char("Driver Name",tracking=True)
    vehicle_driver_phone = fields.Char("Driver Phone",tracking=True)
    description = fields.Text("Work Description",tracking=True)
    reading_km = fields.Integer("Odometer",tracking=True)
    hours = fields.Float("Labour Hours",tracking=True)
    hourly_rate = fields.Float("Hourly Rate", default=0.0, tracking=True)
    service_charges = fields.Float("Service Charges", default=0.0, tracking=True)
    material_total = fields.Float(string="Material Total", compute="_compute_bill_totals")
    total_bill = fields.Float(string="Total Bill", compute="_compute_bill_totals", tracking=True)
    @api.onchange('vehicle_id')
    def _onchange_vehicle_id(self):
        """Auto-fill engine and equipment details from the selected vehicle."""
        if self.vehicle_id:
            self.engine_make = self.vehicle_id.engine_make
            self.engine_model = self.vehicle_id.engine_model
            self.engine_serial = self.vehicle_id.engine_serial
            self.mounted_type = self.vehicle_id.mounted_type
            self.mounted_make = self.vehicle_id.mounted_make
            self.mounted_model = self.vehicle_id.mounted_model
            self.mounted_serial = self.vehicle_id.mounted_serial

    @api.onchange('customer_id')
    def _onchange_customer_id(self):
        """Clear vehicle if customer changes and doesn't match."""
        if self.customer_id and self.vehicle_id and self.vehicle_id.customer_id != self.customer_id:
            self.vehicle_id = False

    fuel_in_tank = fields.Float(string="Fuel in Tank", help="Fuel percentage",tracking=True)
    engine_make = fields.Char(string="Engine Make", required=True,tracking=True)
    engine_model = fields.Char(string="Engine Model", required=True,tracking=True)
    engine_serial = fields.Char(string="Engine Serial Number", required=True,tracking=True)
    mounted_type = fields.Char(string="Mounted Equipment Type", required=True,tracking=True)
    mounted_make = fields.Char(string="Mounted Make", required=True,tracking=True)
    mounted_model = fields.Char(string="Mounted Model", required=True,tracking=True)
    mounted_serial = fields.Char(string="Mounted Serial Number", required=True,tracking=True)
    missing_parts = fields.Text(string="Missed or Damaged Parts", required=True,tracking=True)
    remark = fields.Text(string="Remark",tracking=True)
    @api.onchange('vehicle_id')
    def _onchange_vehicle_id(self):
        """Auto-fill engine and equipment details from the selected vehicle."""
        if self.vehicle_id:
            self.engine_make = self.vehicle_id.engine_make
            self.engine_model = self.vehicle_id.engine_model
            self.engine_serial = self.vehicle_id.engine_serial
            self.mounted_type = self.vehicle_id.mounted_type
            self.mounted_make = self.vehicle_id.mounted_make
            self.mounted_model = self.vehicle_id.mounted_model
            self.mounted_serial = self.vehicle_id.mounted_serial

    @api.onchange('customer_id')
    def _onchange_customer_id(self):
        """Clear vehicle if customer changes and doesn't match."""
        if self.customer_id and self.vehicle_id and self.vehicle_id.customer_id != self.customer_id:
            self.vehicle_id = False

    type_work = fields.Selection([
        ('internal_work', 'Internal Work'),
        ('external_work', 'External Work')
    ], string="Type of Work",tracking=True)
    status = fields.Selection([
        ('created', 'Created'),
        ('checked_in', 'Checked In by Customer Service'),
        ('inspected', 'Inspected'),
        ('approved', 'Approved for Work'),
        ('assigned', 'Assigned to Technical Section'),
        ('working', 'Work In Progress'),
        ('quality_check', 'Quality Check'),
        ('ready_for_delivery', 'Ready For Delivery'),
        ('delivered', 'Delivered'),
        ('invoiced', 'Invoiced'),
        ('closed', 'Closed')

    ], default='created',tracking=True)
    task_ids = fields.One2many(
        'workshop.task', 'job_id', string="Tasks"
    )
    company_id = fields.Many2one('res.company', string="Company", default=lambda self: self.env.company)
    branch_id = fields.Many2one(
        'account.analytic.account',
        string='Branch',
        domain=[('plan_id', '=', 'Branch')],
        default=lambda self: self.env.user.default_branch_id
    )
    accessory_line_ids = fields.One2many(
        'workshop.job.accessory.line',
        'job_order_id',
        string="Accessories"
    )
    image_ids = fields.One2many(
        'workshop.order.image', 'job_order_id', string="Pictures"
    )
    mrcv_ids = fields.One2many(
        'mrcv.header',
        'workshop_order_id',
        string="MRCVs"

    )
    opened_count = fields.Integer(
        string="Opened Jobs",
        compute="_compute_opened_closed_counts",
        store=True
    )

    closed_count = fields.Integer(
        string="Closed Jobs",
        compute="_compute_opened_closed_counts",
        store=True
    )
    sale_order_id = fields.Many2one(
        'sale.order',
        string="Related Sale Order",
        compute="_compute_sale_order_id",
        help="The most recent Sale Order linked to this job."
    )

    @api.depends('mrcv_ids.state', 'mrcv_ids.line_ids.issued_qty', 'hours', 'hourly_rate', 'service_charges')
    def _compute_bill_totals(self):
        for rec in self:
            mat_sum = 0.0
            for mrcv in rec.mrcv_ids:
                if mrcv.state == 'issued':
                    for line in mrcv.line_ids:
                        mat_sum += line.issued_qty * line.product_id.list_price
            
            rec.material_total = mat_sum
            rec.total_bill = mat_sum + (rec.hours * rec.hourly_rate) + rec.service_charges

    def _compute_sale_order_id(self):
        for rec in self:
            so = self.env['sale.order'].search([('workshop_order_id', '=', rec.id)], limit=1, order='create_date desc')
            rec.sale_order_id = so.id

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                # Generate base sequence e.g., JO-2600001
                seq_val = self.env['ir.sequence'].next_by_code('workshop.order') or 'JO-000001'
                
                branch_id = vals.get('branch_id')
                branch = self.env['account.analytic.account'].browse(branch_id) if branch_id else self.env.user.default_branch_id
                b_code = (branch.branch_code or branch.code or branch.name[:2] or 'HQ').upper()
                
                # Format to JOB-YYBranchCodeCounter
                if seq_val.startswith('JO-'):
                    year_prefix = seq_val[3:5] if len(seq_val) > 4 else '00'
                    counter = seq_val[5:] if len(seq_val) > 4 else seq_val
                    vals['name'] = f"JOB-{year_prefix}{b_code}{counter}"
                else:
                    vals['name'] = seq_val
                    
        return super(WorkshopOrder, self).create(vals_list)

    def action_validate_and_close_job(self):
        for rec in self:
            open_mrcvs = rec.mrcv_ids.filtered(lambda m: m.state not in ('approved', 'issued', 'rejected', 'done'))
            if open_mrcvs:
                raise UserError(f"Cannot close job. Uncompleted MRCVs found: {', '.join(open_mrcvs.mapped('name'))}")
            
            mrvs = self.env['mrv.header'].search([('job_id', '=', rec.id)])
            open_mrvs = mrvs.filtered(lambda m: m.state not in ('approved', 'rejected', 'done'))
            if open_mrvs:
                raise UserError(f"Cannot close job. Uncompleted MRVs found: {', '.join(open_mrvs.mapped('name'))}")
            
            rec.status = 'closed'
            rec.job_close_date = fields.Date.today()

    def action_create_quotation_from_mrcv(self):
        self.ensure_one()

        # --- Collect all approved/issued MRCVs for this job
        mrcvs = self.mrcv_ids.filtered(lambda m: m.state in ('approved', 'issued'))
        
        # --- Calculate required quantities from MRCVs
        product_qtys = defaultdict(float)
        for mrcv in mrcvs:
            for mrcv_line in mrcv.line_ids.filtered(lambda l: l.quantity > 0):
                # Calculate quantity already delivered via MRVs
                delivered_qty = sum(
                    mrv_line.quantity for mrv_line in self.env['mrv.line'].search([
                        ('mrcv_line_id', '=', mrcv_line.id)
                    ])
                )
                remaining_qty = mrcv_line.quantity - delivered_qty
                if remaining_qty > 0:
                    product_qtys[mrcv_line.product_id] += remaining_qty

        # --- Check if a sale order already exists
        if self.sale_order_id and self.sale_order_id.exists():
            sale_order = self.sale_order_id
            if sale_order.state not in ['draft', 'sent']:
                raise UserError("Cannot update Quotation because it is already confirmed in Sales.")
            
            if self.status == 'closed':
                # --- FINAL SYNC: Remove ONLY workshop lines and replace with latest MRCV products
                sale_order.with_context(force_workshop_sync=True).order_line.filtered(lambda l: l.is_workshop_line).unlink()
                for product, qty in product_qtys.items():
                    sale_order.write({'order_line': [(0, 0, {
                        'product_id': product.id,
                        'product_uom_qty': qty,
                        'is_workshop_line': True,
                    })]})
            else:
                # --- MID-JOB UPDATE: Just update/add lines, preserve manually added ones
                for product, qty in product_qtys.items():
                    existing_line = sale_order.order_line.filtered(lambda l: l.product_id == product and l.is_workshop_line)
                    if existing_line:
                        existing_line[0].product_uom_qty = qty
                    else:
                        sale_order.write({'order_line': [(0, 0, {
                            'product_id': product.id,
                            'product_uom_qty': qty,
                            'is_workshop_line': True,
                        })]})
            
            return self.action_view_sale_order()

        # --- Redirect to a NEW Sale Order if none exists
        # This avoid "empty SO" validation errors.
        context = {
            'default_partner_id': self.customer_id.id,
            'default_company_id': self.company_id.id,
            'default_origin': self.name,
            'default_workshop_order_id': self.id,
        }
        
        # Add dynamic fields if they exist in SO
        so_fields = self.env['sale.order']._fields
        if 'branch_id' in so_fields:
            context['default_branch_id'] = self.branch_id.id
        if 'job_number' in so_fields:
            context['default_job_number'] = self.name
        if 'plate_number' in so_fields:
            context['default_plate_number'] = self.vehicle_id.name

        # Include initial products in context as default lines
        if product_qtys:
            line_vals = []
            for product, qty in product_qtys.items():
                line_vals.append((0, 0, {
                    'product_id': product.id,
                    'product_uom_qty': qty,
                    'is_workshop_line': True,
                }))
            context['default_order_line'] = line_vals

        return {
            'name': 'New Quotation',
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'view_mode': 'form',
            'target': 'current',
            'context': context,
        }

    def action_view_sale_order(self):
        """Open the related Sale Order."""
        self.ensure_one()
        if not self.sale_order_id:
            raise UserError("No Sales Order linked to this Job.")
        return {
            'name': 'Sale Order',
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'view_mode': 'form',
            'res_id': self.sale_order_id.id,
            'target': 'current',
        }

    @api.depends('job_open_date', 'job_close_date')
    def _compute_opened_closed_counts(self):
        for rec in self:
            rec.opened_count = 1 if rec.job_open_date else 0
            rec.closed_count = 1 if rec.job_close_date else 0

    def action_load_accessories(self):
        """Load accessories matching vehicle category OR category 'Common'"""
        for order in self:
            # Ensure the order is saved
            if not order.id:
                raise UserError("You must save the Job Order before loading accessories.")

            # Clear existing accessory lines
            order.accessory_line_ids.unlink()

            # Search accessories
            accessories = self.env['workshop.accessory'].search([
                '|',
                ('categories', '=', order.vehicle_id.category_id.id),
                ('categories.name', '=', 'common')
            ])

            # Create accessory lines properly
            for acc in accessories:
                self.env['workshop.job.accessory.line'].create({
                    'job_order_id': order.id,
                    'accessory_id': acc.id
                })

    def action_open_mrcv(self):
        """Open MRCV form view with pre-filled data"""
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': 'Create MRCV',
            'res_model': 'mrcv.header',
            'view_mode': 'form',
            'view_id': self.env.ref('hagbes_workshop_management.view_mrcv_header_form').id,
            'target': 'current',  # open in the same tab, use 'new' for popup
            'context': {
                'default_workshop_order_id': self.id,
                'default_partner_id': self.customer_id.id,
                'requester_branch_id':self.branch_id.id,
            }
        }


class WorkshopOrderImage(models.Model):
    _name = "workshop.order.image"
    _description = "Job Order Image"

    job_order_id = fields.Many2one(
        'workshop.order', string="Job Order", ondelete='cascade'
    )
    name = fields.Char(string="Description")
    image = fields.Binary(string="Image", attachment=True)

    def action_open_image_tab(self):
        self.ensure_one()
        url = f"/web/content/{self._name}/{self.id}/image/filename.png?download=false"
        return {
            'type': 'ir.actions.act_url',
            'url': url,
            'target': 'new',  # opens in a new browser tab
        }

class JobOrderAccessoryLine(models.Model):
    _name = "workshop.job.accessory.line"
    _description = "Job Order Accessory Line"

    job_order_id = fields.Many2one(
        'workshop.order',
        string="Job Order",
        ondelete='cascade'
    )
    accessory_id = fields.Many2one(
        'workshop.accessory',
        string="Accessory",
        required=True
    )
    ok = fields.Boolean(string="OK")
    not_ok = fields.Boolean(string="Not OK")
    not_available = fields.Boolean(string="Not Available")
    remark = fields.Char(string="Remark")
    status = fields.Selection([
        ('ok', 'OK'),
        ('not_ok', 'Not OK'),
        ('not_available', 'Not Available'),
    ], string="Status")

    @api.onchange('ok', 'not_ok', 'not_available')
    def _onchange_status(self):
        # only act on a single record (onchange runs on the current record)
        if not self:
            return
        # If user sets one to True, force others to False.
        # We test each in order because the client may flip values in ways that
        # cause multiple fields to be True before onchange runs.
        if self.ok:
            self.not_ok = False
            self.not_available = False
            return
        if self.not_ok:
            self.ok = False
            self.not_available = False
            return
        if self.not_available:
            self.ok = False
            self.not_ok = False
            return
class WorkshopTask(models.Model):
    _name = 'workshop.task'
    _description = 'Workshop Task'

    job_id = fields.Many2one('workshop.order', string="Job Order",ondelete='set null')
    description = fields.Char("Task Description")

    technician_id = fields.Many2one('hr.employee', string="Technician", ondelete='set null', required=False)
    section_id = fields.Many2one('hr.department', string="Section",ondelete='set null')
    status = fields.Selection([
        ('created', 'Created'),
        ('assigned', 'Assigned'),
        ('done', 'Done')
    ], default='created')
    branch_id = fields.Many2one(
        'account.analytic.account',
        string='Branch'
    )
    company_id = fields.Many2one('res.company', string="Company", default=lambda self: self.env.company)

class VehicleCategory(models.Model):
    _name = "workshop.vehicle.category"
    _description = "Vehicle Category"

    name = fields.Char(string="Category Name", required=True)
    type= fields.Many2one('workshop.vehicle.category.type',string="Category Type")
    branch_id = fields.Many2one(
        'account.analytic.account',
        string='Branch'
    )
    company_id = fields.Many2one('res.company', string="Company", default=lambda self: self.env.company)
class VehicleCategoryType(models.Model):
    _name = "workshop.vehicle.category.type"
    _description = "Vehicle Category"

    name = fields.Char(string="Category Name", required=True)
    branch_id = fields.Many2one(
        'account.analytic.account',
        string='Branch'
    )
    company_id = fields.Many2one('res.company', string="Company", default=lambda self: self.env.company)

class VehicleMake(models.Model):
    _name = "workshop.vehicle.make"
    _description = "Vehicle Make"

    name = fields.Char(string="Make Name", required=True)
    branch_id = fields.Many2one(
        'account.analytic.account',
        string='Branch'
    )
    company_id = fields.Many2one('res.company', string="Company", default=lambda self: self.env.company)

class WorkshopAccessory(models.Model):
    _name = "workshop.accessory"
    _description = "Workshop Accessory"

    name = fields.Char(string="Accessory Name", required=True)
    accessory_type = fields.Selection([('Interior','Interior'),('Exterior','Exterior'),('Road Test','Road Test')], string="Type")
    categories = fields.Many2one(
        'workshop.vehicle.category',
        string='Category',
        ondelete='cascade'
    )
    branch_id = fields.Many2one(
        'account.analytic.account',
         string='Branch'
    )
    company_id = fields.Many2one('res.company', string="Company", default=lambda self: self.env.company)


