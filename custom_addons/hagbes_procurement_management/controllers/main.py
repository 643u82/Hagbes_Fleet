from odoo import http
from odoo.http import request
from odoo.exceptions import AccessError, MissingError
import logging

_logger = logging.getLogger(__name__)

class ShipmentTrackingController(http.Controller):

    @http.route('/shipment_tracking/<int:transit_id>', type='http', auth='user')
    def shipment_tracking(self, transit_id, **kwargs):
        shipment = request.env['foreign.transit.process'].sudo().browse(transit_id)
        if not shipment.exists():
            return request.not_found()
        return request.render('hagbes_procurement_management.shipment_tracking_template', {
            'shipment': shipment,
            'title': "Live Shipment Tracking",
        })

    @http.route('/api/shipment_position/<int:record_id>', type='http', auth='user', methods=['POST'], csrf=False)
    def get_shipment_position(self, record_id, model='foreign.transit.process', **kw):
        """API endpoint for the map widget to get the current position."""
        try:
            if model not in ['foreign.transit.process']:
                return {'error': 'Invalid model specified.'}

            record = request.env[model].browse(record_id).exists()
            if not record:
                return {'error': 'Record not found'}

            data = {
                'latitude': record.current_latitude,
                'longitude': record.current_longitude,
                'speed': record.current_speed,
                'course': record.current_course,
                'vessel_name': record.vessel_name or "Unknown Vessel",
                'last_update': record.last_position_update.isoformat() if record.last_position_update else None,
                'tracking_status': record.tracking_status,
                'state': record.state,
            }
            return request.make_json_response(data)
        except Exception as e:
            _logger.error(f"Error fetching shipment position for {model} {record_id}: {e}")
            return request.make_json_response({'error': str(e)}, status=500)
