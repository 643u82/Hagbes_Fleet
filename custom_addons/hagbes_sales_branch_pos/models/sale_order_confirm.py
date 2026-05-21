from odoo import api, fields, models, _
from datetime import date, timedelta
from odoo.exceptions import UserError, ValidationError
import logging 

_logger= logging.getLogger(__name__)



class SaleOrder(models.Model):
    _inherit = "sale.order"

    payment_mode = fields.Selection([
        ('CASH', 'Cash'),
        ('DIRECTTRANSFER', 'Direct Transfer'),
        ('CREDIT', 'Credit'),
        ('CHEQUE', 'Cheque'),
    ], string="Payment Mode", default='CASH')
    @api.depends('partner_id', 'amount_total', 'payment_mode', 'state')
    def _compute_partner_credit_warning(self):
        for order in self:
            # Only show warning for CREDIT mode and in draft/sent states
            if (
                order.payment_mode == 'CREDIT'
                and order.state in ['draft', 'sent']
                and order.partner_id
                and order.partner_id.credit_limit > 0
            ):
                total_due = order.partner_id.credit + order.amount_total
                if total_due > order.partner_id.credit_limit:
                    order.partner_credit_warning = _(
                        "Customer '%s' has reached its credit limit of %.2f Br.\n"
                        "Total amount due (including this order): %.2f Br."
                    ) % (
                        order.partner_id.name,
                        order.partner_id.credit_limit,
                        total_due
                    )
                else:
                    order.partner_credit_warning = ''
            else:
                # ✅ Clear warning for non-CREDIT modes or posted orders
                order.partner_credit_warning = ''
    @api.onchange('payment_mode', 'partner_id')
    def _onchange_payment_mode(self):
        """Automatically update payment terms based on payment mode."""
        for order in self:
            if not order.partner_id:
                order.payment_term_id = False
                continue

            # Immediate payment for cash or direct transfer
            if order.payment_mode in ['CASH', 'DIRECTTRANSFER' , 'CHEQUE']:
                immediate_term = self.env.ref('account.account_payment_term_immediate', raise_if_not_found=False)
                order.payment_term_id = immediate_term

            elif order.payment_mode == 'CREDIT':
                # Check if customer has credit limit
                if not order.partner_id.credit_limit_due_date:
                    return {
                        'warning': {
                            'title': 'Credit Not Allowed',
                            'message': f"{order.partner_id.name} is not eligible for credit (no credit limit defined)."
                        }
                    }

                # Check for due date from partner
                due_date = order.partner_id.credit_limit_due_date
                if not due_date or due_date <= date.today():
                    return {
                        'warning': {
                            'title': 'Invalid Credit Period',
                            'message': f"{order.partner_id.name} has an expired or invalid credit due date."
                        }
                    }

                # If credit, set a custom term (or create one dynamically)
                credit_term = self._get_or_create_dynamic_credit_term(order.partner_id, due_date)
                order.payment_term_id = credit_term

    def _get_or_create_dynamic_credit_term(self, partner, due_date):
        PaymentTerm = self.env['account.payment.term']
        name = f"Credit until {due_date.strftime('%Y-%m-%d')}"
        existing = PaymentTerm.search([('name', '=', name)], limit=1)
        if existing:
            return existing

        today = fields.Date.today()
        days_diff = (due_date - today).days
        if days_diff < 0:
            days_diff = 0

        term = PaymentTerm.create({
            'name': name,
            'note': f"Credit due on {due_date.strftime('%Y-%m-%d')}",
            'line_ids': [(0, 0, {
                'value': 'percent',        
                'value_amount': 100.0,     
                'delay_type': 'days_after',
                'nb_days': days_diff,
            })]
        })
        return term
    def action_confirm(self):
        """Confirm Sale Order with credit, payment term, and stock validation."""  
       
        for order in self:
            partner = order.partner_id.commercial_partner_id
          
            # 🔒 CREDIT VALIDATION (only if payment mode is credit)
            if order.payment_mode == 'CREDIT':
                if not partner.use_partner_credit_limit:
                    raise UserError(_(
                        "Customer '%s' is not eligible for credit purchases."
                    ) % partner.name)
                new_total_credit = partner.credit + order.amount_total
                _logger.info("new total credit is %s",new_total_credit)
                if new_total_credit <= 0:
                    raise UserError(_(
                        "Customer '%s' does not have a defined credit limit."
                    ) % partner.name)

                if new_total_credit > partner.credit_limit:
                    raise UserError(_(
                        "Customer '%s' exceeded their credit limit.\n"
                        "Limit: %s\nCurrent Balance: %s\nBalance After This Order: %s"
                    ) % (
                        partner.name,
                        format(partner.credit_limit, '.2f'),
                        format(partner.credit, '.2f'),
                        format(new_total_credit, '.2f'),
                    ))

                if (
                    partner.credit_limit_due_date
                    and fields.Date.today() > partner.credit_limit_due_date
                    and partner.credit > 0
                ):
                    raise UserError(_(
                        "Credit period for '%s' expired on %s.\nOutstanding balance: %s."
                    ) % (
                        partner.name,
                        partner.credit_limit_due_date,
                        format(partner.credit, '.2f')
                    ))

                # ✅ Ensure payment term is correctly set (recalculate if missing)
                if not order.payment_term_id:
                    today = fields.Date.today()
                    due_date = partner.credit_limit_due_date or (today + timedelta(days=15))
                    term_name = f"Credit until {due_date.strftime('%Y-%m-%d')}"
                    term = self.env['account.payment.term'].create({
                        'name': term_name,
                        'note': f"Auto-generated credit term valid until {due_date.strftime('%Y-%m-%d')}",
                        'line_ids': [(0, 0, {
                                'value': 'percent',
                                'value_amount': 100.0,
                                'delay_type': 'days_after',
                                'nb_days': max(0, (due_date - today).days),
                            })]
                    })
                    order.payment_term_id = term

            # else:
            #     # 💵 For cash/direct transfer
            #     immediate_term = self.env.ref('account.account_payment_term_immediate', raise_if_not_found=False)
            #     if immediate_term:
            #         order.payment_term_id = immediate_term

            # # 🧾 STOCK CHECK (same as before)
            # warehouse = order.warehouse_id
            # if not warehouse:
            #     raise UserError(_("Please select a warehouse on the sale order."))

            # stock_location = warehouse.lot_stock_id
            # StockQuant = self.env['stock.quant']
            # lines_with_partial_qty = []
            # lines_with_zero = []

            # for line in order.order_line:
            #     product = line.product_id
            #     qty_needed = line.product_uom_qty
            #     qty_available = StockQuant._get_available_quantity(
            #                 product_id=product,
            #                 location_id=stock_location,
            #                 strict=True
            #             )
            #     _logger.info("avaialable product is antsh %s and sotck_locations is %s",qty_available,stock_location)

            #     if qty_needed > qty_available:
            #         if qty_available <= 0:
            #             lines_with_zero.append({
            #                 'product': product,
            #                 'requested': qty_needed,
            #                 'available': 0.0,
            #             })
            #         else:
            #             lines_with_partial_qty.append({
            #                 'product': product,
            #                 'requested': qty_needed,
            #                 'available': qty_available,
            #             })

            # # Register lost sales for 0-availability products
            # for line in lines_with_zero:
            #     self.env['lost.sale'].create({
            #         'product_id': line['product'].id,
            #         'customer_id': order.partner_id.id,
            #         'sale_order_id': order.id,
            #         'quantity_requested': line['requested'],
            #         'quantity_available': 0.0,
            #         'quantity_lost':line['requested'],
            #         'branch_id': order.branch_id.id,     
            #         'warehouse_id': order.warehouse_id.id,
            #         'company_id': order.company_id.id,   
            #         'reason': 'out_of_stock',
            #     })

            # if not lines_with_partial_qty and lines_with_zero:
            #     order.write({'state': 'lost'})
            #     return {
            #         'type': 'ir.actions.act_window',
            #         'name': 'Order Marked as Lost',
            #         'res_model': 'lost.sale.notification.wizard',
            #         'view_mode': 'form',
            #         'target': 'new',
            #         'context': {
            #             'default_message': 'All requested products are unavailable. The order has been marked as a lost sale.'
            #         }
            #     }

            # if lines_with_partial_qty or lines_with_zero:
            #     combined_lines = lines_with_partial_qty + lines_with_zero
            #     line_data = []
            #     for item in combined_lines:
            #         line_data.append((0, 0, {
            #             'product_id': item['product'].id,
            #             'requested': item['requested'],
            #             'available': item['available'],
            #             'shortage': item['requested'] - item['available'],
            #         }))

            #     wizard = self.env['sale.confirmation.wizard'].create({
            #         'sale_order_id': order.id,
            #         'line_ids': line_data,
            #     })

            #     return {
            #         'name': 'Insufficient Stock - Confirm Partial?',
            #         'type': 'ir.actions.act_window',
            #         'res_model': 'sale.confirmation.wizard',
            #         'view_mode': 'form',
            #         'target': 'new',
            #         'res_id': wizard.id,
            #         'context': self.env.context,
            #     }

        return super(SaleOrder, self).action_confirm()
    def action_create_invoice_direct(self):
        self.ensure_one()
        if self.state != 'sale':
            raise UserError(_("Only confirmed orders can be invoiced."))
        if self.invoice_status != 'to invoice':
            raise UserError(_("Nothing to invoice."))

        
        invoices = self._create_invoices(final=True)

        # ✅ Return to open the created invoice (same as wizard does)
        return self.action_view_invoice(invoices=invoices)