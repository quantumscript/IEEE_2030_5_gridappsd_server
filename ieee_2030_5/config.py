from __future__ import annotations

import inspect
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Literal, Optional, Tuple, Union

import yaml
from dataclasses_json import dataclass_json

__all__ = ["ServerConfiguration"]

#from ieee_2030_5.adapters import DERControlAdapter

try:
    from gridappsd.field_interface import MessageBusDefinition
except ImportError as ex:
    pass

import ieee_2030_5.models as m
from ieee_2030_5.certs import TLSRepository
from ieee_2030_5.server.exceptions import NotFoundError
from ieee_2030_5.types_ import Lfdi

_log = logging.getLogger(__name__)

class InvalidConfigFile(Exception):
    pass


@dataclass
class DeviceConfiguration(m.EndDevice):
    # This id will be used to create certificates.
    id: str = None

    # This is used in the Registration function set but is
    # configured on the server and used to verify the correct location
    # on the client
    pin: int = None
    # hostname: str = None
    # ip: str = None
    # poll_rate: int = 900
    # # TODO: Direct control means that only one FSA will be available to the client.
    # direct_control: bool = True
    programs: List[str] = field(default_factory=list)
    
    ders: List[Dict] = field(default_factory=list)

    @classmethod
    def from_dict(cls, env):
        return cls(**{k: v for k, v in env.items() if k in inspect.signature(cls).parameters})

    def __hash__(self):
        return self.id.__hash__()


@dataclass
class DERCurveConfiguration(m.DERCurve):

    @classmethod
    def from_dict(cls, env):
        return cls(**{k: v for k, v in env.items() if k in inspect.signature(cls).parameters})

    def __hash__(self):
        return self.description.__hash__()


@dataclass
class DERControlBaseConfiguration(m.DERControlBase):

    @classmethod
    def from_dict(cls, env):
        return cls(**{k: v for k, v in env.items() if k in inspect.signature(cls).parameters})

    def __hash__(self):
        return self.description.__hash__()


@dataclass
class DERControlConfiguration(m.DERControl):
    description: str = None
    base: Dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, env):
        return cls(
            **{
                k: v
                for k, v in env.items() if k in inspect.signature(m.DERControl).parameters
                or k in inspect.signature(cls).parameters
            })

    def __hash__(self):
        return self.description.__hash__()


@dataclass
class DERProgramConfiguration(m.DERProgram):

    default_control: str = None
    controls: List[str] = field(default_factory=list)
    curves: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, env):
        return cls(**{k: v for k, v in env.items() if k in inspect.signature(cls).parameters})

    def __hash__(self):
        return self.description.__hash__()


@dataclass_json
@dataclass
class GridappsdConfiguration:
    field_bus_config: Optional[str] = None
    field_bus_def: Optional[MessageBusDefinition] = None
    feeder_id_file: Optional[str] = None
    feeder_id: Optional[str] = None
    simulation_id_file: Optional[str] = None
    simulation_id: Optional[str] = None


# @dataclass
# class ControlDefaults:
#     setESDelay: Optional[Int]
#     setESHighFreq: UInt16 [0..1]
#     setESHighVolt: Int16 [0..1]
#     setESLowFreq: UInt16 [0..1]
#     setESLowVolt: Int16 [0..1]
#     setESRampTms: UInt32 [0..1]
#     setESRandomDelay: UInt32 [0..1]
#     setGradW: UInt16 [0..1]
#     setSoftGradW: UInt16 [0..1]

# @dataclass
# class Program:
#     description: str
#     mRID: Optional[str]

# @dataclass
# class Control:
#     description: str
#     mRID: Optional[str]


@dataclass
class ProgramList:
    name: str
    programs: List[m.DERProgram]


@dataclass
class ServerConfiguration:
    openssl_cnf: str

    devices: List[DeviceConfiguration]

    tls_repository: str
    openssl_cnf: str

    server: str
    https_port: int

    log_event_list_poll_rate: int = 900
    device_capability_poll_rate: int = 900
    usage_point_post_rate: int = 300
    end_device_list_poll_rate: int = 86400  # daily check-in

    generate_admin_cert: bool = False

    http_port: int = None

    server_mode: Union[
        Literal["enddevices_create_on_start"],
        Literal["enddevices_register_access_only"]] = "enddevices_register_access_only"

    lfdi_mode: Union[
        Literal["lfdi_mode_from_file"],
        Literal["lfdi_mode_from_cert_fingerprint"]] = "lfdi_mode_from_cert_fingerprint"


    programs: List[DERProgramConfiguration] = field(default_factory=list)
    controls: List[DERControlConfiguration] = field(default_factory=list)
    curves: List[DERCurveConfiguration] = field(default_factory=list)
    events: List[Dict] = field(default_factory=list)

    # # map into program_lists array for programs for specific
    # # named list.
    # programs_map: Dict[str, int] = field(default_factory=dict)
    # program_lists: List[ProgramList] = field(default_factory=list)
    # fsa_list: List[FunctionSetAssignments] = field(default_factory=list)
    # curve_list: List[DERCurve] = field(default_factory=list)

    proxy_hostname: Optional[str] = None
    gridappsd: Optional[GridappsdConfiguration] = None
    # DefaultDERControl: Optional[DefaultDERControl] = None
    # DERControlList: Optional[DERControl] = field(default=list)
    
    @property
    def server_hostname(self) -> str:
        server = self.server
        if self.https_port:
            server = server + f":{self.https_port}"
            
        return server

    @classmethod
    def from_dict(cls, env):
        return cls(**{k: v for k, v in env.items() if k in inspect.signature(cls).parameters})

    def __post_init__(self):
        self.curves = [DERCurveConfiguration.from_dict(x) for x in self.curves]
        self.controls = [DERControlConfiguration.from_dict(x) for x in self.controls]
        self.programs = [DERProgramConfiguration.from_dict(x) for x in self.programs]
        self.devices = [DeviceConfiguration.from_dict(x) for x in self.devices]
        for d in self.devices:
            d.deviceCategory = eval(f"m.DeviceCategoryType.{d.deviceCategory}").name
            #d.device_category_type = eval(f"m.DeviceCategoryType.{d.device_category_type}")

        # der_controls, der_default_control = None, None
        # if self.DERControlListFile:
        #     der_controls, der_default_control = DERControlAdapter.load_from_yaml_file(self.DERControlListFile)

        # temp_program_list = self.program_lists
        # if isinstance(self.program_lists, str):
        #     temp_program_list = yaml.safe_load(Path(self.program_lists).read_text())

        # self.program_lists = []
        # for program_list in temp_program_list['program_lists']:
        #     pl_obj = ProgramList(name=program_list["name"], programs=[])
        #     for inter_index, program_obj in enumerate(program_list['programs']):
        #         base = None
        #         if "DERControlBase" in program_obj:
        #             base = DERControlBase()
        #             for k in program_obj.get("DERControlBase"):
        #                 setattr(base, k, program_obj["DERControlBase"].get(k))
        #             del program_obj["DERControlBase"]
        #         # TODO Do Something with base so we can retrieve it.
        #         # if base:
        #         #     self.DefaultDERControl = DefaultDERControl(DERControlBase=base)
        #         #     for k, v in program.items():
        #         #         setattr(self.DefaultDERControl, k, v)
        #         # else:
        #         program = DERProgram()
        #
        #         for k, v in program_obj.items():
        #             setattr(program, k, v)
        #
        #         pl_obj.programs.append(program)
        #     self.program_lists.append(pl_obj)
        #
        # temp_curve_list = self.curve_list
        # if isinstance(self.curve_list, str):
        #     temp_curve_list = yaml.safe_load(Path(self.curve_list).read_text())
        #
        # self.curve_list = []
        # for item in temp_curve_list['curve_list']:
        #     curve_data: List[CurveData] = []
        #     for data in item.get('CurveData'):
        #         curve_data.append(CurveData(xvalue=data['xvalue'], yvalue=data['yvalue']))
        #     del item["CurveData"]
        #
        #     curve = DERCurve(CurveData=curve_data)
        #     for k, v in item.items():
        #         setattr(curve, k, v)
        #     self.curve_list.append(curve)

        if self.gridappsd:
            self.gridappsd = GridappsdConfiguration.from_dict(self.gridappsd)
            if Path(self.gridappsd.feeder_id_file).exists():
                self.gridappsd.feeder_id = Path(self.gridappsd.feeder_id_file).read_text().strip()
            if Path(self.gridappsd.simulation_id_file).exists():
                self.gridappsd.simulation_id = Path(
                    self.gridappsd.simulation_id_file).read_text().strip()

            if not self.gridappsd.feeder_id:
                raise ValueError(
                    "Feeder id from gridappsd not found in feeder_id_file nor was specified "
                    "in gridappsd config section.")

            # TODO: This might not be the best place for this manipulation
            self.gridappsd.field_bus_def = MessageBusDefinition.load(
                self.gridappsd.field_bus_config)
            self.gridappsd.field_bus_def.id = self.gridappsd.feeder_id

            _log.info("Gridappsd Configuration For Simulation")
            _log.info(f"feeder id: {self.gridappsd.feeder_id}")
            if self.gridappsd.simulation_id:
                _log.info(f"simulation id: {self.gridappsd.simulation_id}")
            else:
                _log.info("no simulation id")
            _log.info("x" * 80)

        # if self.field_bus_config:
        #     self.field_bus_def = MessageBusDefinition.load(self.field_bus_config)

    def get_device_pin(self, lfdi: Lfdi, tls_repo: TLSRepository) -> int:
        for d in self.devices:
            test_lfdi = tls_repo.lfdi(d.id)
            if test_lfdi == int(lfdi):
                return d.pin
        raise NotFoundError(f"The device_id: {lfdi} was not found.")
