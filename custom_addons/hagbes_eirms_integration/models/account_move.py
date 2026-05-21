# models/account_move.py
import json
import logging
import base64
from datetime import datetime  
from odoo import models,fields,api,_
from odoo.exceptions import UserError, ValidationError
from dateutil import parser

_logger = logging.getLogger(__name__)

try:
    import requests
except Exception as e:
    requests = None
    _logger.warning("requests library not available: %s", e)


class AccountMove(models.Model):
    _inherit = 'account.move'

    irn = fields.Char(string="IRN", readonly=True,copy=False)
    qr_code = fields.Binary(string="QR Code",readonly=True, copy=False,attachment=False)
    irn_ack_date = fields.Datetime(string="IRN Acknowledgement Date", readonly=True, copy=False)
    irn_status = fields.Char(string="IRN Status", readonly=True, copy=False)
    irn_document_number = fields.Char(string="IRN Document Number", readonly=True, copy=False)
    signed_invoice = fields.Text(string="Signed Invoice", readonly=True, copy=False)
    mor_document_number = fields.Char(
    string="MOR Document Number",
    readonly=True,
    copy=False
    )

    @api.model
    def set_qr_code_from_base64(self, base64_str):
        """Convert base64 QR string (from MOR) to Binary field"""
        if base64_str:
            self.qr_code = base64.b64decode(base64_str)
    @api.model
    def create(self, vals):
        if vals.get('move_type') in ['out_invoice', 'out_refund']:  # Only for customer invoices
            if vals.get('branch_id') and (not vals.get('name') or vals.get('name') == '/'):
                try:
                    # Get branch info
                    branch = self.env['account.analytic.account'].browse(vals['branch_id'])
                    branch_code = branch.code or '00'
                    year = str(datetime.now().year)[-2:]

                    # Dynamic sequence code per branch/year
                    seq_code = f'account.move.{branch_code}.{year}'

                    # Find or create sequence
                    sequence = self.env['ir.sequence'].sudo().search([('code', '=', seq_code)], limit=1)
                    if not sequence:
                        sequence = self.env['ir.sequence'].sudo().create({
                            'name': f'Invoice {branch_code} {year}',
                            'code': seq_code,
                            'prefix': '',
                            'padding': 5,
                            'number_next': 1,
                            'number_increment': 1,
                            'implementation': 'standard',
                            'use_date_range': False,
                            'active': True,
                        })

                    # Get next number
                    next_number = sequence.next_by_id()
                    _logger.info(f"Raw next_number: {next_number}, Type: {type(next_number)}")

                    formatted_number = f"{int(next_number):05d}"

                    # Build invoice name
                    vals['name'] = f"INV{branch_code}{year}{formatted_number}"

                except Exception as e:
                    raise ValidationError(f"Error generating invoice number: {e}")

        return super(AccountMove, self).create(vals)

    def _mor_build_payload(self):
        """Build JSON payload from system params and invoice data."""
        ICP = self.env['ir.config_parameter'].sudo()
        client_id = ICP.get_param('mor.client_id') or ''
        client_secret = ICP.get_param('mor.client_secret') or ''
        api_key = ICP.get_param('mor.api_key') or ''
        seller_tin = ICP.get_param('mor.seller_tin') or ''
        base_url=ICP.get_param('mor.url') or ''

        payload = {
            "clientId": client_id,
            "clientSecret": client_secret,
            "apikey": api_key,
            "tin": seller_tin
        }
        return payload
    def _mor_make_url(self, path):
        """Helper to safely concatenate base MOR URL with a relative path."""
        base_url = self.env['ir.config_parameter'].sudo().get_param('mor.url') or ''
        base_url = base_url.rstrip('/')  # remove trailing slash if any
        path = path.lstrip('/')          # remove leading slash if any
        return f"{base_url}/{path}"
    def _mor_call_login(self, payload, timeout=10):
        """Call the external login API. Return dict with success boolean and response json/error."""
        url = self._mor_make_url('/auth/login')
        if requests is None:
            return {"success": False, "error": "requests library not available on server"}

        headers = {'Content-Type': 'application/json'}
        try:
            _logger.info("MOR login: calling %s with payload %s", url, payload)
            resp = requests.post(url, json=payload, headers=headers, timeout=timeout)
        except Exception as e:
            _logger.exception("MOR login: request failed")
            return {"success": False, "error": str(e)}

        try:
            resp_json = resp.json()
        except Exception:
            resp_json = {"raw_text": resp.text}

        _logger.info("🔹 MOR Login Response JSON: %s", resp_json)

        if resp.status_code in (200, 201):
            # ✅ Extract the token correctly from "data.accessToken"
            data = resp_json.get("data", {})
            token = data.get("accessToken") or data.get("token")

            return {
                "success": True,
                "status_code": resp.status_code,
                "response": resp_json,
                "token": token
            }
        else:
            return {
                "success": False,
                "status_code": resp.status_code,
                "response": resp_json
            }

    

    def _peek_next_invoice_number(self, seq_code):
        """Peek the next sequence number without incrementing."""
        sequence = self.env['ir.sequence'].sudo().search([('code', '=', seq_code)], limit=1)
        if not sequence:
            return None, None

        # peek next number without incrementing
        next_number = sequence.number_next_actual
        formatted = str(next_number).zfill(sequence.padding or 5)
        return sequence, formatted

    def action_post(self):
        """Custom action_post: 
        1️⃣ Generate branch-based invoice number
        2️⃣ Integrate MOR login + registration
        3️⃣ Post invoice only after MOR success
        """

        for move in self:
            if move.move_type not in ['out_invoice', 'out_refund']:
                # Call normal Odoo posting for other types
                return super(AccountMove, move).action_post()

            try:
                # ======================================================
                # 1️⃣ DETERMINE BRANCH CODE
                # ======================================================
                branch = getattr(move, 'branch_id', False)

                if not branch:
                    analytic_ids = set()
                    for line in move.invoice_line_ids:
                        if line.analytic_distribution:
                            analytic_ids.update(line.analytic_distribution.keys())

                    if analytic_ids:
                        analytic_id = int(list(analytic_ids)[0])
                        analytic = self.env['account.analytic.account'].sudo().search(
                            [('id', '=', analytic_id)], limit=1
                        )
                        if not analytic:
                            raise ValidationError(_("Analytic account %s not found for invoice %s") %
                                                  (analytic_id, move.display_name))
                        branch = analytic
                    else:
                        raise ValidationError(_("No branch or analytic account found for invoice %s") %
                                              (move.display_name))

                branch_code = getattr(branch, 'code', False) or '00'
                year = str(datetime.now().year)[-2:]

                seq_code = f'account.move.{branch_code}.{year}'
                sequence = self.env['ir.sequence'].sudo().search([('code', '=', seq_code)], limit=1)
                if not sequence:
                    sequence = self.env['ir.sequence'].sudo().create({
                        'name': f'Invoice {branch_code} {year}',
                        'code': seq_code,
                        'prefix': '',
                        'padding': 5,
                        'number_next': 1,
                        'number_increment': 1,
                        'implementation': 'standard',
                        'use_date_range': False,
                        'active': True,
                    })

                # ======================================================
                # 2️⃣ PEEK NEXT NUMBER (not increment yet)
                # ======================================================
                sequence, formatted_number = move._peek_next_invoice_number(seq_code)
                move.name = f"INV{branch_code}{year}{formatted_number}"
                _logger.info("🧾 Temporarily reserved invoice number %s (not yet consumed)", move.name)

                # ======================================================
                # 3️⃣ BUILD PAYLOAD & SEND TO MOR
                # ======================================================
                payload = move._mor_build_payload()  # your existing method
                result = move._mor_call_login(payload)  # your existing login call

                if not result.get("success"):
                    err = result.get("error") or result.get("response") or "Unknown error"
                    move.message_post(body=f"<b>❌ MOR Login Failed</b><br/><pre>{err}</pre>")
                    _logger.error("❌ MOR login failed for invoice %s: %s", move.name, err)
                    raise UserError(_("Failed to login to MOR service. Reason: %s") % err)

                token = result.get("token")
                if not token:
                    raise UserError(_("MOR login succeeded but token missing."))

                # Build JSON payload to register invoice
                mor_json = move._build_mor_json_payload()

                # 🧾 Log payload before sending
                try:
                    safe_payload = json.dumps(mor_json, indent=4, ensure_ascii=False, default=str)
                    _logger.info("📦 MOR Payload for %s:\n%s", move.name, safe_payload)
                except Exception as log_err:
                    _logger.warning("⚠️ Failed to serialize MOR payload for %s: %s", move.name, log_err)

                register_url = move._mor_make_url("/v1/register")
                headers = {
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                }

                _logger.info("🔹 Sending invoice %s to MOR API: %s", move.name, register_url)
                resp = requests.post(register_url, json=mor_json, headers=headers, timeout=20)

                try:
                    resp_json = resp.json()
                except Exception:
                    resp_json = {"raw_text": resp.text}

                # Log the MOR response too
                _logger.info("📩 MOR Response for %s:\n%s", move.name, json.dumps(resp_json, indent=4, ensure_ascii=False, default=str))

                if resp.status_code not in (200, 201):
                    msg = resp_json.get("message") or resp_json
                    move.message_post(body=f"<b>❌ MOR Registration Failed</b><br/><pre>{json.dumps(resp_json, indent=4, ensure_ascii=False)}</pre>")
                    raise UserError(_("MOR registration failed: %s") % msg)

                body = resp_json.get("body", {})
                data = body.get("data", body)
                irn = data.get("irn")

                if not irn:
                    raise UserError(_("MOR did not return a valid IRN."))

                # ======================================================
                # 4️⃣ PARSE ACK DATE SAFELY
                # ======================================================
                ack_date_raw = data.get("ackDate")
                ack_date_parsed = None
                
                if ack_date_raw:
                    try:
                        ack_date_parsed = parser.parse(ack_date_raw)
                    except Exception:
                        _logger.warning("⚠️ Failed to parse ackDate: %s", ack_date_raw)

                qr_b64 = data.get("signedQR")
                decoded_qr = False

                if qr_b64 and isinstance(qr_b64, str):
                    try:
                        decoded_qr = base64.b64decode(qr_b64)
                        _logger.info("✅ QR code decoded successfully (%d bytes)", len(decoded_qr))
                    except Exception as e:
                        _logger.error("❌ Failed to decode QR code: %s", e)

                move.write({
                    'irn': irn,
                    'irn_ack_date': ack_date_parsed,
                    'irn_status': data.get("status"),
                    'irn_document_number': data.get("documentNumber"),
                    'mor_document_number': data.get("documentNumber"),
                    'qr_code': decoded_qr,
                    'signed_invoice': data.get("signedInvoice"),
                })

                # ✅ Increment the sequence manually now that it's successful
                if sequence:
                    sequence.sudo().write({
                        'number_next_actual': sequence.number_next_actual + 1
                    })
                    _logger.info("✅ Sequence incremented for %s after MOR success", seq_code)

                move.message_post(body=f"<b>✅ MOR Registered Successfully</b><br/>IRN: {irn}<br/>Invoice No: {move.name}")

                # ======================================================
                # 6️⃣ POST THE INVOICE
                # ======================================================
                result_super = super(AccountMove, move).action_post()
                _logger.info("✅ Invoice %s posted successfully.", move.name)
                return result_super

            except Exception as e:
                _logger.exception("❌ Error during action_post for invoice %s: %s", move.name, e)
                raise UserError(_("Error during invoice posting: %s") % str(e))

    def _build_mor_json_payload(self):
        """Builds and returns the MOR JSON structure after invoice is confirmed."""
        self.ensure_one()

        company = self.company_id
        system_number = self.env['ir.config_parameter'].sudo().get_param('mor.system_number')

        seq_str = ''.join(filter(str.isdigit, self.name))[-5:] if self.name else '0'
        seq_num = int(seq_str) if seq_str.isdigit() else 0

        # 🔹 Buyer Details
        partner = self.partner_id
        buyer_data = {
            "City": partner.city or "0",
            "Email": partner.email or "",
            "HouseNumber": partner.street or "NEW",
            "IdNumber": partner.vat or "11122222222222222",
            "IdType": "KID",
            "Tin": '0000025458',
            "LegalName": "Hagbes Plc",
            "Phone": partner.phone or "",
            "Region": str(partner.state_id.id) if partner.state_id else "13",
            "Country": str(partner.country_id.id) if partner.country_id else "70",
            "Zone": getattr(partner, 'zone', 'SHA'),
            "Kebele": getattr(partner, 'kebele', '03'),
            "VatNumber": '43256663343256663322',
            "Wereda": getattr(partner, 'wereda', '13'),
        }

        # 🔹 Document Details
        document_date = self.invoice_date or datetime.today().date()
        document_data = {
            "DocumentNumber": seq_num + 35 ,
            "Date": document_date.strftime("%d-%m-%YT%H:%M:%S"),
            "Type": "INV"
        }

        # 🔹 Item List
        item_list = []
        for idx, line in enumerate(self.invoice_line_ids, start=1):
            tax_amount = 0
            if line.tax_ids:
                tax_data = line.tax_ids.compute_all(line.price_unit, self.currency_id, line.quantity)
                tax_amount = sum(t['amount'] for t in tax_data.get('taxes', []))
            if line.product_id.type in ('product', 'consu'):
                nature = "goods"
            else:
                nature = "services"
            TAX_CODE_MAPPING = {
                '15%': 'VAT15',
                '10%': 'VAT10',
                '0%': 'VAT0',
                'EXEMPT': 'VATEX',
                'Turnover Tax 2%': 'TOT2',
                # Add more as needed
            }

            tax_codes = []
            for tax in line.tax_ids:
                mor_code = TAX_CODE_MAPPING.get(tax.name, None)
                if mor_code:
                    tax_codes.append(mor_code)
                else:
                    _logger.warning("MOR: No tax code mapping for tax '%s' on line %d", tax.name, idx)

            tax_code_str = ",".join(tax_codes) if tax_codes else ""
            item = {
                "Discount":  0,
                "ExciseTaxValue": 0,
                "HarmonizationCode": None,
                "NatureOfSupplies": nature, 
                "ItemCode": line.product_id.default_code or "N/A",
                "ProductDescription": line.name,
                "PreTaxValue": line.price_subtotal,
                "Quantity": line.quantity,
                "LineNumber": idx,
                "TaxAmount": tax_amount,
                "TaxCode": tax_code_str,
                "TotalLineAmount": line.price_total,
                "Unit":  "PCS",
                "UnitPrice": line.price_unit
            }
            item_list.append(item)

        # 🔹 Payment Details
        payment_mode = 'CASH'  # Default
        if hasattr(self, 'invoice_origin_id') and self.invoice_origin_id:
            payment_mode = getattr(self.invoice_origin_id, 'payment_mode', 'CASH')
        elif hasattr(self, 'payment_mode'):  # If you added payment_mode directly on invoice
            payment_mode = self.payment_mode or 'CASH'

        payment_term = "IMMIDIATE" if payment_mode in ['CASH', 'DIRECTTRANSFER','CHEQUE'] else "CREDIT"
        payment_data = {
            "Mode": payment_mode.upper(),
            "PaymentTerm": payment_term.upper()
        }

        # 🔹 Reference Details
        branch = getattr(self, "branch_id", False)

        domain = [
            ('move_type', '=', 'out_invoice'),
            ('state', '=', 'posted'),
            ('irn', '!=', False),
            ('id', '!=', self.id),
        ]
        if branch:
            domain.append(('branch_id', '=', branch.id))

        last_invoice = self.env['account.move'].sudo().search(domain, order='id desc', limit=1)
        previous_irn = last_invoice.irn if last_invoice else "45648798797"
        reference_data = {
            "PreviousIrn": previous_irn,
            "RelatedDocument": None
        }

        # 🔹 Seller Details
        seller_data = {
            "City":  None,
            "Email":"info.it@hagbes.com",
            "HouseNumber": None,
            "LegalName": "Hagbes PLC",
            "Locality": None,
            "Phone": company.phone or None,
            "Region": company.state_id.name if company.state_id else '1',
            "SubCity": None,
            "Tin": company.tin_number or None, 
            "VatNumber": company.vat or None,
            "Wereda": "13",
        }

        # 🔹 Source System
        source_data = {
            "CashierName": self.env.user.name or "AAA",
            "InvoiceCounter": seq_num + 35,
            "SalesPersonName": self.invoice_user_id.name or "AAA",
            "SystemNumber": system_number or "UNKNOWN",
            "SystemType": "POS"
        }

        # 🔹 Value Details
        value_data = {
            "Discount": None,
            "ExciseValue": 0,
            "IncomeWithholdValue": 220,
            "TaxValue": self.amount_tax,
            "TotalValue": self.amount_total,
            "TransactionWithholdValue": 0,
            "InvoiceCurrency": self.currency_id.name
        }

        payload_data = {
            "BuyerDetails": buyer_data,
            "DocumentDetails": document_data,
            "ItemList": item_list,
            "PaymentDetails": payment_data,
            "ReferenceDetails": reference_data,
            "SellerDetails": seller_data,
            "SourceSystem": source_data,
            "TransactionType": getattr(partner,'partner_type',''),
            "ValueDetails": value_data,
            "Version": "1"
        }

        # ✅ RETURN THE PAYLOAD (this was missing!)
        return payload_data