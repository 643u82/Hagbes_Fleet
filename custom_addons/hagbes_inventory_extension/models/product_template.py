# models/product_template.py
from odoo import models, fields,api
from odoo.exceptions import ValidationError

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    default_code = fields.Char(
        string='Part Number',
        required=True,
        copy=False
    )

    # 2️⃣ Enforce uniqueness at DB level
    _sql_constraints = [
        (
            'default_code_unique',
            'unique(default_code)',
            'Part Number must be unique.'
        )
    ]

    # 3️⃣ Prevent editing Part Number after creation (backend)
    def write(self, vals):
        if 'default_code' in vals:
            for rec in self:
                if rec.default_code:
                    raise ValidationError(
                        "Part Number cannot be changed after the product is created."
                    )
        return super().write(vals)

    interchangeable_number_ids = fields.One2many(
        'product.interchange',
        'product_id',
        string="Interchangeable Numbers"
    )
    interchangeable_numbers_text = fields.Char(
        string="Interchangeable Numbers",
        compute='_compute_interchangeable_numbers_text',
        store=False
    )

    @api.depends('interchangeable_number_ids.name')
    def _compute_interchangeable_numbers_text(self):
        for product in self:
            product.interchangeable_numbers_text = ', '.join(
                product.interchangeable_number_ids.mapped('name')
            )

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        help="Company that owns this product",
    )

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        args = args or []
        print(args,"args")
        # 1️⃣ Normal search (name, default_code, etc.)
        res = super().name_search(name=name, args=args, operator=operator, limit=limit)

        if name:
            # 2️⃣ Search products via interchangeable numbers
            interchange_products = self.env['product.interchange'].search([
                ('name', operator, name)
            ]).mapped('product_id')

            if interchange_products:
                # 3️⃣ Add products to results while respecting original domain
                additional = super().name_search(
                    name='',
                    args=[('id', 'in', interchange_products.ids)] + args,
                    operator=operator,
                    limit=limit
                )
                res += additional

        # 4️⃣ Remove duplicates
        seen = set()
        final_res = []
        for r in res:
            if r[0] not in seen:
                final_res.append(r)
                seen.add(r[0])

        return final_res

class ProductInterchange(models.Model):
    _name = 'product.interchange'
    _description = 'Product Interchange'
    _rec_name = 'name'

    name = fields.Char(string="Interchange Number", required=True)
    product_id = fields.Many2one('product.template', string="Product", ondelete='restrict')

    _sql_constraints = [
        ('unique_interchange_name', 'unique(name)', 'Interchange number must be unique!')
    ]

    @api.model
    def create(self, vals):
        # If creating a new interchange for a product, make sure name isn't assigned elsewhere
        name = vals.get('name')
        new_pid = vals.get('product_id')
        if name:
            existing = self.search([('name', '=', name)], limit=1)
            if existing:
                # existing record with same name exists
                if existing.product_id and new_pid and existing.product_id.id != int(new_pid):
                    raise ValidationError(
                        "Interchange number '%s' is already assigned to product '%s' and cannot be reassigned."
                        % (name, existing.product_id.display_name)
                    )
        return super().create(vals)

    def write(self, vals):
        # Prevent changing product_id from one product to a different product
        if 'product_id' in vals:
            for rec in self:
                new_pid = vals.get('product_id')
                # If current record already assigned and new_pid is different => block
                if rec.product_id and new_pid and rec.product_id.id != int(new_pid):
                    raise ValidationError(
                        "Interchange number '%s' is already assigned to product '%s' and cannot be reassigned."
                        % (rec.name, rec.product_id.display_name)
                    )
        return super().write(vals)

    @api.constrains('name', 'product_id')
    def _check_unique_assignment(self):
        # Defensive check when saving: ensure no other record with same name is assigned to different product
        for rec in self:
            if not rec.name:
                continue
            existing = self.search([('name', '=', rec.name), ('id', '!=', rec.id)], limit=1)
            if existing and existing.product_id and rec.product_id and existing.product_id.id != rec.product_id.id:
                raise ValidationError(
                    "Interchange number '%s' is already assigned to product '%s' and cannot be assigned to '%s'."
                    % (rec.name, existing.product_id.display_name, rec.product_id.display_name)
                )

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        """
        When users pick/interactively search interchange numbers (Many2many/Many2one pickers),
        only show interchanges that are either:
          - unassigned (product_id = False), or
          - already assigned to the current product being edited.
        Pass context {'current_product_id': active_id} from the product form view (see XML below).
        """
        args = args or []
        product_id = self.env.context.get('current_product_id') or self.env.context.get('active_id')
        if product_id:
            # allow unassigned OR assigned to this product
            args = args + [('product_id', 'in', [False, int(product_id)])]
        else:
            # default: show only unassigned interchanges
            args = args + [('product_id', '=', False)]
        return super(ProductInterchange, self).name_search(name, args=args, operator=operator, limit=limit)