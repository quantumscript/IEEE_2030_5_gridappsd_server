import logging
import uuid
from ast import Dict
from datetime import datetime
from typing import List

import ieee_2030_5.hrefs as hrefs
import ieee_2030_5.models as m
from ieee_2030_5.adapters import (Adapter, AdapterListProtocol, BaseAdapter,
                                  ready_signal)
from ieee_2030_5.adapters.der import DERProgramAdapter
from ieee_2030_5.adapters.fsa import FSAAdapter
from ieee_2030_5.adapters.timeadapter import TimeAdapter
from ieee_2030_5.data.indexer import add_href
from ieee_2030_5.models.enums import DeviceCategoryType
from ieee_2030_5.types_ import Lfdi
from ieee_2030_5.utils import uuid_2030_5

_log = logging.getLogger(__file__)


EndDeviceAdapter = Adapter[m.EndDevice](hrefs.get_enddevice_href(), generic_type=m.EndDevice)
def initialize_end_device_adapter(sender):
    """ Intializes the following based upon the device configuration and the tlsrepository.
        
    Each EndDevice will have the following sub-components initialized:
    - PowerStatus - PowerStatusLink
    - DeviceStatus - DeviceStatusLink
    - Registration - RegistrationLink
    - MessagingProgramList - MessagingProgramListLink
    - Log
    Either FSA or DemandResponseProgram
    - DemandResponseProgram - DemandResponseProgramListLink
    
    
    As well as the following properties
    - changedTime - Current time of initialization
    - sFDI - The short form of the certificate for the system.
    """

    # assert EndDeviceAdapter.__tls_repository__ is not None
    # EndDeviceAdapter.initialize_from_storage()
    # programs = DERProgramAdapter.get_all()
    # stored_devices = EndDeviceAdapter.get_all()
    programs = DERProgramAdapter.fetch_all()

    for dev in BaseAdapter.device_configs():
        ts = int(round(datetime.utcnow().timestamp()))
        
        edev = m.EndDevice()
        edev.lFDI = BaseAdapter.__tls_repository__.lfdi(dev.id)
        edev.sFDI = BaseAdapter.__tls_repository__.sfdi(dev.id)
        # TODO handle enum eval in a better way.
        edev.deviceCategory = eval(f"DeviceCategoryType.{dev.deviceCategory}")
        edev.enabled = dev.enabled
        edev.changedTime = ts

        # TODO remove subscribable
        edev.subscribable = None
        
        # Short circuit so that we can use autoreloader and debug
        edev_found = EndDeviceAdapter.fetch_by_property("sFDI", edev.sFDI)
        if edev_found:
            break
        
        EndDeviceAdapter.add(edev)
        
        # Add the end device to the list.
        index = EndDeviceAdapter.fetch_index(edev)
        
        
        EndDeviceAdapter.add_replace_child(edev, hrefs.END_DEVICE_REGISTRATION, 
                                   m.Registration(href=hrefs.registration_href(index), pIN=dev.pin, dateTimeRegistered=ts))
        edev.RegistrationLink = m.RegistrationLink(href=hrefs.registration_href(index))
        
        di = hrefs.EdevHref(edev_index=index, edev_subtype=hrefs.EDevSubType.DeviceInformation)
        EndDeviceAdapter.add_replace_child(edev, hrefs.END_DEVICE_INFORMATION, m.DeviceInformation(href=str(di)))
        edev.DeviceInformationLink = m.DeviceInformationLink(str(di))
        
        ds = hrefs.EdevHref(edev_index=index, edev_subtype=hrefs.EDevSubType.DeviceStatus)
        EndDeviceAdapter.add_replace_child(edev, hrefs.END_DEVICE_STATUS, m.DeviceStatus(str(ds)))
        edev.DeviceStatusLink = m.DeviceStatusLink(str(ds))
        
        #edev.FunctionSetAssignmentsListLink = m.FunctionSetAssignmentsListLink(href=hrefs.fsa_href(edev_index=index))
        
        fsa_programs = []
        for cfg_program in dev.programs:
            for program in programs:
                program.mRID = uuid_2030_5()
                if cfg_program["description"] == program.description:
                    fsa_programs.append(program)
                
        if len(fsa_programs) > 0:
            
            fsa = m.FunctionSetAssignments()
            
            FSAAdapter.add(fsa)
                            
            for derp in fsa_programs:                  
                FSAAdapter.add_replace_child(fsa, hrefs.FSA, derp)
                
            edev.FunctionSetAssignmentsListLink = m.FunctionSetAssignmentsListLink(href=hrefs.fsa_href(edev_index=index))
            
            # TODO we are hardcoding assuming only one fsa here.
            fsa.DERProgramListLink = m.DERProgramListLink(href=f"{hrefs.fsa_href(index=0)}_{hrefs.DER_PROGRAM}")
            # fsa = FSAAdapter.create(fsa_programs)
            # edev.FunctionSetAssignmentsListLink = m.FunctionSetAssignmentsListLink(href=hrefs.fsa_href(edev_index=index))
            # self._fsa.append(fsa)
            EndDeviceAdapter.add_replace_child(edev, hrefs.FSA, FSAAdapter)
            
        if dev.ders:
            der_href = hrefs.EdevHref(index, hrefs.EDevSubType.DER)
            deradapter = Adapter[m.DER](str(der_href), generic_type=m.DER)
            edev.DERListLink = m.DERListLink(str(der_href))
            
            EndDeviceAdapter.add_replace_child(edev, hrefs.DER, deradapter)
            for der_indx, der_cfg in enumerate(dev.ders):
                der_href = hrefs.EdevHref(edev_index=index, edev_subtype=hrefs.EDevSubType.DER, edev_subtype_index=der_indx)
                der = m.DER(href=str(der_href))
                der_href.edev_der_subtype = hrefs.DERSubType.Availability
                der.DERAvailabilityLink = m.DERAvailabilityLink(str(der_href))
                
                der_href.edev_der_subtype = hrefs.DERSubType.Capability
                der.DERCapabilityLink = m.DERCapabilityLink(str(der_href))
                
                der_href.edev_der_subtype = hrefs.DERSubType.Settings
                der.DERSettingsLink = m.DERSettingsLink(str(der_href))
                
                der_href.edev_der_subtype = hrefs.DERSubType.Status
                der.DERStatusLink = m.DERStatusLink(str(der_href))
                
                # Configure a link to the current program for the der.
                cfg_der_program = der_cfg.get("program")
                if cfg_der_program:
                    for derp_index, derp in enumerate(programs):
                        if cfg_der_program == derp.description:
                            der.CurrentDERProgramLink = m.CurrentDERProgramLink(derp.href)
                            break
                
                deradapter.add(der)
    
    ready_signal.send(EndDeviceAdapter)
        #self._end_devices.append(edev)
                        

        # log = m.LogEventList(href=hrefs.get_log_list_href(index),
        #                      all=0,
        #                      results=0,
        #                      pollRate=BaseAdapter.server_config().log_event_list_poll_rate)
        # edev.LogEventListLink = m.LogEventListLink(href=log.href)
        # add_href(log.href, log)

        # cfg = m.Configuration(href=hrefs.get_configuration_href(index))
        # add_href(cfg.href, cfg)
        # edev.ConfigurationLink = m.ConfigurationLink(cfg.href)

        # ps = m.PowerStatus(href=hrefs.get_power_status_href(index))
        # add_href(ps.href, ps)
        # edev.PowerStatusLink = m.PowerStatusLink(href=ps.href)

        # ds = m.DeviceStatus(href=hrefs.get_device_status(index))
        # add_href(ds.href, ds)
        # edev.DeviceStatusLink = m.DeviceStatusLink(href=ds.href)

        # di = m.DeviceInformation(href=hrefs.get_device_information(index))
        # add_href(di.href, di)
        # edev.DeviceInformationLink = m.DeviceInformationLink(href=di.href)

        # ts = int(round(datetime.utcnow().timestamp()))
        # reg = m.Registration(href=hrefs.get_registration_href(index),
        #                      pIN=dev.pin,
        #                      dateTimeRegistered=ts)
        # add_href(reg.href, reg)
        # edev.RegistrationLink = m.RegistrationLink(reg.href)

        # log = m.LogEventList(href=hrefs.get_log_list_href(index), all=0)
        # add_href(log.href, log)
        # edev.LogEventListLink = m.LogEventListLink(log.href)

        # fsa_list = m.FunctionSetAssignmentsList(href=hrefs.get_fsa_list_href(edev.href))

        # fsa = m.FunctionSetAssignments(href=hrefs.get_fsa_href(fsa_list_href=fsa_list.href,
        #                                                        index=0),
        #                                mRID="0F")
        # edev.FunctionSetAssignmentsListLink = m.FunctionSetAssignmentsListLink(fsa_list.href)

        # der_program_list = m.DERProgramList(href=hrefs.get_der_program_list(fsa_href=fsa.href),
        #                                     all=0,
        #                                     results=0)

        # fsa.DERProgramListLink = m.DERProgramListLink(href=der_program_list.href)
        # fsa_list.FunctionSetAssignments.append(fsa)

        # for cfg_program in dev.programs:
        #     for program in programs:
        #         program.mRID = "1F"
        #         if cfg_program["description"] == program.description:
        #             der_program_list.all += 1
        #             der_program_list.results += 1
        #             der_program_list.DERProgram.append(program)
        #             break

        # # Allow der list here
        # # # TODO: instantiate from config file.
        # der_list = m.DERList(
        #     href=hrefs.get_der_list_href(index),
        # #pollRate=900,
        #     results=0,
        #     all=0)
        # edev.DERListLink = m.DERListLink(der_list.href)

        # self._end_devices.append(edev)

        # edev_list.EndDevice.append(edev)
ready_signal.connect(initialize_end_device_adapter, DERProgramAdapter)

