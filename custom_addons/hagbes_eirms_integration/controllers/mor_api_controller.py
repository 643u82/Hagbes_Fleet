from odoo import http
from odoo.http import request
import requests
import logging 

_logger = logging.getLogger(__name__)

class MorAPIController(http.Controller):

    

    @http.route('/mor/api/login', type='json')
    def mor_api_login(self,**kwargs):
        data = kwargs.get('data')

        if data is None: 
            return {
                'success': False,
                'error': "Missing 'data' parameter"
            }
        url = 'http://core.mor.gov.et'

        try:
            response = requests.post(url, json=data )
            response.raise_for_status()
            return {
                "success":True,
                "status_code":response.status_code,
                "response":response.json() if response.content else {},
            }
        except Exception as e:
            _logger.error("Faile to login",e)
            return {
                "success":False,
                "error":str(e)
            }
