from typing import Optional

from flask import Response, request

import ieee_2030_5.adapters as adpt
import ieee_2030_5.hrefs as hrefs
import ieee_2030_5.models as m
from ieee_2030_5.server.base_request import RequestOp


class DERRequests(RequestOp):
    """
    Class supporting end devices and any of the subordinate calls to it.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def get(self) -> Response:
        
        if not request.path.startswith(hrefs.DEFAULT_DER_ROOT):
            raise ValueError(f"Invalid path for {self.__class__} {request.path}")
        
        pth_split = request.path.split(hrefs.SEP)
        
        if len(pth_split) == 1:
            # TODO Add arguments
            value = adpt.DERAdapter.fetch_list()
        else:
            value = adpt.DERAdapter.fetch_at(int(pth_split[1]))

        return self.build_response_from_dataclass(value)
    

class DERProgramRequests(RequestOp):
    """
    Class supporting end devices and any of the subordinate calls to it.
    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def get(self) -> Response:
        
        if not request.path.startswith(hrefs.DEFAULT_DERP_ROOT):
            raise ValueError("Invalid path passed to")
        
        derp_href = hrefs.DERProgramHref.parse(request.path)
        if derp_href.index == hrefs.NO_INDEX:
            retval = adpt.DERProgramAdapter.fetch_all(m.DERProgramList(href=request.path))
        
        else:
            derp = adpt.DERProgramAdapter.fetch(derp_href.index)
            
            if derp_href.derp_subtype == hrefs.DERProgramSubType.DERControlListLink:
                if derp_href.derp_subtype_index == hrefs.NO_INDEX:
                    retval = adpt.DERProgramAdapter.fetch_children(derp, hrefs.DERC, m.DERControlList(href=request.path))    
                else:
                    retval = adpt.DERProgramAdapter.fetch_child(derp, hrefs.DERC, derp_href.derp_subtype_index )    
            elif derp_href.derp_subtype == hrefs.DERProgramSubType.ActiveDERControlListLink:
                retval = adpt.DERProgramAdapter.fetch_children(derp, hrefs.DERCA, m.DERControlList(href=request.path))    
            # elif derp_href.der_subtype == hrefs.DERProgramSubType.DERCurveListLink:
            #     retval = adpt.DERProgramAdapter.fetch_der_ _active_control_list(derp_href.index)
            elif derp_href.derp_subtype == hrefs.DERProgramSubType.DefaultDERControlLink:
                retval = adpt.DERProgramAdapter.fetch_child(derp, hrefs.DDERC)
            else:
                raise ValueError(f"Found derph {derp_href}")
        
        return self.build_response_from_dataclass(retval)
    
