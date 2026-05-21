# mailing_sms/models/mailing_mailing.py
import logging
import requests
from odoo import models, fields
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class MailingMailing(models.Model):
    _inherit = "mailing.mailing"

    state = fields.Selection([
        ('draft', 'Draft'),
        ('in_queue', 'Queue'),
        ('done', 'Sent'),
        ('failed', 'Failed')
    ], string="SMS Status", default='draft', tracking=False)

    def action_put_in_queue(self):
        """Override 'Put in Queue' to also send SMS after queuing."""
        res = super(MailingMailing, self).action_put_in_queue()
        self._send_sms_campaign()
        return res

    def _send_sms_campaign(self):
        """Send SMS campaign via AfroSMS bulk API."""
        token = self.env['ir.config_parameter'].sudo().get_param('api_token')
        url = self.env['ir.config_parameter'].sudo().get_param('afro_sms_bulk_send_url')

        sender = self.env['ir.config_parameter'].sudo().get_param('SMS_SENDER_NAME', 'ODOO')
        identifier = self.env['ir.config_parameter'].sudo().get_param('SMS_IDENTIFIER_ID', 'ODOO_SYS')
        create_callback = self.env['ir.config_parameter'].sudo().get_param('SMS_CREATE_CALLBACK', '')
        status_callback = self.env['ir.config_parameter'].sudo().get_param('SMS_STATUS_CALLBACK', '')

        if not url:
            _logger.warning("afro_sms_bulk_send_url not configured. Skipping SMS.")
            self.write({'state': 'failed'})
            return

        for mailing in self:
            contacts = mailing.contact_list_ids.contact_ids
            destinations = [c.mobile.strip() for c in contacts if c.mobile]

            if not destinations:
                _logger.info("No contacts with mobile numbers for mailing '%s'", mailing.name)
                mailing.state = 'failed'
                continue

            # Build "to" structure
            to_list = [{"to": phone, "message": (mailing.body_plaintext or mailing.subject or "No content").strip()}
                       for phone in destinations]

            payload = {
                "to": to_list,
                "from": identifier,
                "sender": sender,
                "campaign": mailing.name,  # 👈 Campaign name used here
                "createCallback": create_callback,
                "statusCallback": status_callback,
            }

            headers = {"Content-Type": "application/json"}
            if token:
                headers["Authorization"] = f"Bearer {token}"

            _logger.info("Sending SMS campaign '%s' to %d recipients", mailing.name, len(destinations))

            try:
                response = requests.post(url, json=payload, headers=headers, timeout=15)
                if response.status_code == 200:
                    _logger.info("SMS campaign '%s' sent successfully: %s", mailing.name, response.text)
                    mailing.state = 'done'
                else:
                    _logger.error(
                        "Failed to send SMS campaign '%s'. Status: %s, Response: %s",
                        mailing.name, response.status_code, response.text
                    )
                    mailing.state = 'failed'
            except Exception as e:
                _logger.exception("Error sending SMS campaign '%s': %s", mailing.name, str(e))
                mailing.state = 'failed'


class SmsComposer(models.TransientModel):
    _inherit = "sms.composer"

    def action_send_sms(self):
        self.ensure_one()
        if not self.recipient_single_number_itf:
            raise UserError("Phone number is empty!")
        sent = self._send_sms_single(self.recipient_single_number_itf, self.body)
        if sent:
            return {"type": "ir.actions.act_window_close"}
        return False

    def _send_sms_single(self, phone, message):
        """Send a single SMS via AfroSMS single API."""
        token = self.env['ir.config_parameter'].sudo().get_param('api_token')
        url = self.env['ir.config_parameter'].sudo().get_param('afro_sms_single_url')

        sender = self.env['ir.config_parameter'].sudo().get_param('SMS_SENDER_NAME', 'ODOO')
        identifier = self.env['ir.config_parameter'].sudo().get_param('SMS_IDENTIFIER_ID', 'ODOO_SYS')
        create_callback = self.env['ir.config_parameter'].sudo().get_param('SMS_CREATE_CALLBACK', '')
        status_callback = self.env['ir.config_parameter'].sudo().get_param('SMS_STATUS_CALLBACK', '')

        if not url:
            raise UserError("afro_sms_single_url not configured. Please set it in System Parameters.")

        if not phone:
            raise UserError("Please provide a phone number.")

        payload = {
            "to": phone.strip(), 
            "message": (message or "No content").strip(),
        }

        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        _logger.info("Sending single SMS to %s", phone)

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=15)
            if response.status_code == 200:
                _logger.info("SMS sent successfully to %s: %s", phone, response.text)
                return True
            else:
                _logger.error(
                    "Failed to send SMS to %s. Status: %s, Response: %s",
                    phone, response.status_code, response.text
                )
                raise UserError(f"SMS failed: {response.text}")
        except Exception as e:
            _logger.exception("Error sending SMS to %s: %s", phone, str(e))
            raise UserError(f"Error sending SMS: {str(e)}")
