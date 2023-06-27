# -------------------------------------------------------------------------------
# Copyright (c) 2022, Battelle Memorial Institute All rights reserved.
# Battelle Memorial Institute (hereinafter Battelle) hereby grants permission to any person or entity
# lawfully obtaining a copy of this software and associated documentation files (hereinafter the
# Software) to redistribute and use the Software in source and binary forms, with or without modification.
# Such person or entity may use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
# the Software, and may permit others to do so, subject to the following conditions:
# Redistributions of source code must retain the above copyright notice, this list of conditions and the
# following disclaimers.
# Redistributions in binary form must reproduce the above copyright notice, this list of conditions and
# the following disclaimer in the documentation and/or other materials provided with the distribution.
# Other than as used herein, neither the name Battelle Memorial Institute or Battelle may be used in any
# form whatsoever without the express written consent of Battelle.
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY
# EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF
# MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL
# BATTELLE OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY,
# OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE
# GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED
# AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
# NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED
# OF THE POSSIBILITY OF SUCH DAMAGE.
# General disclaimer for use with OSS licenses
#
# This material was prepared as an account of work sponsored by an agency of the United States Government.
# Neither the United States Government nor the United States Department of Energy, nor Battelle, nor any
# of their employees, nor any jurisdiction or organization that has cooperated in the development of these
# materials, makes any warranty, express or implied, or assumes any legal liability or responsibility for
# the accuracy, completeness, or usefulness or any information, apparatus, product, software, or process
# disclosed, or represents that its use would not infringe privately owned rights.
#
# Reference herein to any specific commercial product, process, or service by trade name, trademark, manufacturer,
# or otherwise does not necessarily constitute or imply its endorsement, recommendation, or favoring by the United
# States Government or any agency thereof, or Battelle Memorial Institute. The views and opinions of authors expressed
# herein do not necessarily state or reflect those of the United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY operated by BATTELLE for the
# UNITED STATES DEPARTMENT OF ENERGY under Contract DE-AC05-76RL01830
# -------------------------------------------------------------------------------

import logging
import os
import socket
import sys
import threading
from argparse import ArgumentParser
from multiprocessing import Process
from pathlib import Path
from time import sleep

import yaml
from werkzeug.serving import BaseWSGIServer

import ieee_2030_5.hrefs as hrefs
from ieee_2030_5.certs import TLSRepository
from ieee_2030_5.config import InvalidConfigFile, ServerConfiguration
from ieee_2030_5.data.indexer import add_href
from ieee_2030_5.flask_server import run_server
from ieee_2030_5.server.server_constructs import initialize_2030_5

_log = logging.getLogger()


class ServerThread(threading.Thread):

    def __init__(self, server: BaseWSGIServer):
        threading.Thread.__init__(self, daemon=True)
        self.server = server

    def run(self):
        _log.info(f'starting server on {self.server.host}:{self.server.port}')
        self.server.serve_forever()

    def shutdown(self):
        _log.info("shutting down server")
        self.server.shutdown()


def get_tls_repository(cfg: ServerConfiguration,
                       create_certificates_for_devices: bool = True) -> TLSRepository:
    tlsrepo = TLSRepository(cfg.tls_repository,
                            cfg.openssl_cnf,
                            cfg.server_hostname,
                            cfg.proxy_hostname,
                            clear=create_certificates_for_devices,
                            generate_admin_cert=cfg.generate_admin_cert)

    if create_certificates_for_devices:
        already_represented = set()

        # registers the devices, but doesn't initialize_device the end devices here.
        for k in cfg.devices:
            if k in already_represented:
                _log.error(f"Already have {k.id} represented by {k.device_category_type}")
            else:
                already_represented.add(k)
                tlsrepo.create_cert(k.id)
                _log.debug(
                    f"for {k.id}\nlfdi -> {tlsrepo.lfdi(k.id)}\nsfdi -> {tlsrepo.sfdi(k.id)}")
    return tlsrepo


def _shutdown():
    make_stop_file()
    sleep(1)
    remove_stop_file()


def should_stop():
    return Path('server.stop').exists()


def make_stop_file():
    with open('server.stop', 'w') as w:
        pass


def remove_stop_file():
    pth = Path('server.stop')
    if pth.exists():
        os.remove(pth)


def _run_ui():
    
    os.system('python gui/spa/main.py')
    

def _main():
    parser = ArgumentParser()

    parser.add_argument(dest="config", help="Configuration file for the server.")
    parser.add_argument("--no-validate",
                        action="store_true",
                        help="Allows faster startup since the resolving of addresses is not done!")
    parser.add_argument(
        "--no-create-certs",
        action="store_true",
        help="If specified certificates for for client and server will not be created.")
    parser.add_argument("--debug", action="store_true", help="Debug level of the server")
    parser.add_argument("--production",
                        action="store_true",
                        default=False,
                        help="Run the server in a threaded environment.")
    opts = parser.parse_args()

    logging_level = logging.DEBUG if opts.debug else logging.INFO
    logging.basicConfig(level=logging_level)

    os.environ["IEEE_2030_5_CONFIG_FILE"] = str(
        Path(opts.config).expanduser().resolve(strict=True))

    cfg_dict = yaml.safe_load(Path(opts.config).expanduser().resolve(strict=True).read_text())

    config = ServerConfiguration(**cfg_dict)

    if config.lfdi_mode == "lfdi_mode_from_file":
        os.environ["IEEE_2030_5_CERT_FROM_COMBINED_FILE"] = '1'

    assert config.tls_repository
    assert len(config.devices) > 0
    assert config.server_hostname

    add_href(hrefs.get_server_config_href(), config)
    unknown = []
    # Only check for resolvability if not passed --no-validate
    if not opts.no_validate:
        _log.debug("Validating hostnames and/or ip of devices are resolvable.")
        for i in range(len(config.devices)):
            assert config.devices[i].hostname

            try:
                socket.gethostbyname(config.devices[i].hostname)
            except socket.gaierror:
                if hasattr(config.devices[i], "ip"):
                    try:
                        socket.gethostbyname(config.devices[i].ip)
                    except socket.gaierror:
                        unknown.append(config.devices[i].hostname)
                else:
                    unknown.append(config.devices[i].hostname)

    if unknown:
        _log.error("Couldn't resolve the following hostnames.")
        for host in unknown:
            _log.error(host)
        sys.exit(1)

    create_certs = not opts.no_create_certs
    tls_repo = get_tls_repository(config, create_certs)

    # Initialize the repository of 2030.5 devices.
    end_devices = initialize_2030_5(config, tls_repo)

    #if not opts.production:
    try:
        # p = Process(target = _run_ui)
        # p.daemon = True
        # p.start()
                
        run_server(config,
                    tls_repo,
                    end_devices,
                    debug=opts.debug,
                    use_reloader=True,
                    use_debugger=opts.debug,
                    threaded=False)
    except KeyboardInterrupt:
        _log.info("Shutting down server")
    # else:
    #     server = build_server(config, tls_repo, enddevices=end_devices)

    #     thread = None
    #     try:
    #         remove_stop_file()
    #         thread = ServerThread(server)
    #         thread.start()
    #         while not should_stop():
    #             sleep(0.5)
    #     except KeyboardInterrupt as ex:
    #         _log.info("Exiting program.")
    #     finally:
    #         if thread:
    #             thread.shutdown()
    #             thread.join()


if __name__ == '__main__':
    try:
        _main()
    except InvalidConfigFile as ex:
        print(ex.args[0])
    except KeyboardInterrupt:
        pass
