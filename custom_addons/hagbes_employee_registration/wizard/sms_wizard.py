from odoo import models, fields, api
from odoo.exceptions import ValidationError,UserError
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import asyncio
import secrets
import string
import logging
from concurrent.futures import ThreadPoolExecutor
_logger = logging.getLogger(__name__)

class SMSWizard(models.TransientModel):
    _name = "sms.wizard"
    _description = "Send SMS / Reset Password Wizard"

    employee_ids = fields.Many2many(
    'hr.employee',
    string="Employees",
    domain=lambda self: self._get_employee_domain()
    )
    reset_password = fields.Boolean(string="Reset Password for Selected Employees")
    reset_all_passwords = fields.Boolean(string="Reset Password for All Employees")
    send_sms = fields.Boolean(string="Send SMS to Selected Employees")
    send_to_all = fields.Boolean(string="Send SMS to All Employees")
    message = fields.Text(string="Message")

    @property
    def DB_URL(self):
        # Fetch from system parameters
        param = self.env['ir.config_parameter'].sudo().get_param('sms.db_url')
        if not param:
            raise UserError("System parameter 'sms.db_url' is not set!")
        return param

    def _generate_password(self):
        """Generate a 4-digit numeric password"""
        return ''.join(secrets.choice(string.digits) for _ in range(4))

    def _send_sms_db(self, destination, text_message):
        engine = create_engine(self.DB_URL, pool_pre_ping=True)
        SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        db = SessionLocal()
        try:
            _logger.info("Attempting to send SMS to %s: %s", destination, text_message)
            db.execute(
                text(
                    "INSERT INTO outbox (DestinationNumber, TextDecoded, CreatorID) "
                    "VALUES (:dest, :text, :creator)"
                ),
                {"dest": destination, "text": text_message, "creator": "Odoo"}
            )
            db.commit()
            _logger.info("Successfully inserted SMS for %s", destination)
            return True
        except Exception as e:
            db.rollback()
            _logger.error("Failed to send SMS to %s: %s", destination, e, exc_info=True)
            return False
        finally:
            db.close()

    # Async wrapper for SMS sending
    async def _send_sms_async(self, destination, text_message):
        loop = asyncio.get_event_loop()
        executor = ThreadPoolExecutor(max_workers=10)
        await loop.run_in_executor(executor, self._send_sms_db, destination, text_message)

    # Main action
    def action_send_sms(self):
        self.ensure_one()
        failed_employees = []
        success_count = 0

        if not self.message and not self.reset_password and not self.reset_all_passwords:
            raise UserError("Please enter a message or enable 'Reset Password' before sending.")

        # Handle employee scope
        if self.reset_all_passwords or self.send_to_all:
            employees = self.env['hr.employee'].search([])
        else:
            employees = self.employee_ids

        if not employees:
            raise UserError("No employees selected.")

        for emp in employees:
            phone = emp.work_phone or emp.mobile_phone
            if not phone:
                failed_employees.append(emp.name)
                continue
            new_user = emp.user_id
            new_password = None
            if (self.reset_password or self.reset_all_passwords) and emp.user_id:
                new_password = self._generate_password()
                hashed_pw = new_user._crypt_context().hash(new_password)
                new_user._set_encrypted_password(new_user.id, hashed_pw)
                emp.user_id.write({"password": new_password})


            # Default header if no message
            sms_text = (self.message or "Employee ID and Password").strip()

            if new_password and emp.user_id:
                sms_text += f"\nLogin: {emp.user_id.login}\nPassword: {new_password}"

            sent = self._send_sms_db(phone, sms_text)
            if sent:
                success_count += 1
            else:
                failed_employees.append(emp.name)

        if success_count == 0:
            raise UserError(
                "Failed to send SMS. "
                f"Errors for employees: {', '.join(failed_employees) or 'Unknown'}"
            )

        msg = f"SMS sent successfully to {success_count} employees."
        if failed_employees:
            msg += f"\nFailed for: {', '.join(failed_employees)}"

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "SMS Result",
                "message": msg,
                "type": "success" if success_count else "warning",
                "sticky": False,
            },
        }

    @api.model
    def _get_employee_domain(self):
        user = self.env.user
        branches = user.allowed_branch_ids

        if not branches:
            return [('id', '=', 0)]

        return [('branch_id', 'in', branches.ids)]


class SmsComposerInherit(models.TransientModel):
    _inherit = "sms.composer"

    reset_password = fields.Boolean(string="Reset Password")
    send_smas = fields.Boolean(string="Send SMS", default=True)
    reset_all_passwords = fields.Boolean(string="Reset All Passwords", default=False)

    employee_ids= fields.Many2many(
        'hr.employee',
        string="Employee",
        default=lambda self: self._compute_recipient_single_non_stored(),
        store=False,
    )

    
    send_sms=fields.Boolean(string="Send SMS", default=True)
    send_to_all=fields.Boolean(string="Send to All Employees", default=False)

    def action_send_sms(self):
            """ Override default button to call your custom wizard """
           
                # Create wizard record
            wizard = self.env['sms.wizard'].create({
                "employee_ids": [(6, 0, self.employee_ids.ids)],
                "message": self.body,
                "reset_password": False,
                "reset_all_passwords": False,
                "send_sms": True,
                "send_to_all": False,
            })

            # Call your wizard method
            return wizard.action_send_sms()

    @api.model
    def _default_employee_from_form(self):
        active_id = self.env.context.get('active_id')
        if not active_id:
            return []
        employee = self.env['hr.employee'].browse(active_id)
        return employee.ids

    @api.depends('res_model', 'number_field_name')
    def _compute_recipient_single_non_stored(self):
        for composer in self:
            records = composer._get_records()

            # Default values
            composer.recipient_single_description = False
            composer.recipient_single_number = ''
            composer.employee_id = False

            if not records or not composer.comment_single_recipient:
                continue

            records.ensure_one()

            # Get SMS recipient info from Odoo
            res = records._sms_get_recipients_info(
                force_field=composer.number_field_name,
                partner_fallback=True
            )

            info = res[records.id]

            # Set SMS fields
            composer.recipient_single_description = (
                info['partner'].name
                or records._mail_get_partners()[records[0].id].display_name
            )

            composer.recipient_single_number = (
                info['sanitized'] or info['number'] or ''
            )

            # 🔥 NEW — compute employee
            if info.get("employee_ids"):
                composer.employee_id = info["employee_ids"][0]
            else:
                composer.employee_id = False   

    def button_load_and_send_sms(self):
        """Load the employee from active form and send SMS"""
        active_id = self.env.context.get('active_id')
        if not active_id:
            raise UserError("No active employee found")
        print ("Active ID:", active_id)
        employee = self.env['hr.employee'].browse(active_id)
        self.employee_ids = employee.ids

        # Call your overridden send SMS
        return self.action_send_sms()
