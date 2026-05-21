from odoo import models, fields, api, _

class ResPartner(models.Model):
    _inherit = 'res.partner'


    property_stock_customer = fields.Many2one(
            'stock.location', 
            string='Customer Location',
            company_dependent=True,
            help="The stock location used as customer location for this partner"
        )




    property_stock_supplier = fields.Many2one(
        'stock.location', 
        string='Vendor Location',
        company_dependent=True,
        help="The stock location used as vendor location for this partner"
    )


    vendor_type = fields.Selection([
        ('local', 'Local'),
        ('foreign', 'Foreign')
    ], string='Vendor Type')

    is_clearing_agent = fields.Boolean(string='Is Clearing Agent')
    is_freight_forwarder = fields.Boolean(string='Is Freight Forwarder')
    is_shipping_line = fields.Boolean(string='Is Shipping Line')

    bank_swift_code = fields.Char(string='SWIFT Code')
    bank_routing_number = fields.Char(string='Routing Number')

    trade_license_number = fields.Char(string='Trade License Number')
    trade_license_expiry = fields.Date(string='Trade License Expiry')

    # Tax Information
    tax_identification_number = fields.Char(string='Tax ID Number')
    vat_registration_number = fields.Char(string='VAT Registration Number')

    iso_certification = fields.Char(string='ISO Certification')
    other_certifications = fields.Text(string='Other Certifications')

    foreign_payment_terms = fields.Selection([
        ('advance_100', '100% Advance'),
        ('advance_50_balance_bl', '50% Advance, 50% Against B/L'),
        ('advance_30_balance_bl', '30% Advance, 70% Against B/L'),
        ('lc_sight', 'LC at Sight'),
        ('lc_30_days', 'LC 30 Days'),
        ('lc_60_days', 'LC 60 Days'),
        ('lc_90_days', 'LC 90 Days'),
        ('open_account', 'Open Account'),
    ], string='Foreign Payment Terms')

    preferred_incoterm_id = fields.Many2one('account.incoterms', string='Preferred Incoterm')

    foreign_purchase_count = fields.Integer(compute='_compute_foreign_purchase_count')
    payment_request_count = fields.Integer(compute='_compute_payment_request_count')
    lc_count = fields.Integer(compute='_compute_lc_count')

    duplicate_bank_partner_ids = fields.Many2many(
        'res.partner',
        compute='_compute_duplicate_bank_partner_ids',
        string='Partners with same bank'
    )

    duplicated_bank_account_partners_count = fields.Integer(
        string="Duplicate Bank Partners Count",
        compute='_compute_duplicated_bank_account_partners_count'
    )

    @api.depends('bank_ids.acc_number')
    def _compute_duplicate_bank_partner_ids(self):
        for partner in self:
            duplicates = self.env['res.partner']
            for bank in partner.bank_ids:
                matching_partners = self.search([
                    ('bank_ids.acc_number', '=', bank.acc_number),
                    ('id', '!=', partner.id)
                ])
                duplicates |= matching_partners
            partner.duplicate_bank_partner_ids = duplicates

    @api.depends('bank_ids.acc_number')
    def _compute_duplicated_bank_account_partners_count(self):
        for partner in self:
            duplicates = self.env['res.partner']
            for bank in partner.bank_ids:
                matching_partners = self.search([
                    ('bank_ids.acc_number', '=', bank.acc_number),
                    ('id', '!=', partner.id)
                ])
                duplicates |= matching_partners
            partner.duplicated_bank_account_partners_count = len(duplicates)

    def _compute_foreign_purchase_count(self):
        for partner in self:
           
            if self.env['purchase.order'].check_access_rights('read', raise_exception=False):
                partner.foreign_purchase_count = self.env['purchase.order'].search_count([
                    ('partner_id', '=', partner.id),
                    ('order_type', '=', 'foreign')
                ])
            else:
                partner.foreign_purchase_count = 0

    def _compute_payment_request_count(self):

        for partner in self:
            if self.env['foreign.payment.request'].check_access_rights('read', raise_exception=False):
                partner.payment_request_count = self.env['foreign.payment.request'].search_count([
                    ('supplier_id', '=', partner.id)
                ])
            else:
               
                partner.payment_request_count = 0

    def _compute_lc_count(self):
        for partner in self:
            # Add access rights check for robustness
            if self.env['foreign.lc'].check_access_rights('read', raise_exception=False):
                partner.lc_count = self.env['foreign.lc'].search_count([
                    ('supplier_id', '=', partner.id)
                ])
            else:
                partner.lc_count = 0

    def action_view_foreign_purchases(self):
        self.ensure_one()
        return {
            'name': _('Foreign Purchase Orders'),
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order',
            'view_mode': 'tree,form',
            'domain': [('partner_id', '=', self.id), ('order_type', '=', 'foreign')],
            'context': {'default_partner_id': self.id}
        }

    def action_view_payment_requests(self):
        self.ensure_one()
        return {
            'name': _('Payment Requests'),
            'type': 'ir.actions.act_window',
            'res_model': 'foreign.payment.request',
            'view_mode': 'tree,form',
            'domain': [('supplier_id', '=', self.id)],
            'context': {'default_supplier_id': self.id}
        }

    def action_view_lcs(self):
        self.ensure_one()
        return {
            'name': _('Letters of Credit'),
            'type': 'ir.actions.act_window',
            'res_model': 'foreign.lc',
            'view_mode': 'tree,form',
            'domain': [('supplier_id', '=', self.id)],
            'context': {'default_supplier_id': self.id}
        }

    def action_view_partner_with_same_bank(self):
        self.ensure_one()
        duplicates = self.env['res.partner']
        for bank in self.bank_ids:
            matching_partners = self.search([
                ('bank_ids.acc_number', '=', bank.acc_number),
                ('id', '!=', self.id)
            ])
            duplicates |= matching_partners

        return {
            'name': _('Partners with same bank account'),
            'type': 'ir.actions.act_window',
            'res_model': 'res.partner',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', duplicates.ids)],
            'context': {'default_bank_acc_number': ', '.join(bank.acc_number for bank in self.bank_ids)},
        }


# from odoo import models, fields, api, _

    
# class ResPartner(models.Model):
#     _inherit = 'res.partner'

#     vendor_type = fields.Selection([
#         ('local', 'Local'),
#         ('foreign', 'Foreign')
#     ], string='Vendor Type')

#     is_clearing_agent = fields.Boolean(string='Is Clearing Agent')
#     is_freight_forwarder = fields.Boolean(string='Is Freight Forwarder')
#     is_shipping_line = fields.Boolean(string='Is Shipping Line')

#     bank_swift_code = fields.Char(string='SWIFT Code')
#     bank_routing_number = fields.Char(string='Routing Number')

#     trade_license_number = fields.Char(string='Trade License Number')
#     trade_license_expiry = fields.Date(string='Trade License Expiry')

#     # Tax Information
#     tax_identification_number = fields.Char(string='Tax ID Number')
#     vat_registration_number = fields.Char(string='VAT Registration Number')

#     iso_certification = fields.Char(string='ISO Certification')
#     other_certifications = fields.Text(string='Other Certifications')

#     foreign_payment_terms = fields.Selection([
#         ('advance_100', '100% Advance'),
#         ('advance_50_balance_bl', '50% Advance, 50% Against B/L'),
#         ('advance_30_balance_bl', '30% Advance, 70% Against B/L'),
#         ('lc_sight', 'LC at Sight'),
#         ('lc_30_days', 'LC 30 Days'),
#         ('lc_60_days', 'LC 60 Days'),
#         ('lc_90_days', 'LC 90 Days'),
#         ('open_account', 'Open Account'),
#     ], string='Foreign Payment Terms')

#     preferred_incoterm_id = fields.Many2one('account.incoterms', string='Preferred Incoterm')

#     foreign_purchase_count = fields.Integer(compute='_compute_foreign_purchase_count')
#     payment_request_count = fields.Integer(compute='_compute_payment_request_count')
#     lc_count = fields.Integer(compute='_compute_lc_count')

#     duplicate_bank_partner_ids = fields.Many2many(
#         'res.partner',
#         compute='_compute_duplicate_bank_partner_ids',
#         string='Partners with same bank'
#     )

#     @api.depends('bank_ids.acc_number')
#     def _compute_duplicate_bank_partner_ids(self):
#         for partner in self:
#             duplicates = self.env['res.partner']
#             for bank in partner.bank_ids:
#                 matching_partners = self.search([
#                     ('bank_ids.acc_number', '=', bank.acc_number),
#                     ('id', '!=', partner.id)
#                 ])
#                 duplicates |= matching_partners
#             partner.duplicate_bank_partner_ids = duplicates

#     def _compute_foreign_purchase_count(self):
#         for partner in self:
#             partner.foreign_purchase_count = self.env['purchase.order'].search_count([
#                 ('partner_id', '=', partner.id),
#                 ('order_type', '=', 'foreign')
#             ])

#     def _compute_payment_request_count(self):
#         for partner in self:
#             partner.payment_request_count = self.env['foreign.payment.request'].search_count([
#                 ('supplier_id', '=', partner.id)
#             ])

#     def _compute_lc_count(self):
#         for partner in self:
#             partner.lc_count = self.env['foreign.lc'].search_count([
#                 ('supplier_id', '=', partner.id)
#             ])

#     def action_view_foreign_purchases(self):
#         self.ensure_one()
#         return {
#             'name': _('Foreign Purchase Orders'),
#             'type': 'ir.actions.act_window',
#             'res_model': 'purchase.order',
#             'view_mode': 'tree,form',
#             'domain': [('partner_id', '=', self.id), ('order_type', '=', 'foreign')],
#             'context': {'default_partner_id': self.id}
#         }

#     def action_view_payment_requests(self):
#         self.ensure_one()
#         return {
#             'name': _('Payment Requests'),
#             'type': 'ir.actions.act_window',
#             'res_model': 'foreign.payment.request',
#             'view_mode': 'tree,form',
#             'domain': [('supplier_id', '=', self.id)],
#             'context': {'default_supplier_id': self.id}
#         }

#     def action_view_lcs(self):
#         self.ensure_one()
#         return {
#             'name': _('Letters of Credit'),
#             'type': 'ir.actions.act_window',
#             'res_model': 'foreign.lc',
#             'view_mode': 'tree,form',
#             'domain': [('supplier_id', '=', self.id)],
#             'context': {'default_supplier_id': self.id}
#         }
