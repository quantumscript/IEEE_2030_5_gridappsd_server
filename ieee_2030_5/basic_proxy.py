from __future__ import annotations

import logging
import os
import ssl
from dataclasses import dataclass
from http.client import HTTPSConnection
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Tuple
from urllib.parse import urlparse

import OpenSSL
import yaml

from ieee_2030_5.certs import (TLSRepository, lfdi_from_fingerprint,
                               sfdi_from_lfdi)
from ieee_2030_5.config import ServerConfiguration

_log = logging.getLogger(__name__)


@dataclass
class ContextWithPaths:
    context: ssl.SSLContext
    certpath: str
    keypath: str


class RequestForwarder(BaseHTTPRequestHandler):

    def get_context_cert_pair(self) -> ContextWithPaths:
        x509_binary = self.connection.getpeercert(True)
        cert_file = None
        key_file = None
        if x509_binary:
            x509 = OpenSSL.crypto.load_certificate(OpenSSL.crypto.FILETYPE_ASN1, x509_binary)
            # subject = x509.get_subject().CN
            # serial_num = x509.get_serial_number()
            # fingerprint = x509.digest("sha256").decode("ascii")
            # _log.info(f"Connected using fingerprint: {fingerprint}")
            # lfdi = lfdi_from_fingerprint(fingerprint)
            # _log.info(f"LFDI -> {lfdi}")
            # sfdi = sfdi_from_lfdi(lfdi)
            # _log.info(f"SFDI -> {sfdi}")
            cn = x509.get_subject().CN
            cert_file, key_file = self.server.tls_repo.get_file_pair(cn)

        context = ssl.SSLContext(ssl.PROTOCOL_TLS)
        context.verify_mode = ssl.CERT_OPTIONAL

        # context.load_verify_locations(cafile="/home/gridappsd/tls/certs/ca.crt")
        assert cert_file
        ca_file = str(Path(cert_file).parent.joinpath("ca.pem"))
        context.load_verify_locations(cafile=ca_file)
        if cert_file is not None and key_file is not None and \
                Path(cert_file).exists() and Path(key_file).exists():
            context.load_cert_chain(certfile=cert_file, keyfile=key_file)
        return ContextWithPaths(context=context, certpath=cert_file, keypath=key_file)

    def __start_request__(self) -> HTTPSConnection:
        ccp = self.get_context_cert_pair()

        host, port = self.server.proxy_target
        conn = HTTPSConnection(host=host, port=port, context=ccp.context)
        conn.connect()
        return conn

    def __handle_response__(self, conn: HTTPSConnection):

        response = conn.getresponse()
        data = response.read()

        _log.debug(f"Response from server:\n{data}")
        self.wfile.write(f'HTTP/1.1 {response.status}\n'.encode('utf-8'))

        for k, v in response.headers.items():

            if k not in ('Connection', ):
                if k == 'Content-Length':
                    self.send_header(k, str(len(data)))
                else:
                    self.send_header(k, v)
        self.end_headers()

        # self.wfile.write(data)
        # self.send_response(response.status, data.decode("utf-8"))
        self.wfile.write(data)
        self.close_connection = False
        return response

    def do_GET(self):
        

        conn = self.__start_request__()

        conn.request(method="GET", url=self.path, headers=self.headers, encode_chunked=True)

        response = self.__handle_response__(conn)
        _log.info(f"GET {self.path} Content-Length: {self.headers.get('Content-Length')}, Response Status: {response.status}")

    def do_POST(self):
        _log.info(f"POST {self.path} Content-Length: {self.headers.get('Content-Length')}")

        conn = self.__start_request__()
        read_data = self.rfile.read(int(self.headers.get('Content-Length')))

        conn.request(method="POST",
                     url=self.path,
                     headers=self.headers,
                     body=read_data,
                     encode_chunked=True)

        response = self.__handle_response__(conn)
        _log.info(f"POST {self.path} Content-Length: {self.headers.get('Content-Length')}, Response Status: {response.status}")
        
    def do_DELETE(self):
        _log.info(f"DELETE {self.path} Content-Length: {self.headers.get('Content-Length')}")

        conn = self.__start_request__()
        read_data = self.rfile.read(int(self.headers.get('Content-Length')))

        conn.request(method="DELETE",
                     url=self.path,
                     headers=self.headers,
                     body=read_data,
                     encode_chunked=True)

        response = self.__handle_response__(conn)
        _log.info(f"DELETE {self.path} Content-Length: {self.headers.get('Content-Length')}, Response Status: {response.status}")
        
    def do_PUT(self):
        _log.info(f"PUT {self.path} Content-Length: {self.headers.get('Content-Length')}")

        conn = self.__start_request__()
        read_data = self.rfile.read(int(self.headers.get('Content-Length')))

        conn.request(method="PUT",
                     url=self.path,
                     headers=self.headers,
                     body=read_data,
                     encode_chunked=True)

        response = self.__handle_response__(conn)
        _log.info(f"PUT {self.path} Content-Length: {self.headers.get('Content-Length')}, Response Status: {response.status}")


class ProxyServer(HTTPServer):

    def __init__(self, tls_repo: TLSRepository, proxy_target: Tuple[str, int], **kwargs):
        super().__init__(**kwargs)
        self._tls_repo = tls_repo
        self._proxy_target = proxy_target

    @property
    def proxy_target(self) -> Tuple[str, int]:
        return self._proxy_target

    @property
    def tls_repo(self) -> TLSRepository:
        return self._tls_repo


def start_proxy(server_address: Tuple[str, int], tls_repo: TLSRepository,
                proxy_target: Tuple[str, int]):
    logging.getLogger().info(f"Serving {server_address} proxied to {proxy_target}")
    RequestForwarder.protocol_version = "HTTP/1.1"
    httpd = ProxyServer(server_address=server_address,
                        proxy_target=proxy_target,
                        tls_repo=tls_repo,
                        RequestHandlerClass=RequestForwarder)
    # Since version 3.10: SSLContext without protocol argument is deprecated.
    # sslctx = ssl.SSLContext()
    sslctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)

    # Use optional, because we need the cert for 2030.5 but not the admin
    # interface.
    sslctx.verify_mode = ssl.CERT_OPTIONAL
    sslctx.load_verify_locations(cafile=tls_repo.ca_cert_file)

    sslctx.check_hostname = False    # If set to True, only the hostname that matches the certificate will be accepted
    sslctx.load_cert_chain(certfile=tls_repo.server_cert_file, keyfile=tls_repo.server_key_file)
    httpd.socket = sslctx.wrap_socket(httpd.socket, server_side=True)
    httpd.serve_forever()


def build_address_tuple(hostname: str) -> Tuple[str, int]:
    """Create a Tuple[str, int] from the passed hostname.

    The hostname can be formatted using https://server:port or server:port

    :param: hostname
    """
    parsed = urlparse(hostname)

    if parsed.hostname:
        hostname = (parsed.hostname, parsed.port)
    else:
        hostname = hostname.split(":")
        hostname = (hostname[0], int(hostname[1]))
    return hostname


def _main():
    import argparse

    parser = argparse.ArgumentParser()

    parser.add_argument(dest="config", help="Configuration file for the server.")
    parser.add_argument("--debug",
                        action="store_true",
                        default=False,
                        help="Turns debugging on for logging of the proxy.")

    opts = parser.parse_args()

    debug_level = logging.DEBUG if opts.debug else logging.DEBUG
    logging.basicConfig(level=debug_level)

    cfg_dict = yaml.safe_load(Path(opts.config).expanduser().resolve(strict=True).read_text())

    config = ServerConfiguration(**cfg_dict)

    tls_repo = TLSRepository(repo_dir=config.tls_repository,
                             openssl_cnffile_template=config.openssl_cnf,
                             serverhost=config.server_hostname,
                             proxyhost=config.proxy_hostname,
                             clear=False)

    proxy_host = build_address_tuple(config.proxy_hostname)
    server_host = build_address_tuple(config.server_hostname)

    _log.debug(f"Proxy host tuple: {proxy_host}")
    _log.debug(f"Server host tuple: {server_host}")

    start_proxy(server_address=(proxy_host[0], int(proxy_host[1])),
                tls_repo=tls_repo,
                proxy_target=(server_host[0], int(server_host[1])))


if __name__ == '__main__':
    _main()
