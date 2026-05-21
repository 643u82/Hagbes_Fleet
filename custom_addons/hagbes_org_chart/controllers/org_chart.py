from odoo import http
from odoo.http import request

class OrgChartController(http.Controller):
    @http.route('/custom_org_chart_extension/data', type='json', auth='user')
    def get_org_chart_data(self):
        jobs = request.env['hr.job'].sudo()
        return jobs.get_org_chart_data()