from datetime import datetime

import pytz
from flask import Response, request

import ieee_2030_5.adapters as adpt
from ieee_2030_5.server.base_request import RequestOp
from ieee_2030_5.types_ import format_time
from ieee_2030_5.utils import xml_to_dataclass


class Log(RequestOp):

    def get(self) -> Response:
        pth = request.environ['PATH_INFO']
        return self.build_response_from_dataclass(adpt.LogAdapter.fetch_list(pth))

    def post(self) -> Response:
        """Posting of log event allows client to store information for a display to get.
        
        For 2030.5 this is posted at an end device level so that its available to the
        server.
        """
        path = request.environ['PATH_INFO']
        data: m.LogEvent = xml_to_dataclass(request.data.decode('utf-8'))
        data_type = type(data)
        if data_type not in (m.LogEvent):
            raise BAD_REQUEST()

        if not data.createdDateTime:
            data.createdDateTime = format_time(datetime.utcnow().replace(tzinfo=pytz.utc))
        adpt.LogAdapter.store(path, data)