from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import datetime
import logging 

_logger = logging.getLogger(__name__)
class AccountMove(models.Model):
    _inherit = "account.move"

    manual_invoice = fields.Boolean(string='Manual Invoice',default=False)
    ej_number=fields.Char(string='EJ Number')
    machine_id = fields.Char(string = 'Machine ID')
    state = fields.Selection([
            ('draft', 'Draft'),
            ('waiting_pos_print', 'Waiting POS Print'),
            ('waiting_fs_number', 'Waiting FS Number'),
            ('posted', 'Posted'),
            ('cancel', 'Cancelled'),
        ], string='Status', required=True, readonly=True, copy=False, tracking=True,
        default='draft',
        ondelete={
            'waiting_pos_print': 'set default',
            'waiting_fs_number': 'set default',
        })
    def action_set_waiting_fs_number(self):
        for move in self:
            if move.state == "waiting_pos_print":
                move.state = "waiting_fs_number"
    def action_set_posted(self):
        for move in self:
            if move.state == "waiting_fs_number":
                move.with_context(from_fs_flow=True).action_post()
            
    @api.model
    def create(self, vals):
        # Only apply to customer invoices and refunds
        if vals.get('move_type') in ('out_invoice', 'out_refund') and (not vals.get('name') or vals.get('name') == 'New'):
            try:
                # Determine branch_id
                branch_code = '00'
                branch_id = vals.get('branch_id')

                # If branch_id not set, try to get from related sale order
                if not branch_id and vals.get('invoice_origin'):
                    sale_order = self.env['sale.order'].search([('name', '=', vals['invoice_origin'])], limit=1)
                    if sale_order:
                        branch_id = sale_order.branch_id.id

                # Get branch code if branch_id exists
                if branch_id:
                    branch = self.env['account.analytic.account'].browse(branch_id)
                    branch_code = branch.code or '00'

                # Last two digits of the year
                year = str(datetime.now().year)[-2:]

                # Sequence code per branch/year
                seq_code = f'invoice.{branch_code}.{year}'

                # Find or create the sequence
                sequence = self.env['ir.sequence'].sudo().search([('code', '=', seq_code)], limit=1)
                if not sequence:
                    sequence = self.env['ir.sequence'].sudo().create({
                        'name': f'Invoice {branch_code} {year}',
                        'code': seq_code,
                        'prefix': '',  # we'll add prefix manually
                        'padding': 5,
                        'number_next': 1,
                        'number_increment': 1,
                        'implementation': 'standard',
                        'use_date_range': False,
                        'active': True,
                    })

                # Get next number from sequence
                next_number = sequence.next_by_id()
                formatted_number = f"{int(next_number):05d}"

                # Build final invoice name
                vals['name'] = f"INV{branch_code}{year}{formatted_number}"
                _logger.info(f"Generated invoice name: {vals['name']}")

            except Exception as e:
                raise ValidationError(f"Error generating invoice sequence: {e}")

        return super(AccountMove, self).create(vals)
    def action_post(self):
        # First, let Odoo handle posting for all moves (especially payments!)
        res = super(AccountMove, self).action_post()

        # Only apply custom POS workflow to customer invoices (out_invoice/out_refund)
        for move in self:
            if (
                not move.manual_invoice
                and move.move_type in ('out_invoice', 'out_refund')  
                and move.state == 'posted' 
                and not self.env.context.get('from_fs_flow')
                
            ):
                move.write({'state': 'waiting_pos_print'})  # Or better: use pos_workflow_state!

        return res
    def print_to_pos(self):
        self.ensure_one()

        # ✅ Format date in ISO 8601 with timezone (+03:00)
        tz_offset = "+03:00"
        timestamp = datetime.now().strftime(f"%Y-%m-%dT%H:%M:%S.%f")[:-3] + tz_offset

        # ✅ Determine payment_mode (from related sale order if available)
        payment_mode = 'CASH'
        sale_order = self.env['sale.order'].search([('name', '=', self.invoice_origin)], limit=1)
        if sale_order:
            payment_mode = sale_order.payment_mode or 'CASH'

        # ✅ Map payment_mode to PaymentType
        payment_type_map = {
            'CASH': '0',
            'CHEQUE': '1',
            'CREDIT': '2',
            'DIRECTTRANSFER': '0',
        }
        payment_type = payment_type_map.get(payment_mode, '0')
        _logger.info(f"payment type for invoice{self.name} is {payment_type} and payment mode is {payment_mode}")
        # ✅ Payment Term
        payment_term = "IMMEDIATE" if payment_mode in ['CASH', 'DIRECTTRANSFER', 'CHEQUE'] else "CREDIT"

        # ✅ Get branch code from invoice.branch_id
        branch_code = ""
        # Try to get branch code from analytic_distribution on invoice lines
        for line in self.invoice_line_ids:
            if line.analytic_distribution:
                try:
                    analytic_data = line.analytic_distribution
                    # analytic_data is JSON like {analytic_id: percentage}
                    analytic_account_id = list(analytic_data.keys())[0] if analytic_data else None
                    if analytic_account_id:
                        analytic_account = self.env['account.analytic.account'].browse(int(analytic_account_id))
                        branch_code = analytic_account.code or "00"
                        break  # stop after finding first valid branch
                except Exception as e:
                    _logger.warning(f"Error parsing analytic_distribution: {e}")
        # fallback
        if not branch_code:
            branch_code = "00"

        pos_id = f"pos-{branch_code}"


        # ✅ Salesperson and cashier info
        salesperson_name = self.invoice_user_id.name or "Unknown"
        cashier_name = self.env.user.name or "Unknown"

        # ✅ Partner Info
        partner = self.partner_id
        customer_name = partner.name or ""
        customer_tin = getattr(partner, "tin_number", "") or ""
        customer_vat = partner.vat or ""

        # ✅ Prepare line items
        hold_sales_items = []
        for index, line in enumerate(self.invoice_line_ids, start=1):
            tax_type = 4
            if line.tax_ids:
                tax = line.tax_ids[0]
                if tax.amount_type == 'percent' and tax.amount > 0:
                    tax_type = 1

            hold_sales_items.append({
                "HoldSalesItemIdentifierId": f"{self.name}{index}",
                "CategoryIdentifierId": str(line.product_id.categ_id.id or ""),
                "CategoryName": line.product_id.categ_id.name or None,
                "ItemIdentifierId": str(line.product_id.id or ""),
                "ItemDescription": line.product_id.name or "",
                "ItemCode": line.product_id.default_code or "",
                "UomIdentifierId": str(line.product_uom_id.id or ""),
                "UomName": line.product_uom_id.name or "",
                "Quantity": float(line.quantity),
                "SalesUnitPrice": float(line.price_unit),
                "TaxType": tax_type,
            })

        # ✅ Final payload
        pos_data = {
            "HoldSalesIdentifierId": str(self.name),
            "TransactionType": "0",
            "InvoiceNo": self.name or "",
            "PaymentType": payment_type,
            "TableNumber": " ",
            "SalesPerson": salesperson_name,
            "HoldMemo": " ",
            "Date": timestamp,
            "CustomerName": customer_name,
            "CustomerTIN": customer_tin,
            "CustomerVAT": customer_vat,
            "CashierUpdated": cashier_name,
            "POSId": pos_id, 
            "HoldSalesItems": hold_sales_items,
        }

        
        # _logger.info("payload is %s",pos_data)
        return {
            'type': 'ir.actions.client',
            'tag': 'print_to_pos',
            'data': pos_data
        }
    def get_fs_number(self):
        
        invoice_numbers = []   # array to collect invoice numbers

        for record in self:
            if record.manual_invoice:
                continue
            invoice_numbers.append(record.name)   # add each invoice number


                            
        # super(AccountMove,record).action_post()
        return {
            "type": "ir.actions.client",
            "tag": "get_fs_number", 
            "data": invoice_numbers
        }


