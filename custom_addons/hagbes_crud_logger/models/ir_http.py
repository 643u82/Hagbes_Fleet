import json
import logging
import time

from odoo import models
from odoo.http import request as http_request
from odoo.tools.config import config

_logger = logging.getLogger("monitoring.http.requests")


class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    @classmethod
    def _dispatch(cls, *args, **kwargs):
        begin = time.time()

        # IMPORTANT: class-based super
        response = super(IrHttp, cls)._dispatch(*args, **kwargs)

        end = time.time()

        try:
            path = http_request.httprequest.environ.get("PATH_INFO", "")
            if not path.startswith(("/longpolling", "/websocket")):
                info = cls._monitoring_info(http_request, response, begin, end)
                cls._monitoring_log(info)
        except Exception:
            _logger.exception("HTTP monitoring failed")

        return response

    @classmethod
    def _monitoring_info(cls, request, response, begin, end):
        return {
            "start_time": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(begin)),
            "duration": round(end - begin, 4),

            "method": request.httprequest.method,
            "path": request.httprequest.environ.get("PATH_INFO"),
            "user_agent": request.httprequest.environ.get("HTTP_USER_AGENT"),

            "db": request.session.db if hasattr(request, "session") else None,
            "uid": request.uid,
            "login": request.session.login if hasattr(request, "session") else None,
            "server_environment": config.get("running_env"),

            "model": request.params.get("model") if hasattr(request, "params") else None,
            "model_method": request.params.get("method") if hasattr(request, "params") else None,

            "status_code": getattr(response, "status_code", None),
        }

    @classmethod
    def _monitoring_log(cls, info):
        _logger.info(json.dumps(info))
