import logging
from typing import Optional

import werkzeug.exceptions
from flask import Response, request

import ieee_2030_5.hrefs as hrefs
import ieee_2030_5.models as m
from ieee_2030_5.adapters import Adapter
from ieee_2030_5.adapters.enddevices import EndDeviceAdapter
from ieee_2030_5.adapters.fsa import FSAAdapter
from ieee_2030_5.data.indexer import get_href
from ieee_2030_5.models import Registration
from ieee_2030_5.server.base_request import RequestOp
from ieee_2030_5.types_ import Lfdi
from ieee_2030_5.utils import dataclass_to_xml, xml_to_dataclass

_log = logging.getLogger(__name__)

class EDevRequests(RequestOp):
    """
    Class supporting end devices and any of the subordinate calls to it.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
    def put(self) -> Response:
        parsed = hrefs.EdevHref.parse(request.path)
        
        mysubobj = xml_to_dataclass(request.data.decode('utf-8'))
        
        
        ed = EndDeviceAdapter.fetch(parsed.edev_index)
        deradapter: Adapter[m.DER] = EndDeviceAdapter.fetch_child(ed, hrefs.DER)
        der = deradapter.fetch(parsed.edev_subtype_index)
        
        
        try:
            deradapter.fetch_child(der, parsed.edev_der_subtype.value)
            response_status = 204
        except (KeyError, IndexError):
            response_status = 201
        finally:
            if not mysubobj.href:
                mysubobj.href = request.path
            deradapter.add_replace_child(der, parsed.edev_der_subtype.value, mysubobj)
            
        return Response(status=response_status)
        # response_code = adpt.DERAdapter.store(parsed, xml_to_dataclass(request.data.decode('utf-8')))
        #return Response(status=int(response_code))                                              
                                              
                        
        
    def post(self, path: Optional[str] = None) -> Response:
        """
        Handle post request to /edev
        
        The expectation is that data will be an xml object like the following:
        
            <EndDevice xmlns="urn:ieee:std:2030.5:ns">
                <sFDI>231589308001</sFDI>
                <changedTime>0</changedTime>
            </EndDevice>
        
        Args:
            path: 

        Returns:

        """
        # request.data should have xml data.
        if not request.data:
            raise werkzeug.exceptions.Forbidden()

        ed: m.EndDevice = xml_to_dataclass(request.data.decode('utf-8'))

        if not isinstance(ed, m.EndDevice):
            raise werkzeug.exceptions.Forbidden()

        # This is what we should be using to get the device id of the registered end device.
        device_id = self.tls_repo.find_device_id_from_sfdi(ed.sFDI)
        ed.lFDI = self.tls_repo.lfdi(device_id)
        if end_device := EndDeviceAdapter.fetch_by_lfdi(ed.lfdi):
            status = 200
            ed_href = end_device.href
        else:
            if not ed.href:
                ed = EndDeviceAdapter.store(device_id, ed)

            ed_href = ed.href
            status = 201

        return Response(status=status, headers={'Location': ed_href})

    def get(self) -> Response:
        """
        Supports the get request for end_devices(EDev) and end_device_list_link.

        Paths:
            /edev
            /edev/0
            /edev/0/di
            /edev/0/rg
            /edev/0/der

        """
        _log.debug(f"Args are: {request.args}")
        edev_href = hrefs.EdevHref.parse(request.path)
        start = int(request.args.get("s", 0))
        limit = int(request.args.get("l", 1))
        after = int(request.args.get("a", 0))
        

        ed = EndDeviceAdapter.fetch_by_property('lFDI', self.lfdi)
        
        # means we don't have any /edev without any index
        if edev_href.edev_subtype is hrefs.EDevSubType.None_Available:
            retval = m.EndDeviceList(href=request.path, all=1, results=1, EndDevice=[ed])
        
        
        elif edev_href.edev_subtype is hrefs.EDevSubType.FunctionSetAssignments:
            
            fsaadpt: FSAAdapter = EndDeviceAdapter.fetch_child(ed, hrefs.FSA, edev_href.edev_index)
            
            if edev_href.edev_subtype_index == hrefs.NO_INDEX:
                retval = fsaadpt.fetch_all(m.FunctionSetAssignmentsList(href=request.path), start=start, after=after, limit=limit)
            else:
                retval = fsaadpt.fetch(edev_href.edev_subtype_index)
                
            
            # if edev_href.edev_subtype_index == hrefs.NO_INDEX:
            #     retval = EndDeviceAdapter.fetch_children(m.DERList(request.path), hrefs.DERSubType)
            # else:
            #     retval = EndDeviceAdapter.fetch_child(ed, hrefs.FSA, edev_href.edev_subtype_index)
                
        # we have /edev_index_der or /edev_index_der_subindex or /edev_index_der_subindex_dersubtype
        elif edev_href.edev_subtype == hrefs.EDevSubType.DER:
        
            deradpt: Adapter[m.DER] = EndDeviceAdapter.fetch_child(ed, hrefs.DER, edev_href.edev_index)
                        
            if edev_href.edev_subtype_index == hrefs.NO_INDEX:
                retval = deradpt.fetch_all(m.DERList(href=request.path), start=start, after=after, limit=limit)
            else:
                der = deradpt.fetch(edev_href.edev_subtype_index)
                if edev_href.edev_der_subtype is hrefs.DERSubType.None_Available:
                    retval = der
                else:
                    retval = deradpt.fetch_child(der, edev_href.edev_der_subtype.value)
        
            # try:
            #     ed = EndDeviceAdapter.fetch(int(pth_split[1]))
            #     # FSA is a list off the end device, the rest are singleton items.
            #     if pth_split[2] == hrefs.FSA:                   
            #         retval = EndDeviceAdapter.fetch_children(ed, hrefs.FSA, m.FunctionSetAssignmentsList(href=request.path))
            #     elif pth_split[2] == hrefs.DER:
            #         deradpt = EndDeviceAdapter.fetch_child(ed, hrefs.DER, )
            #         retval = EndDeviceAdapter.fetch_children(ed, hrefs.DER, m.DERList(href=request.path))
            #     else:
            #         retval = EndDeviceAdapter.fetch_child(ed, pth_split[2], 0)
            # except KeyError:
            #     raise werkzeug.exceptions.NotFound("Missing Resource")
            
        else:
            retval = EndDeviceAdapter.fetch_child(ed, edev_href.edev_subtype.value)
            # if pth_split[2] == "rg":
            #     retval = EndDeviceAdapter.fetch_registration(edev_index=int(pth_split[1]))
            # elif pth_split[2] == "di":
            #     retval = "foo"
            # elif pth_split[2] == "fsa":
            #     retval = EndDeviceAdapter.fetch_fsa_list(edev_index=int(pth_split[1]))
            # elif pth_split[2] == "der":
            #     retval = adpt.DERAdapter.fetch_list(edev_index=int(pth_split[1]))
            
        return self.build_response_from_dataclass(retval)


class SDevRequests(RequestOp):
    """
    SelfDevice is an alias for the end device of a client.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def get(self) -> Response:
        """
        Supports the get request for end_devices(EDev) and end_device_list_link.

        Paths:
            /sdev

        """
        end_device = self._end_devices.get_end_device_list(self.lfdi).EndDevice[0]
        return self.build_response_from_dataclass(end_device)

class FSARequests(RequestOp):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
    def get(self):
        """ Retrieve a FSA or Program List
        """
        
        fsa_href = hrefs.fsa_parse(request.path)
        
        if fsa_href.fsa_index == hrefs.NO_INDEX:
            retval = FSAAdapter.fetch_all(m.FunctionSetAssignmentsList(), "FunctionSetAssignments")
        elif fsa_href.fsa_sub == hrefs.FSASubType.DERProgram.value:
            fsa = FSAAdapter.fetch(fsa_href.fsa_index)
            retval = FSAAdapter.fetch_children(fsa, "fsa", m.DERProgramList())
            # retval = FSAAdapter.fetch_children_list_container(fsa_href.fsa_index, m.DERProgram, m.DERProgramList(href="/derp"), "DERProgram")
        else:
            retval = FSAAdapter.fetch(fsa_href.fsa_index)
            
        # pth_split = request.path.split(hrefs.SEP)
        
        
        # if len(pth_split) == 1:
        #     retval = FSAAdapter.fetch_list()
        # elif len(pth_split) == 2:
        #     retval = FSAAdapter.fetch_at(int(pth_split[1]))
        # elif len(pth_split) == 3:
        #     retval = EndDeviceAdapter.fetch_fsa_list(edev_index=int(pth_split[1]))
        # elif len(pth_split) == 4:
        #     retval = EndDeviceAdapter.fetch_fsa(edev_index=int(pth_split[1]), fsa_index=int(pth_split[3]))
        # else:
        #     raise ValueError(f"Path split is {pth_split}")
            
        return self.build_response_from_dataclass(retval)