import json
from typing import Optional

from flask import Flask, Response, render_template, request

import ieee_2030_5.hrefs as hrefs
import ieee_2030_5.models as m
from ieee_2030_5.adapters import Adapter
from ieee_2030_5.adapters.der import DERProgramAdapter
from ieee_2030_5.adapters.enddevices import EndDeviceAdapter
from ieee_2030_5.adapters.fsa import FSAAdapter
from ieee_2030_5.certs import TLSRepository
from ieee_2030_5.config import ServerConfiguration
from ieee_2030_5.server.server_constructs import EndDevices
from ieee_2030_5.utils import dataclass_to_xml, xml_to_dataclass


class AdminEndpoints:
    def __init__(self, app: Flask, tls_repo: TLSRepository, config: ServerConfiguration):
        self.tls_repo = tls_repo
        self.server_config = config
        
        app.add_url_rule("/admin", view_func=self._admin)
        app.add_url_rule("/admin/enddevices/<int:index>", view_func=self._admin_enddevices)    
        app.add_url_rule("/admin/enddevices", view_func=self._admin_enddevices)
        app.add_url_rule("/admin/end-device-list", view_func=self._admin_enddevice_list)
        app.add_url_rule("/admin/program-lists", view_func=self._admin_der_program_lists)
        app.add_url_rule("/admin/lfdi", endpoint="admin/lfdi", view_func=self._lfdi_lists)
        app.add_url_rule("/admin/edev/<int:edev_index>/ders/<int:der_index>/current_derp", view_func=self._admin_der_update_current_derp, methods=['PUT', 'GET'])
#        app.add_url_rule("/admin/ders/<int:edev_index>", view_func=self._admin_ders)
        
        # COMPLETE
        app.add_url_rule("/admin/edev/<int:edevid>/fsa/<int:fsaid>/derp", view_func=self._admin_edev_fsa_derp)
        app.add_url_rule("/admin/edev/<int:edevid>/fsa/<int:fsaid>", view_func=self._admin_edev_fsa)
        app.add_url_rule("/admin/edev/<int:edevid>/fsa", view_func=self._admin_edev_fsa)
        app.add_url_rule("/admin/edev/<int:edevid>/der", view_func=self._admin_edev_ders)
        app.add_url_rule("/admin/edev/<int:edevid>/der/<int:derid>/current_derp", view_func=self._admin_edev_ders)
        app.add_url_rule("/admin/edev/<int:edevid>/der/<int:derid>", view_func=self._admin_edev_ders)
        app.add_url_rule("/admin/edev", view_func=self._admin_edev)
        # END COMPLETE
        
        app.add_url_rule("/admin/derp/<int:derp_index>/derc/<int:control_index>",  methods=['GET', 'PUT'], view_func=self._admin_derp_derc)
        app.add_url_rule("/admin/derp/<int:derp_index>/derc",  methods=['GET', 'POST'], view_func=self._admin_derp_derc)
        app.add_url_rule("/admin/derp/<int:derp_index>/derca",  methods=['GET'], view_func=self._admin_derp_derca)
        app.add_url_rule("/admin/derp/<int:derp_index>/dderc",  methods=['GET', 'PUT'], view_func=self._admin_derp_derc)
        app.add_url_rule("/admin/derp",  methods=['GET', 'POST'], view_func=self._admin_derp)
        #app.add_url_rule("/admin/derp/<int:index>",  methods=['GET', 'POST'], view_func=self._derp)
        #app.add_url_rule("/admin/derp/<int:index>/derc", methods=['GET', 'POST'], view_func=self._derp_derc)
        
    # def _admin_edev_fsa(self, edevid: int, fsaid: int = -1, derc: int = -1) -> Response:
    #     #edev = EndDeviceAdapter.fetch_at(edevid)
        
    #     if fsaid > -1 and derc > -1:
            
            
        #fsa = FSAAdapter.fetch_by_end_device(edevid)
        
    def _admin_edev(self) -> Response:
        return Response(dataclass_to_xml(EndDeviceAdapter.fetch_all(m.EndDeviceList())))

    def _admin_edev_ders(self, edevid: int, derid: int = None) -> Response:
        ed = EndDeviceAdapter.fetch(edevid)
        deradpter: Adapter[m.DER] = EndDeviceAdapter.fetch_child(ed, hrefs.DER)
        if derid:
            retval: m.DER = deradpter.fetch(derid)
            if request.path.endswith('current_derp'):
                derp_href = hrefs.DERProgramHref.parse(retval.CurrentDERProgramLink)
                retval = DERProgramAdapter.fetch(derp_href.index)
        else:
            retval = deradpter.fetch_all(m.DERList())
            
        
        return Response(dataclass_to_xml(retval))
    
    def _admin_edev_fsa(self, edevid: int, fsaid: int = -1) -> Response:
        if edevid > -1 and fsaid > -1:
            obj = EndDeviceAdapter.fetch_fsa(edev_index=edevid, fsa_index=fsaid)
        elif edevid > -1:
            obj = EndDeviceAdapter.fetch_fsa_list(edev_index=edevid)
        else:
            return Response("Invalid edevid specified", status=400)
        
        return Response(dataclass_to_xml(obj))
    
    def _admin_edev_fsa_derp(self, edevid: int, fsaid: int) -> Response:
        derps = EndDeviceAdapter.fetch_derp_list(edev_index=edevid, fsa_index=fsaid)
        return Response(dataclass_to_xml(derps))
        
    def _admin_der_program_lists(self) -> Response:
        return Response(dataclass_to_xml(DERProgramAdapter.fetch_list()))
    
    # def _admin_ders(self, edev_index: int) -> Response:
    #     return Response(dataclass_to_xml(DERAdapter.fetch_list(edev_index=edev_index)))
    
    # def _der_settings(self, edev_index: int, der_index: int):
    #     return Response(dataclass_to_xml(DERAdapter.fetch_settings_at(edev_index=edev_index, der_index=der_index)))
        
    def _admin_der_update_current_derp(self, edev_index: int, der_index: int):
        if request.method == 'PUT':
            data: m.DERProgram = xml_to_dataclass(request.data.decode('utf-8'))
            if not isinstance(data, m.DERProgram):
                return Response(status=400)
            
            if data.mRID:
                program = DERProgramAdapter.fetch_by_mrid(data.mRID)
                response_status = 200
                if not program:
                    program = DERProgramAdapter.create(data).data
                    response_status = 201
            else:
                program = DERProgramAdapter.create(data).data
                response_status = 201
            print(EndDeviceAdapter.fetch_child_names())
            der = DERAdapter.fetch_at(edev_index, der_index)
            der.CurrentDERProgramLink = m.CurrentDERProgramLink(program.href)
            return Response(dataclass_to_xml(program), status=response_status)
        else:
            der = DERAdapter.fetch_at(edev_index, der_index)
            if der.CurrentDERProgramLink:
                parsed = hrefs.der_program_parse(der.CurrentDERProgramLink.href)
                program = DERProgramAdapter.fetch_at(parsed.index)
            else:
                program = m.DERProgram()
            
            return Response(dataclass_to_xml(program))
            
            
        
        
    def _admin_derp(self, index: int = -1) -> Response:
        if request.method == 'GET' and index < 0:
            return Response(dataclass_to_xml(DERProgramAdapter.fetch_all(m.DERProgramList())))
        elif request.method == 'GET':
            return Response(dataclass_to_xml(DERProgramAdapter.fetch_at(index)))
        
        if request.method == 'POST':
            xml = request.data.decode('utf-8')
            data = xml_to_dataclass(request.data.decode('utf-8'))
            
            response = DERProgramAdapter.create(data)
            
            return Response(headers={'Location': response.href}, status=response.statusint)
            
            
        return Response(f"I am {index}, {request.method}")

    def _admin_derp_derca(self, derp_index: int) -> Response:
        ctrl_list = DERProgramAdapter.fetch_der_active_control_list(derp_index)
        return Response(dataclass_to_xml(ctrl_list))
        
    def _admin_derp_derc(self, derp_index: int) -> Response:
        derp = DERProgramAdapter.fetch(derp_index)
        
        if request.method == "POST":
            xml = request.data.decode('utf-8')
            data = xml_to_dataclass(request.data.decode('utf-8'))
            
            if isinstance(data, m.DefaultDERControl):
                status_code = 201
                # data.href = hrefs.der_program_href(derp_index, hrefs.DERProgramSubType.DefaultDERControlLink)
                if DERProgramAdapter.size_children(derp, hrefs.DDERC) > 0:
                    status_code = 204
                    DERProgramAdapter.remove_child(derp, hrefs.DDERC)
                
                DERProgramAdapter.add_replace_child(derp, hrefs.DDERC, data)
                
                return Response(headers={'Location': data.href}, status=status_code)
            elif isinstance(data, m.DERControl):
                status_code = 201
                # data.href = hrefs.der_program_href(derp_index, hrefs.DERProgramSubType.DERControlListLink)
                try:
                    index = DERProgramAdapter.fetch_child_index_by_mrid(derp, hrefs.DERC, data.mRID)
                    DERProgramAdapter.replace_child(derp, hrefs.DERC, index, data)
                    status_code = 204
                except KeyError:
                    DERProgramAdapter.add_replace_child(derp, hrefs.DERC, data)
                                        
                return Response(headers={'Location': data.href}, status=status_code)
        
        if request.path.endswith("dderc"):
            results = DERProgramAdapter.fetch_child(derp_index, "dderc")
        elif request.path.endswith("derc"):
            results = DERProgramAdapter.fetch_children(derp, "derc", m.DERControlList(href=request.path))
        elif request.path.endswith("derca"):
            results = DERProgramAdapter.fetch_children(derp, "derca", m.DERControlList(href=request.path))
            
        return Response(dataclass_to_xml(results))
        

    def _admin(self) -> Response:
        arg_path = request.args.get('path')
        device = request.args.get('device')
        
        if arg_path == '/enddevices':
            return Response(dataclass_to_xml(EndDeviceAdapter.fetch_list()))
        
        if arg_path.startswith('/edev'):
            edev_path = hrefs.edev_parse(arg_path)
            if edev_path.der_index == hrefs.NO_INDEX:
                return Response(dataclass_to_xml(DERAdapter.fetch_list(edev_index=edev_path.edev_index)))
            elif edev_path.der_sub is None:
                return Response(dataclass_to_xml(DERAdapter.fetch_at(edev_index=edev_path.edev_index, der_index=edev_path.der_index)))
            elif edev_path.der_sub == hrefs.DERSubType.CurrentProgram.value:
                return Response(dataclass_to_xml(DERAdapter.fetch_current_program_at(edev_index=edev_path.edev_index, der_index=edev_path.der_index)))
            
        elif arg_path.startswith("/fsa"):
            
            fsa_path = hrefs.fsa_parse(arg_path)
            
            if fsa_path.fsa_index == hrefs.NO_INDEX:
                return Response(dataclass_to_xml(FSAAdapter.fetch_list()))
            elif fsa_path.fsa_index != hrefs.NO_INDEX and fsa_path.fsa_sub is None:
                return Response(dataclass_to_xml(FSAAdapter.fetch_at(fsa_path.fsa_index)))
            else:
                return Response(dataclass_to_xml(FSAAdapter.fetch_program_list(fsa_path.fsa_index)))
            
                
        
        
        

    def _admin_enddevices(self, index:int = None) -> Response:
        
        return Response(dataclass_to_xml(EndDeviceAdapter.fetch_all(m.EndDeviceList())))
    
    def _lfdi_lists(self) -> Response:
        items = []

        for k, v in self.end_devices.__all_end_devices__.items():
            items.append({"key": k, "lfdi": int(v.end_device.lFDI)})

        return Response(json.dumps(items))

    # def _admin_edev_fsa(self, edevid: int, fsaid: int = -1) -> Response:
    #     #edev = self.end_devices.get(edevid)
    #     return Response(json.dumps(json.dumps(self.end_devices.get_fsa_list(edevid=edevid))))

    def _program_lists(self) -> str:
        return render_template("admin/program-lists.html",
                               program_lists=self.server_config.program_lists)

    def _admin_enddevice_list(self) -> str:
        return render_template("admin/end-device-list.html",
                               end_device_list=self.end_devices.get_end_devices())
