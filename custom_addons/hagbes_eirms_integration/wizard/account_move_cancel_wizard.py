# wizard/mor_cancel_wizard.py
import json
import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import requests

_logger = logging.getLogger(__name__)


class AccountMoveCancelWizard(models.TransientModel):
    _name = 'account.move.cancel.wizard'
    _description = 'Cancel Invoice Wizard for MOR'

    reason = fields.Selection([
        ('1', 'Duplicate'),
        ('2', 'Data entry mistake'),
        ('3', 'Order cancelled'),
        ('4', 'Other'),
    ], string="Reason", required=True, help="Reason for cancelling the invoice")

    remark = fields.Char(string="Remark", help="Optional remark")

    def action_confirm_cancel(self):
        """Send cancellation request to MOR after user selects reason."""
        self.ensure_one()
        active_id = self.env.context.get('active_id')
        invoice = self.env['account.move'].browse(active_id)

        if not invoice.irn:
            raise ValidationError(_("This invoice does not have an IRN to cancel."))

        # ========================================
        # 1️⃣ LOGIN TO MOR
        # ========================================
        ICP = self.env['ir.config_parameter'].sudo()
        base_url = (ICP.get_param('mor.url') or '').rstrip('/')
        login_payload = {
            "clientId": ICP.get_param('mor.client_id'),
            "clientSecret": ICP.get_param('mor.client_secret'),
            "apikey": ICP.get_param('mor.api_key'),
            "tin": ICP.get_param('mor.seller_tin')
        }

        login_url = f"{base_url}/auth/login"
        headers = {"Content-Type": "application/json"}

        _logger.info("🔹 MOR Cancel Login Request: %s", json.dumps(login_payload, indent=4))

        resp = requests.post(login_url, json=login_payload, headers=headers, timeout=15)
        try:
            data = resp.json()
        except Exception:
            data = {"raw_text": resp.text}

        if resp.status_code not in (200, 201):
            raise ValidationError(_("MOR login failed: %s") % data)

        token = data.get("data", {}).get("accessToken")
        if not token:
            raise ValidationError(_("MOR login succeeded but token missing."))

        # ========================================
        # 2️⃣ SEND CANCEL REQUEST
        # ========================================
        cancel_payload = {
            "Irn": invoice.irn,
            "ReasonCode": self.reason,
            "Remark": self.remark or ""
        }

        cancel_url = "http://core.mor.gov.et/v1/cancel"
        headers["Authorization"] = f"Bearer {token}"

        _logger.info("📤 MOR Cancel Request for %s:\n%s", invoice.name, json.dumps(cancel_payload, indent=4))

        resp = requests.post(cancel_url, json=cancel_payload, headers=headers, timeout=20)
        try:
            cancel_resp = resp.json()
        except Exception:
            cancel_resp = {"raw_text": resp.text}

        _logger.info("📩 MOR Cancel Response for %s:\n%s", invoice.name, json.dumps(cancel_resp, indent=4))

        if resp.status_code not in (200, 201):
            raise UserError(_("MOR cancellation failed: %s") % cancel_resp)

        # ========================================
        # 3️⃣ UPDATE INVOICE STATUS
        # ========================================
        invoice.write({
            'state': 'cancel',
        })

        invoice.message_post(body=f"<b>✅ Invoice cancelled on MOR</b><br/><pre>{json.dumps(cancel_resp, indent=4)}</pre>")

        return {'type': 'ir.actions.act_window_close'}
 