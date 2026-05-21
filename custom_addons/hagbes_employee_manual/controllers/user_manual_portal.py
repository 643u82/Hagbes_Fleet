from odoo import http
from odoo.http import request


class EmployeeManualPortal(http.Controller):
    @http.route("/employee/user_manuals", type="http", auth="user", website=True)
    def hagbes_employee_manuals(self, **kwargs):
        user = request.env.user
        manuals = (
            request.env["user.manual.category"]
            .sudo()
            .search([("group_id", "in", user.groups_id.ids)])
        )
        values = {"manuals": manuals}
        return request.render("hagbes_employee_manual.portal_user_manuals", values)

    @http.route(
        "/employee/user_manuals/download/<int:manual_id>",
        type="http",
        auth="user",
        website=True,
    )
    def hagbes_employee_manual_download(self, manual_id, **kwargs):
        manual = request.env["user.manual.category"].sudo().browse(manual_id)
        if not manual.exists():
            return request.not_found()
        user = request.env.user
        if manual.group_id not in user.groups_id and not user.has_group("hr.group_hr_manager"):
            return request.not_found()
        return request.redirect(
            f"/web/content/{manual._name}/{manual.id}/manual_file/{manual.manual_filename or ''}"
        )

