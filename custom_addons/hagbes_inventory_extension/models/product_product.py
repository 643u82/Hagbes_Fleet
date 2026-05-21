from odoo import models, fields, api

class ProductProduct(models.Model):
    _inherit = 'product.product'

    interchangeble = fields.One2many(
        related='product_tmpl_id.interchangeable_number_ids',
        string="Interchangeable Numbers",
        readonly=False
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
