from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError

class UserManualCategory(models.Model):
    _name = "user.manual.category"
    _inherit = ["mail.thread"]
    _description = "Employee User Manual Category"
    _order = "name"

    # -------------------------
    # Fields
    # -------------------------
    name = fields.Char(required=True)
    description = fields.Text()
    group_ids = fields.Many2many(
    "res.groups",
    string="Security Groups",
    help="Employees in any of the selected groups may see the manual.",
    )

    manual_file = fields.Binary(
        string="Manual File",
        attachment=True,
        help="Upload PDF or Markdown manual.",
    )
    manual_filename = fields.Char(string="Filename")

    # -------------------------
    # Access Rules
    # -------------------------
    def _check_admin_write_access(self):
        """Only Admin can create/update/delete manuals."""
        if not self.env.user.has_group("base.group_system"):
            raise AccessError(_("Only Administrators can create or modify manuals."))

    # -------------------------
    # CRUD Overrides
    # -------------------------
    @api.model
    def create(self, vals):
        self._check_admin_write_access()
        print(f">>> Creating manual: {vals.get('name')}")
        return super().create(vals)

    def write(self, vals):
        self._check_admin_write_access()
        print(f">>> Updating manual IDs: {[r.id for r in self]}")
        return super().write(vals)

    def unlink(self):
        self._check_admin_write_access()
        print(f">>> Deleting manual IDs: {[r.id for r in self]}")
        return super().unlink()

    # -------------------------
    # Search Restriction (filter records for non-admins)
    @api.model
    def search(self, args, offset=0, limit=None, order=None, count=False):
        if not self.env.user.has_group("base.group_system"):
            user_group_ids = self.env.user.groups_id.ids
            print(f">>> Non-admin search, user groups: {user_group_ids}")

            args = [
                "|",
                ("group_ids", "in", user_group_ids),
                ("group_ids", "=", False),
            ] + (args or [])

        return super().search(args, offset=offset, limit=limit, order=order, count=count)




    # -------------------------
    # @api.model
    # def search(self, args, offset=0, limit=None, order=None, count=False):
    #     if not self.env.user.has_group("base.group_system"):
    #         user_group_ids = self.env.user.groups_id.ids
    #         print(f">>> Non-admin search, user groups: {user_group_ids}")
    #         args = ["|", ("group_id", "in", user_group_ids), ("group_id", "=", False)] + (args or [])
    #     return super().search(args, offset=offset, limit=limit, order=order, count=count)

    # -------------------------
    # Read (no strict access check needed now)
    # -------------------------

    def read(self, fields=None, load="_classic_read"):
        user = self.env.user
        if not user.has_group("base.group_system"):
            user_group_ids = user.groups_id.ids

            accessible_records = self.filtered(
                lambda r: not r.group_ids or any(g.id in user_group_ids for g in r.group_ids)
            )

            print(f">>> User {user.name} can read manual IDs: {[r.id for r in accessible_records]}")
            return super(UserManualCategory, accessible_records).read(fields=fields, load=load)

        return super().read(fields=fields, load=load)
    # def read(self, fields=None, load="_classic_read"):
    #     """Non-admins can only read manuals for their groups."""
    #     user = self.env.user
    #     if not user.has_group("base.group_system"):
    #         user_group_ids = user.groups_id.ids
    #         # filter self to only include records the user belongs to
    #         accessible_records = self.filtered(lambda r: not r.group_id or r.group_id.id in user_group_ids)
    #         print(f">>> User {user.name} can read manual IDs: {[r.id for r in accessible_records]}")
    #         return super(UserManualCategory, accessible_records).read(fields=fields, load=load)
    #     return super().read(fields=fields, load=load)


    # -------------------------
    # File Download Action
    # -------------------------
    def action_download_manual(self):
        self.ensure_one()
        print(f">>> Download manual: {self.name} for user {self.env.user.name}")
        return {
            "type": "ir.actions.act_url",
            "url": f"/web/content/{self._name}/{self.id}/manual_file/{self.manual_filename or ''}",
            "target": "self",
        }
    def action_preview_manual(self):
        """Open file in a new browser tab (preview if browser supports it)."""
        self.ensure_one()
        if not self.manual_file:
            raise UserError("No manual file uploaded.")
        # `download=false` tells the controller to show it in-browser if possible
        return {
            'type': 'ir.actions.act_url',
            'url': f"/web/content/{self._name}/{self.id}/manual_file/{self.manual_filename or ''}?download=false",
            'target': 'new',
        }