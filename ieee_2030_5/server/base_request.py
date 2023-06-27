from __future__ import annotations
import logging
from dataclasses import dataclass
from typing import Dict, Callable, Optional

import werkzeug
from flask import request, Response

from ieee_2030_5.certs import TLSRepository
from ieee_2030_5.config import ServerConfiguration
from ieee_2030_5.models import DeviceCategoryType
import ieee_2030_5.server.server_endpoints as eps

from ieee_2030_5.types_ import SEP_XML
from ieee_2030_5.utils import dataclass_to_xml

_log = logging.getLogger(__name__)


class ServerOperation:

    def __init__(self):
        if 'ieee_2030_5_peercert' not in request.environ:
            raise werkzeug.exceptions.Forbidden()
        self._headers = {'Content-Type': SEP_XML}

    def head(self, **kwargs):
        raise werkzeug.exceptions.MethodNotAllowed()

    def get(self, **kwargs):
        raise werkzeug.exceptions.MethodNotAllowed()

    def post(self, **kwargs):
        raise werkzeug.exceptions.MethodNotAllowed()

    def delete(self, **kwargs):
        raise werkzeug.exceptions.MethodNotAllowed()

    def put(self, **kwargs):
        raise werkzeug.exceptions.MethodNotAllowed()

    def execute(self, **kwargs):
        methods = {
            'GET': self.get,
            'POST': self.post,
            'DELETE': self.delete,
            'PUT': self.put
        }

        fn = methods.get(request.environ['REQUEST_METHOD'])
        if not fn:
            raise werkzeug.exceptions.MethodNotAllowed()

        return fn(**kwargs)


class RequestOp(ServerOperation):
    def __init__(self, server_endpoints: eps.ServerEndpoints):
        super().__init__()
        self._tls_repository = server_endpoints.tls_repo
        self._server_endpoints = server_endpoints

    @property
    def tls_repo(self) -> TLSRepository:
        return self._tls_repository

    @property
    def server_config(self) -> ServerConfiguration:
        return self._server_endpoints.config

    @property
    def lfdi(self):
        return request.environ["ieee_2030_5_lfdi"] # self._tls_repository.lfdi(request.environ['ieee_2030_5_subject'])

    @property
    def device_id(self):
        return request.environ.get("ieee_2030_5_subject")

    def get_path(self, required_prefix: Optional[str] = None) -> str:
        """
        Retrieve the context web request environment PATH_INFO with optional required_prefix
        argument.  If that argument is specified then it will be validated against PATH_INFO.  The
        function will raise a ValueError if the PATH_INFO does not start with required_prefix.

        Args:
            required_prefix:

        Returns:
            The path specified in request.environ['PATH_INFO'
        """

        pth = request.environ['PATH_INFO']

        if required_prefix and not pth.startswith(required_prefix):
            raise ValueError(f"Invalid path for {self.__class__} {request.path}")

        return pth

    def build_response_from_dataclass(self, obj: dataclass) -> Response:
        return Response(dataclass_to_xml(obj), headers=self._headers)
