import json
import logging
from datetime import datetime, date
import pytz
import base64

from odoo import models, fields
from odoo.exceptions import UserError

try:
    import requests
except Exception:
    requests = None

_logger = logging.getLogger(__name__)


# =========================================================
# ACCOUNT PAYMENT (PERSISTENT STORAGE)
# =========================================================
class AccountPayment(models.Model):
    _inherit = "account.payment"

    mor_receipt_id = fields.Char("MOR Receipt ID", readonly=True)
    mor_receipt_status = fields.Char("MOR Status", readonly=True)
    mor_rrn = fields.Char("MOR RRN", readonly=True)
    mor_qr = fields.Binary(
        "MOR QR Code",
        attachment=True,
        readonly=True
    )
    mor_raw_response = fields.Text("MOR Raw Response", readonly=True)


# =========================================================
# PAYMENT REGISTER WIZARD (API + FLOW CONTROL)
# =========================================================
class AccountPaymentRegister(models.TransientModel):
    _inherit = "account.payment.register"

    # -----------------------------------------------------
    # MOR datetime formatter
    # -----------------------------------------------------
    def _format_mor_datetime(self, dt):
        tz = pytz.timezone("Africa/Addis_Ababa")

        if isinstance(dt, str):
            dt = fields.Datetime.from_string(dt)

        if isinstance(dt, date) and not isinstance(dt, datetime):
            dt = datetime.combine(dt, datetime.min.time())

        if not dt:
            dt = fields.Datetime.now()

        if dt.tzinfo is None:
            dt = pytz.UTC.localize(dt)

        dt = dt.astimezone(tz)

        return dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3] + "+03:00"

    # -----------------------------------------------------
    # Build MOR receipt payload
    # -----------------------------------------------------
    def _build_sales_receipt_payload(
        self,
        invoice,
        seller_tin,
        system_number,
    ):
        self.ensure_one()

        payment_mode = getattr(invoice, "payment_mode", "CASH")

        return {
            "ReceiptNumber": f"REC{invoice.name}",
            "ReceiptType": "Sales Receipts",
            "Reason": f"Payment for invoice {invoice.name}",
            "ReceiptDate": self._format_mor_datetime(self.payment_date),
            "ReceiptCounter": str(invoice.id),
            "SourceSystemType": "POS",
            "SourceSystemNumber": system_number,
            "ReceiptCurrency": self.currency_id.name,
            "CollectedAmount": self.amount,
            "SellerTIN": seller_tin,

            "Invoices": [{
                "InvoiceIRN": invoice.irn,
                "PaymentCoverage": "FULL"
                if self.amount >= invoice.amount_total
                else "PARTIAL",
                "InvoicePaidAmount": self.amount,
                "RemainingAmount": max(
                    invoice.amount_total - self.amount, 0
                ),
                "TotalAmount": invoice.amount_total,
            }],

            "TransactionDetails": {
                "ModeOfPayment": payment_mode,
                "CollectorName": self.env.user.name,
                "AccountNumber": (
                    self.partner_bank_id.acc_number
                    if self.partner_bank_id else ""
                ),
                "TransactionNumber": f"TRX{invoice.id}",
            }
        }

    # -----------------------------------------------------
    # MAIN OVERRIDE
    # -----------------------------------------------------
    def action_create_payments(self):

        if requests is None:
            raise UserError("requests library is not available")

        ICP = self.env["ir.config_parameter"].sudo()

        seller_tin = ICP.get_param("mor.seller_tin")
        system_number = ICP.get_param("mor.system_number")

        if not ICP.get_param("mor.url"):
            raise UserError("MOR base URL not configured")

        mor_response = {}

        for wizard in self:
            invoices = wizard.line_ids.move_id
            if not invoices:
                continue

            invoice = invoices[0]

            if not invoice.irn:
                raise UserError(
                    f"Invoice {invoice.name} has no IRN"
                )

            # -------------------------------
            # LOGIN (reusing AccountMove)
            # -------------------------------
            login_payload = invoice._mor_build_payload()
            login_result = invoice._mor_call_login(login_payload)

            if not login_result.get("success"):
                raise UserError(
                    f"MOR login failed: {login_result}"
                )

            token = login_result.get("token")
            if not token:
                raise UserError("MOR token missing")

            # -------------------------------
            # SEND RECEIPT
            # -------------------------------
            payload = wizard._build_sales_receipt_payload(
                invoice,
                seller_tin,
                system_number,
            )

            _logger.info(
                "📦 MOR Receipt Payload:\n%s",
                json.dumps(payload, indent=4)
            )

            receipt_url = invoice._mor_make_url(
                "/v1/receipt/sales"
            )

            response = requests.post(
                receipt_url,
                json=payload,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                timeout=20
            )

            try:
                mor_response = response.json()
            except Exception:
                mor_response = {"raw": response.text}

            _logger.info(
                "📩 MOR Receipt Response:\n%s",
                json.dumps(mor_response, indent=4)
            )

            if response.status_code not in (200, 201):
                raise UserError(
                    "Payment NOT created.\n"
                    f"MOR receipt failed:\n{mor_response}"
                )

        # -------------------------------------------------
        # CREATE PAYMENT
        # -------------------------------------------------
        payments = super().action_create_payments()

        # payments is already an account.payment recordset
        for payment in payments:
            payment.write({
                "mor_receipt_id": mor_response.get("ReceiptID"),
                "mor_receipt_status": mor_response.get("Status"),
                "mor_rrn": mor_response.get("RRN"),
                "mor_qr": mor_response.get("QRCode"),
                "mor_raw_response": json.dumps(mor_response, indent=4),
            })

        return payments
