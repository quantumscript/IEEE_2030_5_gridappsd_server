import inspect
import logging
import typing
from dataclasses import dataclass, fields, is_dataclass
from enum import Enum
from typing import (Any, Dict, Generic, List, Optional, Protocol, Type,
                    TypeVar, get_args, get_origin)

from blinker import Signal

import ieee_2030_5.config as cfg
import ieee_2030_5.hrefs as hrefs
import ieee_2030_5.models as m
from ieee_2030_5.certs import TLSRepository
from ieee_2030_5.models.sep import List_type

_log = logging.getLogger(__name__)

class AlreadyExists(Exception):
    pass

class ReturnCode(Enum):
    OK = 200
    CREATED = 201
    NO_CONTENT = 204
    BAD_REQUEST = 400


def populate_from_kwargs(obj: object, **kwargs) -> Dict[str, Any]:

    if not is_dataclass(obj):
        raise ValueError(f"The passed object {obj} is not a dataclass.")

    for k in fields(obj):
        if k.name in kwargs:
            type_eval = eval(k.type)

            if typing.get_args(type_eval) is typing.get_args(Optional[int]):
                setattr(obj, k.name, int(kwargs[k.name]))
            elif typing.get_args(k.type) is typing.get_args(Optional[bool]):
                setattr(obj, k.name, bool(kwargs[k.name]))
            # elif bytes in args:
            #     setattr(obj, k.name, bytes(kwargs[k.name]))
            else:
                setattr(obj, k.name, kwargs[k.name])
            kwargs.pop(k.name)
    return kwargs

class AdapterIndexProtocol(Protocol):
    
    def fetch_at(self, index: int) -> m.Resource:
        pass


class AdapterListProtocol(AdapterIndexProtocol):
    def fetch_list(self, start: int = 0, after: int =0, limit:int = 0) -> m.List_type:
        pass
    
    def fetch_edev_all(self) -> List:
        pass
        

ready_signal = Signal("ready-signal")

T = TypeVar('T')
C = TypeVar('C')
D = TypeVar('D')


class Adapter(Generic[T]):
    
    def __init__(self, url_prefix: str, **kwargs):
        if "generic_type" not in kwargs:
            raise ValueError("Missing generic_type parameter")
        self._generic_type: Type = kwargs['generic_type']
        self._href_prefix: str = url_prefix
        self._current_index: int  = -1
        self._item_list: Dict[int, T] = {}
        self._child_prefix: Dict[Type, str] = {}
        self._child_map: Dict[int, Dict[str, List[C]]] = {}
        
    @property
    def href_prefix(self) -> str:
        return self._href_prefix
    
    @property
    def href(self) -> str:
        return self._href_prefix
    
    @href.setter
    def href(self, value:str) -> None:
        self._href_prefix = value
    
    def fetch_by_property(self, prop: str, prop_value: Any) -> Optional[T]:
        for obj in self._item_list.values():
            if getattr(obj, prop) == prop_value:
                return obj
            
    def fetch_child_names(self) -> List[str]:
        return list(self._child_prefix.keys())
    
    def add_container(self, child_type: Type, href_prefix: str):
        self._child_prefix[child_type] = href_prefix
        
    def remove_child(self, parent: T, name: str, child: Any):
        found_index = self.fetch_index(parent)
        self._child_map[found_index][name].remove(child)
        
    def remove_child_by_mrid(self, parent: T, name: str, mRID: str):
        
        found_index = self.fetch_index(parent)
        
        indexes = [index for index, x in enumerate(self._child_map[found_index][name]) if x.mRID == mRID]
        for index in sorted(indexes, reverse=True):
            self._child_map[found_index][name].pop(index)
        
    def add_replace_child(self, parent: T, name: str, child: Any, href: str = None):
        
        # Make sure parent is in the Adapter by looking for it's index.
        found_index = self.fetch_index(parent)
        
        # Deal with missing indexes
        if found_index not in self._child_map:
            self._child_map[found_index] = {}
            
        if name not in self._child_map[found_index]:
            self._child_map[found_index][name] = []
            
        if len(self._child_map[found_index][name]) > 0:
            if not isinstance(child, type(self._child_map[found_index][name][0])):
                raise ValueError(f"Children can only have single types {type(child)} != {type(self._child_map[found_index][name][0])}")
        if not child.href:
            if href:
                child.href = href
            else:
                child.href = hrefs.SEP.join([parent.href, name, str(len(self._child_map[found_index][name]))])
        
        # Replace based upon resource href
        for index, c in enumerate(self._child_map[found_index][name]):
            if c.href == child.href:
                _log.debug(f"Replacing child {child.href}")
                self._child_map[found_index][name][index] = child
                return
            
        self._child_map[found_index][name].append(child)
        
    def fetch_children_by_parent_index(self, parent_index: int, child_type: Type) -> List[Type]:
        if child_type not in self._child_map[parent_index]:
            raise KeyError(f"No child object of type {child_type}")
        
        return self._child_map[parent_index][child_type]
    
    def fetch_children(self, parent: T, name: str, container: Optional[Type] = None) -> List[Type]:
        found_index = self.fetch_index(parent)
        # Should end with List if container is not None
        if container is not None:
            if not container.__class__.__name__.endswith("List"):
                raise ValueError(f"Invalid container, type must end in List")
        
        try:
            children = self._child_map[found_index][name]
        except KeyError:
            children = []
        
        retval = children
        
        if container is not None:
            prop = container.__class__.__name__[:container.__class__.__name__.find("List")]
            setattr(container, prop, children)
            setattr(container, "results", len(children))
            setattr(container, "all", len(children))
            retval = container
            
        return retval
                
    def fetch_child(self, parent: T, name: str, index: int = 0) -> Type:
        return self.fetch_children(parent, name)[index]
            
    def add(self, item: T):
        if not isinstance(item, self._generic_type):
            raise ValueError(f"Item {item} is not of type {self._generic_type}")
        
        # Only replace if href is specified.
        if hasattr(item, 'href') and getattr(item, 'href') is None:
            setattr(item, 'href', hrefs.SEP.join([self._href_prefix, str(self._current_index + 1)]))
        self._current_index += 1
        self._item_list[self._current_index] = item
    
    def fetch_all(self, container: Optional[D] = None, start: int = 0, after: int = 0, limit: int = 1) -> D:

        if container is not None:
            if not container.__class__.__name__.endswith("List"):
                raise ValueError("Must have List as the last portion of the name for instance")
        
            prop_found = container.__class__.__name__[:container.__class__.__name__.find("List")]
        
            items = list(self._item_list.values())
            all_len = len(items)
            all_results = len(items)
            all_items = items
                
            if start > len(items):
                all_items = []
                all_results = 0
            else:
                if limit == 0:
                    all_items = items[start:]
                else:
                    all_items = items[start: start + limit]
                all_results = len(all_items)
                
            setattr(container, prop_found, all_items)
            setattr(container, "all", all_len)
            setattr(container, "results", all_results)
        else:
            container = list(self._item_list.values())
            
        return container
    
    def fetch_index(self, obj: T, using_prop: str = None) -> int:
        found_index = -1
        for index, obj1 in self._item_list.items():
            if using_prop is None:    
                if obj1 == obj:
                    found_index = index
                    break
            else:
                if getattr(obj, using_prop) == getattr(obj1, using_prop):
                    found_index = index
                    break
        if found_index == -1:
            raise KeyError(f"Object {obj} not found in adapter")
        return found_index
    
    def fetch(self, index: int):
        return self._item_list[index]
    
    def fetch_by_mrid(self, mRID: str):
        for item in self._item_list:
            if not hasattr(item, 'mRID'):
                raise ValueError(f"Item of {type(T)} does not have mRID property")
            if item.mRID == mRID:
                return item
            
        raise KeyError()
    
    def size(self) -> int:
        return len(self._item_list)
    
    def size_children(self, parent: T, name: str) -> int:
        return len(self.fetch_children(parent, name))
    
    def fetch_child_index_by_mrid(self, parent: T, name: str, mRID: str) -> int:
        for index, child in enumerate(self.fetch_children(parent, name)):
            if child.mRID == mRID:
                return index
        
        raise KeyError("mRID not found")
    
    def replace_child(self, parent: T, name: str, index: int, child: Any):
        children = self.fetch_children(parent, name)
        if not type(child) == type(children[index]):
            return ValueError(f"Children should be  of the same type {type(child)} is not {type(children[index])}")
        parent_index = self.fetch_index(parent)
        if not child.href:
            child.href = children[index].href
        self._child_map[parent_index][name][index] = child
    
    
    
            

class BaseAdapter:
    __count__: int = 0
    __server_configuration__: cfg.ServerConfiguration
    __tls_repository__: cfg.TLSRepository = None
    __lfdi__mapped_configuration__: Dict[str, cfg.DeviceConfiguration] = {}
    after_initialized = Signal('after-initialized')
        
    @classmethod
    def get_next_index(cls) -> int:
        """Retrieve the next index for an adapter list."""
        return cls.__count__

    @classmethod
    def increment_index(cls) -> int:
        """Increment the list to the next index and return the result to the caller.
        
        
        """
        next = cls.get_next_index()
        cls.__count__ += 1
        return next
    
    @classmethod
    def ready(cls) -> Signal:
        return Signal("ready")

    @classmethod
    def get_current_index(cls) -> int:
        return cls.__count__

    @staticmethod
    def server_config() -> cfg.ServerConfiguration:
        return BaseAdapter.__server_configuration__

    @staticmethod
    def device_configs() -> List[cfg.DeviceConfiguration]:
        return BaseAdapter.__server_configuration__.devices

    @staticmethod
    def tls_repo() -> cfg.TLSRepository:
        return BaseAdapter.__tls_repository__

    @staticmethod
    def get_config_from_lfdi(lfdi: str) -> Optional[cfg.DeviceConfiguration]:
        return BaseAdapter.__lfdi__mapped_configuration__.get(lfdi)

    @staticmethod
    def is_initialized():
        return BaseAdapter.__device_configurations__ is not None and BaseAdapter.__tls_repository__ is not None

    @staticmethod
    def initialize(server_config: cfg.ServerConfiguration, tlsrepo: TLSRepository):
        """Initialize all of the adapters
        
        The initialization means that there are concrete object backing the storage system based upon
        urls that can be read during the http call to the spacific end point.  In other words a
        DERCurve dataclass can be retrieved from storage by going to the href /dc/1 rather than
        having to get it through an object.  
        
        The adapters are responsible for storing data into the object store using add_href function.
        """
        BaseAdapter.__server_configuration__ = server_config
        BaseAdapter.__lfdi__mapped_configuration__ = {}
        BaseAdapter.__tls_repository__ = tlsrepo

        # Map from the configuration id and lfdi to the device configuration.
        for cfg in server_config.devices:
            lfdi = tlsrepo.lfdi(cfg.id)
            BaseAdapter.__lfdi__mapped_configuration__[lfdi] = cfg

        #BaseAdapter.after_initialized.send(BaseAdapter)
        ready_signal.send(BaseAdapter)
        # BaseAdapter.ready().send(BaseAdapter)
        # Find subclasses of us and initialize them calling _initalize method
        # TODO make this non static
        #EndDeviceAdapter._initialize()

    @staticmethod
    def build(**kwargs) -> dataclass:
        raise NotImplementedError()

    @staticmethod
    def store(value: dataclass) -> dataclass:
        raise NotImplementedError()

    @staticmethod
    def build_instance(cls, cfg_dict: Dict, signature_cls=None) -> object:
        if signature_cls is None:
            signature_cls = cls
        return cls(**{
            k: v
            for k, v in cfg_dict.items() if k in inspect.signature(signature_cls).parameters
        })

from ieee_2030_5.adapters.dcap import DeviceCapabilityAdapter
from ieee_2030_5.adapters.der import (DERControlAdapter, DERCurveAdapter,
                                      DERProgramAdapter)
from ieee_2030_5.adapters.enddevices import EndDeviceAdapter
from ieee_2030_5.adapters.log import LogAdapter
from ieee_2030_5.adapters.mupupt import MirrorUsagePointAdapter
