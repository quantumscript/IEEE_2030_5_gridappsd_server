from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from http.client import BAD_REQUEST
from typing import Optional

import pytz
import tzlocal
import werkzeug.exceptions
from flask import Flask, Response, request
from werkzeug.exceptions import Forbidden
from werkzeug.routing import BaseConverter

import ieee_2030_5.adapters as adpt
import ieee_2030_5.hrefs as hrefs
import ieee_2030_5.models as m
from ieee_2030_5.certs import TLSRepository
from ieee_2030_5.config import ServerConfiguration
from ieee_2030_5.data.indexer import get_href, get_href_filtered
from ieee_2030_5.server.base_request import RequestOp
from ieee_2030_5.server.dcapfs import Dcap
from ieee_2030_5.server.derfs import DERProgramRequests, DERRequests
from ieee_2030_5.server.enddevicesfs import (EDevRequests, FSARequests,
                                             SDevRequests)
# module level instance of hrefs class.
from ieee_2030_5.server.meteringfs import (MirrorUsagePointRequest,
                                           UsagePointRequest)
from ieee_2030_5.server.server_constructs import EndDevices
from ieee_2030_5.server.timefs import TimeRequest
from ieee_2030_5.server.uuid_handler import UUIDHandler
from ieee_2030_5.types_ import TimeOffsetType, format_time
from ieee_2030_5.utils import dataclass_to_xml, xml_to_dataclass

_log = logging.getLogger(__name__)


class Admin(RequestOp):

    def get(self):
        if not self.is_admin_client:
            raise Forbidden()
        return Response("We are able to do stuff here")

    def post(self):
        if not self.is_admin_client:
            raise Forbidden()
        return Response(json.dumps({'abc': 'def'}), headers={'Content-Type': 'application/json'})








class ServerList(RequestOp):

    def __init__(self, list_type: str, **kwargs):
        super().__init__(**kwargs)
        self._list_type = list_type

    def get(self) -> Response:
        response = None
        if self._list_type == 'EndDevice':
            response = self._end_devices.get_end_device_list(self.lfdi)

        if response:
            response = dataclass_to_xml(response)

        return response


class RegexConverter(BaseConverter):

    def __init__(self, url_map, *items):
        super(RegexConverter, self).__init__(url_map)
        self.regex = items[0]
        _log.debug(f"regex is {self.regex}")


class ServerEndpoints:

    def __init__(self, app: Flask, tls_repo: TLSRepository, config: ServerConfiguration):
        self.config = config
        self.tls_repo = tls_repo
        self.mimetype = "text/xml"
        self.app: Flask = app
        self.app.url_map.converters['regex'] = RegexConverter

        _log.debug(f"Adding rule: {hrefs.uuid_gen} methods: {['GET']}")
        app.add_url_rule(hrefs.uuid_gen, view_func=self._generate_uuid)
        _log.debug(f"Adding rule: {hrefs.get_dcap_href()} methods: {['GET']}")
        app.add_url_rule(hrefs.get_dcap_href(), view_func=self._dcap)
        _log.debug(f"Adding rule: {hrefs.get_time_href()} methods: {['GET']}")
        app.add_url_rule(hrefs.get_time_href(), view_func=self._tm)
        _log.debug(f"Adding rule: {hrefs.sdev} methods: {['GET']}")
        app.add_url_rule(hrefs.sdev, view_func=self._sdev)
        # _log.debug(f"Adding rule: {hrefs.derp} methods: {['GET']}")
        # app.add_url_rule(hrefs.derp, view_func=self._derp)

        # All the energy devices
        #app.add_url_rule(f"/{hrefs.EDEV}", methods=["GET", "POST", "PUT"], view_func=self._edev)
        app.add_url_rule(f"/<regex('{hrefs.EDEV}{hrefs.MATCH_REG}'):path>",
                         view_func=self._edev,
                         methods=["GET", "PUT", "POST"])
        # This rule must be before der
        app.add_url_rule(f"/<regex('{hrefs.DER_PROGRAM}{hrefs.MATCH_REG}'):path>",
                         view_func=self._derp,
                         methods=["GET"])
        app.add_url_rule(f"/<regex('{hrefs.DER}{hrefs.MATCH_REG}'):path>",
                         view_func=self._der,
                         methods=["GET", "PUT"])
        app.add_url_rule(f"/<regex('{hrefs.MUP}{hrefs.MATCH_REG}'):path>",
                         view_func=self._mup,
                         methods=["GET", "POST"])
        app.add_url_rule(f"/<regex('{hrefs.UTP}{hrefs.MATCH_REG}'):path>",
                         view_func=self._upt,
                         methods=["GET", "POST"])
        app.add_url_rule(f"/<regex('{hrefs.CURVE}{hrefs.MATCH_REG}'):path>",
                         view_func=self._curves,
                         methods=["GET"])
        
        app.add_url_rule(f"/<regex('{hrefs.FSA}{hrefs.MATCH_REG}'):path>",
                         view_func=self._fsa,
                         methods=["GET"])
        app.add_url_rule(f"/<regex('{hrefs.LOG}{hrefs.MATCH_REG}'):path>",
                         view_func=self._log,
                         methods=["GET", "POST"])
        # rulers = (
        #     (hrefs.der_urls, self._der),
        #     #(hrefs.edev_urls, self._edev),
        #     (hrefs.mup_urls, self._mup),
        #     (hrefs.curve_urls, self._curves),
        #     (hrefs.program_urls, self._programs)
        # )
        #
        # for endpoints, view_func in rulers:
        #     # Item should either be a single rule or a rule with a second element having the methods
        #     # in it.
        #     # edev = [
        #     #   /edev,
        #     #   (f"/edev/<int: index>", ["GET", "POST"])
        #     # ]
        #     for item in endpoints:
        #         try:
        #             rule, methods = item
        #         except ValueError:
        #             rule = item
        #             methods = ["GET"]
        #         _log.debug(f"Adding rule: {rule} methods: {methods}")
        #         app.add_url_rule(rule, view_func=view_func, methods=methods)
        #
        # self.add_endpoint(hrefs.dcap, view_func=self._dcap)
        # self.add_endpoint(hrefs.edev, view_func=self._edev)
        # self.add_endpoint(hrefs.mup, view_func=self._mup, methods=['GET', 'POST'])
        # self.add_endpoint(hrefs.uuid_gen, view_func=self._generate_uuid)
        # app.add_url_rule(hrefs.rsps, view_func=None)
        # self.add_endpoint(hrefs.tm, view_func=self._tm)
        #
        # for index, ed in end_devices.all_end_devices.items():
        #     self.add_endpoint(hrefs.edev + f"/{index}", view_func=self._edev)
        #     self.add_endpoint(hrefs.mup + f"/{index}", view_func=self._mup)

    def _log(self, path):
        return

    def _foo(self, bar):
        return Response("Foo Response")

    def _generate_uuid(self) -> Response:
        return Response(UUIDHandler().generate())

    #
    # def _admin(self) -> Response:
    #     return Admin(server_endpoints=self).execute()
    
    def _fsa(self, path) -> Response:
        return FSARequests(server_endpoints=self).execute()

    def _upt(self, path) -> Response:
        return UsagePointRequest(server_endpoints=self).execute()

    def _mup(self, path) -> Response:
        return MirrorUsagePointRequest(server_endpoints=self).execute()
    
    # Needs to be before der
    def _derp(self, path) -> Response:
        return DERProgramRequests(server_endpoints=self).execute()

    def _der(self, path) -> Response:
        _log.debug(request.method)
        return DERRequests(server_endpoints=self).execute()

    def _dcap(self) -> Response:
        return Dcap(server_endpoints=self).execute()

    def _edev(self, path: Optional[str] = None) -> Response:
        return EDevRequests(server_endpoints=self).execute()

    # def _edev(self, index: Optional[int] = None, category: Optional[str] = None) -> Response:
    #     return EDevRequests(server_endpoints=self).execute(index=index, category=category)

    def _sdev(self) -> Response:
        return SDevRequests(server_endpoints=self).execute()

    def _tm(self) -> Response:
        return TimeRequest(server_endpoints=self).execute()


    def _curves(self, path) -> Response:
        pth = request.environ['PATH_INFO']
        obj = get_href(pth)
        # if index is None:
        #     items = get_href_filtered(hrefs.curve)
        #     curve_list = DERCurveList(DERCurve=items, all=len(items), href=request.path, results=len(items))
        #     response = Response(dataclass_to_xml(curve_list))
        # else:
        #     response = Response(dataclass_to_xml(get_href(request.path)))
        return RequestOp(server_endpoints=self).build_response_from_dataclass(obj)
        # if index is None:
        #     items = get_href_filtered(href_prefix=hrefs.program)
        #     program_list = DERProgramList(DERProgram=items, all=len(items), href=request.path, results=len(items))
        #     response = Response(dataclass_to_xml(program_list))
        # else:
        #     response = Response(dataclass_to_xml(get_href(request.path)))
        # return response
