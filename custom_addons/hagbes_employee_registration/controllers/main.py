from odoo import http
from odoo.http import request
from werkzeug.utils import redirect


class ForcePasswordChangeController(http.Controller):

    @http.route(['/odoo', '/odoo/'], type='http', auth='user')
    def force_redirect(self, **kwargs):
        user = request.env.user
        if user.must_change_password:
            return redirect('/web/force_password_change')
        return redirect('/odoo/discuss')  # or the default

    @http.route('/web/force_password_change', type='http', auth='user', website=True)
    def force_password_change(self, **post):
        user = request.env.user.sudo()
        if not user or not user.exists():
            return redirect('/web/login')
        return request.render('hagbes_employee_registration.force_password_change_template', {
            'user': user,
            'error': None,
        })

    @http.route('/web/force_password_change/save', type='http', auth='user', website=True, methods=['POST'])
    def force_password_change_save(self, **post):
        user = request.env.user.sudo()
        new_password = post.get('new_password')
        confirm_password = post.get('confirm_password')
        error = None

        if not new_password or not confirm_password:
            error = "Please fill both password fields."
        elif new_password != confirm_password:
            error = "Passwords do not match."
        else:
            # Change password and flag
            user.write({
                'password': new_password,
                'must_change_password': False
            })

            # Avoid session re-authentication here!
            # Just force logout, and redirect to login
            request.session.logout()
            return redirect('/web/login')

        return request.render('hagbes_employee_registration.force_password_change_template', {
            'user': user,
            'error': error,
        })