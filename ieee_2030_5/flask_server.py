import hashlib
import itertools
import json
import logging
import os
import ssl
import threading
import time
from dataclasses import fields
from functools import lru_cache
from pathlib import Path
from queue import Queue

import OpenSSL
import werkzeug.exceptions
from flask import Flask, Response, redirect, render_template, request, url_for
# from flask_socketio import SocketIO, send
from werkzeug.serving import BaseWSGIServer, make_server

from ieee_2030_5.utils import dataclass_to_xml

__all__ = ["build_server"]

import ieee_2030_5.adapters as adpt
import ieee_2030_5.hrefs as hrefs
import ieee_2030_5.models as m
from ieee_2030_5.certs import (TLSRepository, lfdi_from_fingerprint,
                               sfdi_from_lfdi)
# templates = Jinja2Templates(directory="templates")
from ieee_2030_5.config import ServerConfiguration
from ieee_2030_5.data.indexer import get_href, get_href_all_names
from ieee_2030_5.models import DeviceCategoryType
from ieee_2030_5.server.admin_endpoints import AdminEndpoints
from ieee_2030_5.server.server_constructs import EndDevices, get_groups
from ieee_2030_5.server.server_endpoints import ServerEndpoints

_log = logging.getLogger(__file__)


class LogProtocolHandler(logging.Handler):

    def __init__(self, level=0) -> None:
        super().__init__(level)
        super().setFormatter('%(message)s')

    def emit(self, record: logging.LogRecord) -> None:
        pass    # super().handle(record)


_log_protocol = logging.getLogger("protocol")
_log_protocol.addHandler(LogProtocolHandler(logging.DEBUG))


class PeerCertWSGIRequestHandler(werkzeug.serving.WSGIRequestHandler):
    """
    We subclass this class so that we can gain access to the connection
    property. self.connection is the underlying client socket. When a TLS
    connection is established, the underlying socket is an instance of
    SSLSocket, which in turn exposes the getpeercert() method.

    The output from that method is what we want to make available elsewhere
    in the application.
    """
    config: ServerConfiguration
    tlsrepo: TLSRepository
    reqresponse: Queue()

    @staticmethod
    @lru_cache
    def is_admin(path_info) -> bool:
        start_paths = ['/admin', '/socket-io']
        a_filter = itertools.accumulate(start_paths,
                                        lambda x: 1 if path_info.startswith(x) else 0,
                                        initial=0)
        return next(a_filter) > 0

    def make_environ(self):
        """
        The superclass method develops the environ hash that eventually
        forms part of the Flask request object.

        We allow the superclass method to run first, then we insert the
        peer certificate into the hash. That exposes it to us later in
        the request variable that Flask provides
        """
        _log.debug("Making environment")
        environ = super(PeerCertWSGIRequestHandler, self).make_environ()

        # Assume browser is being hit with things that start with /admin allow
        # a pass through from web (should be protected via auth but not right now)
        if PeerCertWSGIRequestHandler.is_admin(
                environ['PATH_INFO']) and not self.config.generate_admin_cert:
            raise werkzeug.exceptions.Forbidden()

        try:
            # For admin use the admin peer even though it's not what is sent in to the client.
            # This allows admin to login from any api, though not necessarily secure this
            # allows a way to have the admin be boxed off.
            if PeerCertWSGIRequestHandler.is_admin(environ['PATH_INFO']):
                cert, key = self.tlsrepo.get_file_pair("admin")
                x509 = OpenSSL.crypto.load_certificate(OpenSSL.crypto.FILETYPE_PEM, cert)
            else:
                x509_binary = self.connection.getpeercert(True)
                x509 = OpenSSL.crypto.load_certificate(OpenSSL.crypto.FILETYPE_ASN1, x509_binary)
            environ['ieee_2030_5_peercert'] = x509
            environ['ieee_2030_5_serial_number'] = x509.get_serial_number()
            if PeerCertWSGIRequestHandler.config.lfdi_mode == "lfdi_mode_from_file":
                _log.debug("Using hash from combined file.")
                pth = PeerCertWSGIRequestHandler.tlsrepo.__get_combined_file__(x509.get_subject().CN)
                sha256hash = hashlib.sha256(pth.read_text().encode('utf-8')).hexdigest()
                environ['ieee_2030_5_lfdi'] = lfdi_from_fingerprint(sha256hash)
            else:
                environ['ieee_2030_5_lfdi'] = lfdi_from_fingerprint(
                    x509.digest("sha256").decode('ascii'))
            environ['ieee_2030_5_sfdi'] = sfdi_from_lfdi(environ['ieee_2030_5_lfdi'])

            _log.debug(
                f"Environment lfdi: {environ['ieee_2030_5_lfdi']} sfdi: {environ['ieee_2030_5_sfdi']}"
            )
            if not PeerCertWSGIRequestHandler.is_admin(environ['PATH_INFO']):
                found_device_id = self.tlsrepo.find_device_id_from_sfdi(
                    environ['ieee_2030_5_sfdi'])
                assert found_device_id, "Unknown device found."
        except OpenSSL.crypto.Error:
            # Only if we have a debug_device do we want to expose this device through the admin page.
            # if self.debug_device:
            #     cert_file, key_file = self.tlsrepo.get_file_pair(self.debug_device)
            #     x509 = OpenSSL.crypto.load_certificate(OpenSSL.crypto.FILETYPE_PEM, Path(cert_file).read_bytes())
            #     environ['ieee_2030_5_peercert'] = x509
            #     environ['ieee_2030_5_subject'] = x509.get_subject().CN

            # else:
            environ['peercert'] = None

        return environ


# based on
# https://stackoverflow.com/questions/19459236/how-to-handle-413-request-entity-too-large-in-python-flask-server#:~:text=server%20MAY%20close%20the%20connection,client%20from%20continuing%20the%20request.&text=time%20the%20client%20MAY%20try,you%20the%20Broken%20pipe%20error.&text=Great%20than%20the%20application%20is%20acting%20correct.
def handle_chunking():
    """
    Sets the "wsgi.input_terminated" environment flag, thus enabling
    Werkzeug to pass chunked requests as streams.  The gunicorn server
    should set this, but it's not yet been implemented.
    """

    transfer_encoding = request.headers.get("Transfer-Encoding", None)
    if transfer_encoding == u"chunked":
        request.environ["wsgi.input_terminated"] = True


def before_request():
    # if request.scheme == 'http':
    #     url = request.url.replace('http://', 'https://', 1)
    #     url = url.replace('8080', '7443')
    #     code = 301
    #     return redirect(url, code=code)
    pass
    #PeerCertWSGIRequestHandler.reqresponse.put(request)
    # _log.debug(f"HEADERS: {request.headers}")
    # _log.debug(f"REQ_path: {request.path}")
    # _log.debug(f"ARGS: {request.args}")
    # _log.debug(f"DATA: {request.get_data()}")
    # _log.debug(f"FORM: {request.form}")


def after_request(response: Response) -> Response:
    _log_protocol.debug(f"\nREQ: {request.path}")
    _log_protocol.debug(f"\nRESP HEADER: {str(response.headers).strip()}")
    _log_protocol.debug(f"\nRESP: {response.get_data().decode('utf-8')}")

    # _log.debug(f"RESP HEADERS:\n{response.headers}")
    # _log.debug(f"RESP:\n{response.get_data().decode('utf-8')}")
    return response


def __build_ssl_context__(tlsrepo: TLSRepository) -> ssl.SSLContext:
    # to establish an SSL socket we need the private key and certificate that
    # we want to serve to users.
    server_key_file = str(tlsrepo.server_key_file)
    server_cert_file = str(tlsrepo.server_cert_file)

    # in order to verify client certificates we need the certificate of the
    # CA that issued the client's certificate. In this example I have a
    # single certificate, but this could also be a bundle file.
    ca_cert = str(tlsrepo.ca_cert_file)

    # create_default_context establishes a new SSLContext object that
    # aligns with the purpose we provide as an argument. Here we provide
    # Purpose.CLIENT_AUTH, so the SSLContext is set up to handle validation
    # of client certificates.
    ssl_context = ssl.create_default_context(purpose=ssl.Purpose.CLIENT_AUTH, cafile=str(ca_cert))

    # load in the certificate and private key for our server to provide to clients.
    # force the client to provide a certificate.
    ssl_context.load_cert_chain(
        certfile=server_cert_file,
        keyfile=server_key_file,
    # password=app_key_password
    )
    # change this to ssl.CERT_REQUIRED during deployment.
    # TODO if required we have to have one all the time on the server.
    ssl_context.verify_mode = ssl.CERT_OPTIONAL    # ssl.CERT_REQUIRED
    return ssl_context


def __build_http_app__(config: ServerConfiguration) -> Flask:
    app = Flask(__name__, template_folder=str(Path(".").resolve().joinpath('templates')))
    # Debug headers path and request arguments
    app.before_request(before_request)
    # Allows for larger data to be sent through because of chunking types.
    app.before_request(handle_chunking)
    app.after_request(after_request)

    @app.route("/dcap", methods=['GET'])
    def http_root() -> Response:
        return dataclass_to_xml(m.DeviceCapability(href=f"https://localhost:7443/dcap"))
        #return adpt.DeviceCapabilityAdapter()


def __build_app__(config: ServerConfiguration, tlsrepo: TLSRepository) -> Flask:
    app = Flask(__name__, template_folder=str(Path(".").resolve().joinpath('templates')))

    # Debug headers path and request arguments
    app.before_request(before_request)
    # Allows for larger data to be sent through because of chunking types.
    app.before_request(handle_chunking)
    app.after_request(after_request)

    ServerEndpoints(app, tls_repo=tlsrepo, config=config)
    AdminEndpoints(app, tls_repo=tlsrepo, config=config)

    # TODO investigate socket-io connection here.
    # app.config['SECRET_KEY'] = 'secret!'
    # socketio = SocketIO(app)

    # @socketio.on('my event')
    # def handle_my_custom_event(json):
    #     print('received json: ' + str(json))
    #     send(f"I received: {json}")

    # now we get into the regular Flask details, except we're passing in the peer certificate
    # as a variable to the template.
    @app.route('/')
    def root():
        return redirect("/admin/index.html")
        # cert = request.environ['peercert']
        # cert_data = f"{cert.get_subject()}"
        # return render_template("admin/index.html")
        # return render_template('helloworld.html', client_cert=request.environ['peercert'])

    @app.route("/admin/index.html")
    def admin_home():
        return render_template("admin/index.html")

    @app.route("/admin/execute", methods=["get", "post"])
    def execute_method():
        if request.method == "POST":
            _log.debug("Posting stuff to server.")

        return render_template("admin/execute.html")

    @app.route("/admin/add-fsa", methods=["get", "post"])
    def admin_fsa():
        if request.method == "POST":
            return redirect("admin/index.html")

        controls, default_control = adpt.DERControlAdapter.get_all()
        return render_template("admin/add-fsa.html")

    @app.route("/admin/add-end-device", methods=["get", "post"])
    def admin_end_device():
        if request.method == "POST":
            return redirect(url_for("admin_home"))

        return render_template("admin/add-end-device.html", device_categories=DeviceCategoryType)

    @app.route("/admin/add-der-program", methods=["get", "post"])
    def admin_der_program():
        controls, default_control = adpt.DERControlAdapter.get_all()

        if request.method == "POST":
            args = request.form.to_dict()
            print(f"Args before: {args}")
            adpt.DERProgramAdapter.build(**args)
            print(f"Args after: {args}")

            return redirect(url_for("admin_home"))

        return render_template("admin/add-der-program.html",
                               der_controls=controls,
                               default_der_control=default_control)

    @app.route("/admin/default-der-control", methods=['get', 'post'])
    def admin_default_der_control():
        dderc = adpt.DERControlAdapter.fetch_default()

        if request.method == 'POST':
            kwargs = request.form.to_dict()
            # TODO: Build a helper that will allow us to populate by known form elements.
            # Helper for connect and energize mode, which are ready for usage.
            if 'enable_opModConnect' not in kwargs:
                kwargs['enable_opModConnect'] = 'off'
            
            if 'enable_opModEnergize' not in kwargs:
                kwargs['enable_opModEnergize'] = 'off'

            field_list = fields(dderc)
            base_control = dderc.DERControlBase
            for k, v in kwargs.items():
                if k.startswith('enable_'):
                    k = k.split('_')[1]
                    v = True if v == 'on' else False

                for f in field_list:
                    if k == f.name:
                        setattr(dderc, k, v)
                for f in fields(base_control):
                    if k == f.name:
                        setattr(base_control, k, v)

            adpt.DERControlAdapter.store_default(dderc=dderc)

            return redirect(url_for("admin_home"))

        return render_template("admin/update-default-der-control.html", dderc=dderc)

    @app.route("/admin/resources")
    def admin_resource_list():
        resource = request.args.get("rurl")
        obj = get_href(resource)
        all_resources = sorted(get_href_all_names())
        if obj:
            return render_template("admin/resource_list.html",
                                   resource_urls=all_resources,
                                   href_shown=resource,
                                   object=dataclass_to_xml(obj))
        else:
            return render_template("admin/resource_list.html", resource_urls=all_resources)

    @app.route("/admin/clients")
    def admin_clients():
        clients = tlsrepo.client_list
        return render_template("admin/clients.html", registered=clients, connected=[])

    @app.route("/admin/clients/dcap/<int:index>")
    def admin_clients_dcap(index: int = hrefs.NO_INDEX):
        clients = tlsrepo.client_list
        return render_template("admin/clients.html", registered=clients, connected=[])

    @app.route("/admin/groups")
    def admin_groups():
        groups = get_groups()
        return render_template("admin/groups.html", groups=groups)

    @app.route("/admin/aggregators")
    def admin_aggregators():
        return Response("<h1>Aggregators</h1>")

    @app.route("/admin/routes")
    def admin_routes():
        routes = '<ul>'
        for p in app.url_map.iter_rules():
            routes += f"<li>{p.rule}</li>"
        routes += "</ul>"
        return Response(f"{routes}")

    return app


def run_app(app: Flask, host, ssl_context, request_handler, port, **kwargs):    
    app.run(host=host,
            ssl_context=ssl_context,
            request_handler=request_handler,
            port=port,
            **kwargs)


def run_server(config: ServerConfiguration, tlsrepo: TLSRepository, enddevices: EndDevices,
               **kwargs):
    app = __build_app__(config, tlsrepo)
    ssl_context = __build_ssl_context__(tlsrepo)

    try:
        host, port = config.server_hostname.split(":")
    except ValueError:
        # host and port not available
        host = config.server_hostname
        port = 8443

    if config.http_port is not None:
        http_app = __build_http_app__(config=config)

    PeerCertWSGIRequestHandler.config = config
    PeerCertWSGIRequestHandler.tlsrepo = tlsrepo

    run_app(app=app, host=host, ssl_context=ssl_context, port=port, request_handler=PeerCertWSGIRequestHandler, **kwargs)
    

def build_server(config: ServerConfiguration, tlsrepo: TLSRepository, **kwargs) -> BaseWSGIServer:

    app = __build_app__(config, tlsrepo)
    ssl_context = __build_ssl_context__(tlsrepo)

    try:
        host, port = config.server_hostname.split(":")
    except ValueError:
        # host and port not available
        host = config.server_hostname
        port = 8443
        
    PeerCertWSGIRequestHandler.config = config
    PeerCertWSGIRequestHandler.tlsrepo = tlsrepo

    return make_server(app=app,
                       host=host,
                       ssl_context=ssl_context,
                       request_handler=PeerCertWSGIRequestHandler,
                       port=port,
                       **kwargs)
