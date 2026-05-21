from odoo import http
from odoo.http import request
import requests
import logging
import base64
_logger = logging.getLogger(__name__)

class PosProxyController(http.Controller):

    @http.route("/pos/set_waiting_fs_number", type="json", auth="user")
    def set_waiting_fs_number(self, invoice_id):
        invoice = request.env["account.move"].sudo().browse(invoice_id)
        invoice.action_set_waiting_fs_number()
        return {"success": True}
    @http.route("/pos/register_fs_number", type="json", auth="user")
    def register_fs_number(self, invoice_number, fs_number, ej_number=None, machine_id=None):
        invoice = request.env["account.move"].sudo().search(
            [("name", "=", invoice_number)],
            limit=1
        )

        if not invoice:
            return {"success": False, "error": "Invoice not found"}

        invoice.ref = fs_number
        invoice.ej_number = ej_number
        invoice.machine_id = machine_id

        invoice.action_set_posted()

        return {
            "success": True,
            "message": f"Invoice {invoice.name} posted with FS {fs_number}",
        }
    