from __future__ import annotations

import logging
from dataclasses import fields
from enum import Enum
from typing import Any, Dict, List, NamedTuple, Optional, Tuple

from blinker import Signal

import ieee_2030_5.hrefs as hrefs
import ieee_2030_5.models as m
from ieee_2030_5.adapters import (Adapter, AdapterListProtocol, BaseAdapter,
                                  ready_signal)
from ieee_2030_5.adapters.timeadapter import TimeAdapter
from ieee_2030_5.config import InvalidConfigFile
from ieee_2030_5.data.indexer import add_href, get_href_filtered
from ieee_2030_5.models.sep import DERProgram
from ieee_2030_5.types_ import StrPath

_log = logging.getLogger(__name__)

__all__: List[str] = [
    "DERControlAdapter",
    "DERProgramAdapter",
    "DERCurveAdapter",
    "DERAdapter"
]

class CreateStatus(Enum):
    Error = "Error"
    Created = "Created"
    Updated = "Updated"

class CreateResponse(NamedTuple):
    data: Any
    href: str
    index: int = -1
    status: str = CreateStatus.Created.value
    
    @property
    def statusint(self) -> int:
        if self.status == CreateStatus.Created.value:
            return 201
        elif self.status == CreateStatus.Updated.value:
            return 204
        elif self.status == CreateStatus.Error:
            return 400
        

DERCurveAdapter = Adapter[m.DERCurve]("curve", generic_type=m.DERCurve)

def initialize_der_curve_adapter(sender):
    config = BaseAdapter.server_config()
    for index, curve_cfg in enumerate(config.curves):
        der_curve = m.DERCurve(**curve_cfg.__dict__)
        der_curve.href = hrefs.curve_href(index)
        DERCurveAdapter.add(der_curve)
    
    ready_signal.send(DERCurveAdapter)
    
ready_signal.connect(initialize_der_curve_adapter, BaseAdapter)


DERControlAdapter = Adapter[m.DERControl]("derc", generic_type=m.DERControl)

def initialize_der_control_adapter(sender):
    config = BaseAdapter.server_config()
    for index, ctl in enumerate(config.controls):
        
        # Create a new DERControl and DERControlBase and initialize as much as possible
        base_control: m.DERControlBase = BaseAdapter.build_instance(m.DERControlBase, ctl.base)

        control: m.DERControl = BaseAdapter.build_instance(m.DERControl, ctl.__dict__)
        control.href = hrefs.get_derc_href(index=index)
        #control.mRID = f"MYCONTROL{index}"
        control.DERControlBase = base_control
        
        DERControlAdapter.add(control)
    
    ready_signal.send(DERControlAdapter)
ready_signal.connect(initialize_der_control_adapter, DERCurveAdapter)


DERProgramAdapter = Adapter[DERProgram](hrefs.der_program_href(), generic_type=m.DERProgram)

def time_updated(timestamp):
    
    for derp_index, derp in enumerate(DERProgramAdapter.fetch_all()):
        try:            
            controls = DERProgramAdapter.fetch_children(derp, hrefs.DERC)
        except KeyError:
            # If controls aren't defined in the program then no need to continue
            continue
        
        try:
            current_active = DERProgramAdapter.fetch_children(derp, hrefs.DER_CONTROL_ACTIVE)
        except KeyError:
            current_active = []
            
        for ctrl_index, ctrl in enumerate(controls):
            if not ctrl.EventStatus:
                if ctrl.interval is not None:
                    _log.debug(f"Setting up event for ctrl {ctrl_index} current_time: {timestamp} start_time: {ctrl.interval.start}")
                    if timestamp > ctrl.interval.start and timestamp < ctrl.interval.start + ctrl.interval.duration:
                        ctrl.EventStatus = m.EventStatus(currentStatus=1, dateTime=timestamp, potentiallySuperseded=False, reason="Active") 
                    else:
                        ctrl.EventStatus = m.EventStatus(currentStatus=0, dateTime=timestamp, potentiallySuperseded=False, reason="Scheduled") 
                    _log.debug(f"ctrl.EventStatus is {ctrl.EventStatus}")
                else:
                    ctrl.EventStatus = m.EventStatus(currentStatus=0, dateTime=timestamp, potentiallySuperseded=False, reason="Scheduled") 
                
            if ctrl.EventStatus:
                if ctrl.interval:
                    # Active control
                    if ctrl.interval.start < timestamp and timestamp < ctrl.interval.start + ctrl.interval.duration:
                        if ctrl.EventStatus.currentStatus == 0:
                            _log.debug(f"Activating control {ctrl_index}")
                            ctrl.EventStatus.currentStatus = 1 # Active
                            ctrl.EventStatus.dateTime = timestamp
                            ctrl.EventStatus.reason = f"Control event active {ctrl.mRID}"

                        if ctrl.mRID not in [x.mRID for x in current_active]:
                            DERProgramAdapter.add_replace_child(derp, hrefs.DER_CONTROL_ACTIVE, ctrl)
                            
                    elif timestamp > ctrl.interval.start + ctrl.interval.duration:
                        if ctrl.EventStatus.currentStatus == 1:
                            _log.debug(f"Deactivating control {ctrl_index}")
                            
                            ctrl.EventStatus.currentStatus = -1 # for me this means complete
                            DERProgramAdapter.remove_child(derp, hrefs.DER_CONTROL_ACTIVE, ctrl)
                

def initialize_der_program_adapter(sender):
    
    config = BaseAdapter.server_config()
    
    controls: List[m.DERControl] = DERControlAdapter.fetch_all()
    curves: List[m.DERCurve] = DERCurveAdapter.fetch_all()    
   
    # Initialize "global" m.DERPrograms href lists, including all the different links to
    # locations for active, default, curve and control lists.
    for index, program_cfg in enumerate(config.programs):
        # The configuration contains a mapping to control lists so when
        # building the DERProgram object we need to remove it from the paramters before
        # initialization.
        params = program_cfg.__dict__.copy()
        del params['default_control']
        del params['controls']
        del params['curves']
        
        program = m.DERProgram(**params)
        program.description = program_cfg.description
        program.primacy = program_cfg.primacy
        # program.version = program_cfg.version

        # TODO Fix this!
        # program.mRID =
        # mrid = program_cfg.get('mrid')
        # if mrid is None or len(mrid.trim()) == 0:
        #     program.mRID = f"program_mrid_{index}"
        # program_cfg['mrid'] = program.mRID

        program.href = hrefs.get_program_href(index)
        program.DefaultDERControlLink = m.DefaultDERControlLink(href=hrefs.der_program_href(index, hrefs.DERProgramSubType.DefaultDERControlLink))
        program.ActiveDERControlListLink = m.ActiveDERControlListLink(href=hrefs.der_program_href(index, hrefs.DERProgramSubType.ActiveDERControlListLink))
        program.DERControlListLink = m.DERControlListLink(href=hrefs.der_program_href(index, hrefs.DERProgramSubType.DERControlListLink))
        program.DERCurveListLink = m.DERCurveListLink(href=hrefs.der_program_href(index, hrefs.DERProgramSubType.DERCurveListLink))
        DERProgramAdapter.add(program)
        
        default_ctl = None
        
        for ctl_cfg in program_cfg.controls:
            for ctl in controls:
                if isinstance(ctl_cfg, str):
                    description = ctl_cfg
                else:
                    description = ctl_cfg["description"]
                if ctl.description == description:
                    DERProgramAdapter.add_replace_child(program, hrefs.DERC, ctl)

        for ctl in controls:
            if ctl.description == program_cfg.default_control:
                DERProgramAdapter.add_replace_child(program, hrefs.DDERC, ctl)
                default_ctl = ctl
        
        if default_ctl is None:
            raise InvalidConfigFile(f"Section program: {program_cfg.description} default control {program_cfg.default_control} not found!")
            
        for curve_cfg in program_cfg.curves:
            for curve in curves:
                if isinstance(curve_cfg, str):
                    description = curve_cfg
                else:
                    description = curve_cfg["description"]
                    
                if curve.description == description:
                    DERProgramAdapter.add_replace_child(program, "dc", curve)
        
        ready_signal.send(DERProgramAdapter)
        TimeAdapter.tick.connect(time_updated)
        # else:
        #     default_ctl: m.DefaultDERControl = BaseAdapter.build_instance(
        #         m.DefaultDERControl, der_cfg.__dict__)
        #     default_ctl.href = hrefs.get_derc_default_href(index)
        #     #default_ctl.mRID = der_ctl.mRID + " default"
        #     default_ctl.setESDelay = 20
        #     default_ctl.DERControlBase = der_ctl.DERControlBase

        #     program.DefaultDERControlLink = m.DefaultDERControlLink(href=default_ctl.href)
        #     self._der_programs.append(program)
        #     program.ActiveDERControlListLink = m.ActiveDERControlListLink(href=hrefs.der_program_href(index, hrefs.DERProgramSubType.ActiveDERControlListLink))
        #     program.DERControlListLink = m.DERControlListLink(href=hrefs.der_program_href(index, hrefs.DERProgramSubType.DERControlListLink.value))
        #     program.DERCurveListLink = m.DERCurveListLink(href=hrefs.der_program_href(index, hrefs.DERProgramSubType.DERCurveListLink.value))
            

        # der_control_list = m.DERControlList(href=hrefs.get_program_href(index, hrefs.DERC))

        # for ctl_description in program_cfg.controls:
        #     try:
        #         derc = next(filter(lambda d: d.description == ctl_description, der_controls))
        #     except StopIteration:
        #         raise InvalidConfigFile(
        #             f"Section program: {program_cfg.description} control {ctl_description} not found!"
        #         )
        #     else:
        #         der_control_list.DERControl.append(derc)

        # add_href(der_control_list.href, der_control_list)

        # der_curve_list = m.DERCurveList(href=hrefs.get_program_href(index, hrefs.CURVE))

        # for curve_description in program_cfg.curves:
        #     try:
        #         der_curve = next(
        #             filter(lambda d: d.description == curve_description, der_curves))
        #     except StopIteration:
        #         raise InvalidConfigFile(
        #             f"Section program: {program_cfg.description} curve {curve_description} not found!"
        #         )
        #     else:
        #         der_curve_list.DERCurve.append(der_curve)

        # der_curve_list.all = len(der_curve_list.DER)
        #ready_signal.send(DERProgramAdapter)
    

ready_signal.connect(initialize_der_program_adapter, DERControlAdapter)
# DERProgramAdapter = _DERProgramAdapter()
# ready_signal.connect(DERProgramAdapter.__initialize__, DERControlAdapter)


# class _DERAdapter(BaseAdapter, AdapterListProtocol):
#     def __init__(self) -> None:
#         super().__init__()
        
#         self._edev_ders: Dict[int, List[m.DER]] = {}
#         self._der_capabilities: Dict[int, List[m.DERCapability]] = {}
#         self._der_settings: Dict[int, List[m.DERSettings]] = {}
#         self._der_status: Dict[int, List[m.DERStatus]] = {}
#         self._der_availabilites: Dict[int, List[m.DERAvailability]] = {}
#         self._der_current_program: Dict[int, List[m.DERProgram]] = {}
#         self._edev_der_settings: Dict[int, List[m.DERSettings]] = {}
        
#     def __initialize__(self, sender):
#         # TODO: Load ders
#         cfg = BaseAdapter.server_config()
        
#     def create(self, edev_index: int, der_index: int,  modesSupported: str, deviceType: int) -> m.DER:
        
#         der = m.DER(href=hrefs.edev_der_href(edev_index=edev_index, der_index=der_index))
#         der.DERCapabilityLink = m.DERCapabilityLink(hrefs.der_sub_href(edev_index=edev_index, index=der_index, subtype=hrefs.DERSubType.Capability))
#         der.DERSettingsLink = m.DERSettingsLink(hrefs.der_sub_href(edev_index=edev_index, index=der_index, subtype=hrefs.DERSubType.Settings))
#         der.DERStatusLink = m.DERStatusLink(hrefs.der_sub_href(edev_index=edev_index, index=der_index, subtype=hrefs.DERSubType.Status))
#         der.DERAvailabilityLink = m.DERAvailabilityLink(hrefs.der_sub_href(edev_index=edev_index, index=der_index, subtype=hrefs.DERSubType.Availability))
#         # der.CurrentDERProgramLink = m.CurrentDERProgramLink(hrefs.der_sub_href(edev_index=edev_index, index=der_index, subtype=hrefs.DERSubType.CurrentProgram))
#         if not self._edev_ders.get(edev_index):
#             self._edev_ders[edev_index] = []
            
#         self._edev_ders[edev_index].append(der)
        
#         if not self._der_capabilities.get(edev_index):
#             self._der_capabilities[edev_index] = []
#         self._der_capabilities[edev_index].append(m.DERCapability(hrefs.der_sub_href(edev_index=edev_index, index=der_index, subtype=hrefs.DERSubType.Capability),
#                                                              modesSupported=modesSupported,
#                                                              type=deviceType))
        
#         if not self._der_settings.get(edev_index):
#             self._der_settings[edev_index] = []
            
#         self._der_settings[edev_index].append(m.DERSettings(href=hrefs.der_sub_href(edev_index=edev_index, index=der_index, subtype=hrefs.DERSubType.Settings)))
        
#         if not self._der_status.get(edev_index):
#             self._der_status[edev_index] = []
        
#         self._der_status[edev_index].append(m.DERStatus(href=hrefs.der_sub_href(edev_index=edev_index, index=der_index, subtype=hrefs.DERSubType.Status)))
        
#         if not self._der_availabilites.get(edev_index):
#             self._der_availabilites[edev_index] = []
        
#         self._der_availabilites[edev_index].append(m.DERAvailability(href=hrefs.der_sub_href(edev_index=edev_index, index=der_index, subtype=hrefs.DERSubType.Availability)))
        
#         if not self._der_current_program.get(edev_index):
#             self._der_current_program[edev_index] = []
        
#         self._der_current_program[edev_index].append(m.DERProgram(href=hrefs.der_sub_href(edev_index=edev_index, index=der_index, subtype=hrefs.DERSubType.CurrentProgram)))
        
#         return der
    
#     def fetch_edev_all(self, edev_index: int) -> List:
#         return self._edev_ders.get(edev_index, [])
    
#     def fetch_list(self, edev_index: int, start: int = 0, after: int = 0, limit: int = 0) -> m.DERList:
        
#         try:
#             der_list = m.DERList(href=hrefs.der_sub_href(edev_index), 
#                                 all=len(self._edev_ders[edev_index]), results=len(self._edev_ders[edev_index]), DER=self._edev_ders[edev_index])
#         except KeyError:
#             der_list = m.DERList(href=hrefs.der_sub_href(edev_index), 
#                                  all=0, results=0, DER=[])
#         return der_list
    
#     def fetch_at(self, edev_index: int, der_index: int) -> m.DER:
#         return self._edev_ders[edev_index][der_index]
    
#     def fetch_settings_at(self, edev_index: int, der_index: int) -> m.DERSettings:
#         return self._edev_der_settings[edev_index][der_index]
    
#     def store_settings_at(self, edev_index: int, der_index: int, settings: m.DERSettings):
#         self._edev_der_settings[edev_index][der_index] = settings
    
#     def fetch_status_at(self, edev_index: int, der_index: int) -> m.DERStatus:
#         return self._der_status[edev_index][der_index]
    
#     def store_status_at(self, edev_index: int, der_index: int, status: m.DERStatus):
#         self._edev_der_status[edev_index][der_index] = status
    
#     def fetch_capability_at(self, edev_index: int, der_index: int) -> m.DERCapability:
#         return self._der_capabilities[edev_index][der_index]
    
#     def store_capability_at(self, edev_index: int, der_index: int, capability: m.DERCapability):
#         self._der_capabilities[edev_index][der_index] = capability
    
#     def fetch_availibility_at(self, edev_index: int, der_index: int) -> m.DERAvailability:
#         return self._der_availabilites[edev_index][der_index]
    
#     def store_availibility_at(self, edev_index: int, der_index: int, availability: m.DERAvailability):
#         self._der_availabilites[edev_index][der_index] = availability
    
#     def fetch_current_program_at(self, edev_index: int, der_index: int) -> m.DERProgram:
#         return self._der_current_program[edev_index][der_index]
    
#     def store_current_program_at(self, edev_index: int, der_index: int, current_program: m.DERProgram):
#         self._der_current_program[edev_index][der_index] = current_program
    
#     def store(self, parsed_edev: hrefs.EdevHref, data) -> int:
#         if parsed_edev.der_sub == hrefs.DERSubType.Availability.value:
#             self._der_availabilites[parsed_edev.edev_index][parsed_edev.der_index] = data
#         elif parsed_edev.der_sub == hrefs.DERSubType.Capability.value:
#             self._der_capabilities[parsed_edev.edev_index][parsed_edev.der_index] = data
#         elif parsed_edev.der_sub == hrefs.DERSubType.Status.value:
#             self._der_status[parsed_edev.edev_index][parsed_edev.der_index] = data
#         elif parsed_edev.der_sub == hrefs.DERSubType.Settings.value:
#             self._der_settings[parsed_edev.edev_index][parsed_edev.der_index] = data
#         else:
#             raise ValueError(data)
        
#         return 200
    
#     def get_list(self, edev_index: int):
#         return self._edev_ders[edev_index]
    
    
# DERAdapter = _DERAdapter()
# ready_signal.connect(DERAdapter.__initialize__, BaseAdapter)



if __name__ == '__main__':
    from pathlib import Path

    import yaml

    from ieee_2030_5.__main__ import get_tls_repository
    from ieee_2030_5.config import ServerConfiguration
    
    cfg_pth = Path("/home/os2004/repos/gridappsd-2030_5/config.yml")
    cfg_dict = yaml.safe_load(cfg_pth.read_text())

    config = ServerConfiguration(**cfg_dict)

    tls_repo = get_tls_repository(config, False)

    BaseAdapter.initialize(config, tls_repo)    

    print(DERCurveAdapter.fetch_edev_all())
    print(DERCurveAdapter.fetch_list())