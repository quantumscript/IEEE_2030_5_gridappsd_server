"""
This module handles MirrorUsagePoint and UsagePoint constructs for a server.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

from flask import Response, request
from werkzeug.exceptions import BadRequest

import ieee_2030_5.adapters as adpt
import ieee_2030_5.hrefs as hrefs
import ieee_2030_5.models as m
from ieee_2030_5.data.indexer import get_href
from ieee_2030_5.server.base_request import RequestOp
from ieee_2030_5.server.uuid_handler import UUIDHandler
from ieee_2030_5.utils import dataclass_to_xml, xml_to_dataclass


class Error(Exception):
    pass


@dataclass
class ResponseStatus:
    location: str
    status: str


class UsagePointRequest(RequestOp):
    
    def get(self) -> Response:
        pth_info = request.environ['PATH_INFO']
        try:
            upt = adpt.MirrorUsagePointAdapter.fetch_usage_point_by_href(pth_info)
        except StopIteration:
            return Response(status=404, response="Not Found")
        return self.build_response_from_dataclass(upt)


class MirrorUsagePointRequest(RequestOp):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def get(self) -> Response:
        pth_info = request.path

        if not pth_info.startswith(hrefs.DEFAULT_MUP_ROOT):
            raise ValueError(f"Invalid path for {self.__class__} {request.path}")
        
        mup_href = hrefs.MirrorUsagePointHref.parse(pth_info)
        try:
            if mup_href.mirror_usage_point_index == hrefs.NO_INDEX:
                mup = adpt.MirrorUsagePointAdapter.fetch_mirror_usage_point_list(pth_info)
            else:
                mup = adpt.MirrorUsagePointAdapter.fetch_mirror_usage_by_href(pth_info)
                
            return self.build_response_from_dataclass(mup)
        except StopIteration:
            if pth_info == hrefs.mirror_usage_point_href():
                mupl = adpt.MirrorUsagePointAdapter.fetch_mirror_usage_point_list()
                
                
            return Response("Not Found", status=404)
        

    def post(self) -> Response:
        xml = request.data.decode('utf-8')
        data = xml_to_dataclass(request.data.decode('utf-8'))
        data_type = type(data)
        if data_type not in (m.MirrorUsagePoint, m.MirrorReadingSet, m.MirrorMeterReading):
            raise BadRequest()

        pth_info = request.path
        pths = pth_info.split(hrefs.SEP)
        if len(pths) == 1 and data_type is not m.MirrorUsagePoint:
            # Check to make sure not a new mrid
            raise BadRequest("Must post MirrorUsagePoint to top level only")

        # Creating a new mup
        if data_type == m.MirrorUsagePoint:
            result = adpt.MirrorUsagePointAdapter.create(mup=data)
        else:
            result = adpt.MirrorUsagePointAdapter.create_reading(href=pth_info, data=data)
        
        result = ResponseStatus(status=result[0], location = result[1])

        if isinstance(result, Error):
            return Response(result.args[1], status=500)
        # Note response to the post is different due to added endpoint.
        
        return Response(headers={'Location': result.location}, status=result.status if isinstance(result.status, int) else result.status.value)
