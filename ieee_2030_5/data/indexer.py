from __future__ import annotations

import pickle
from copy import deepcopy
from dataclasses import dataclass, field
import logging

from datetime import datetime
from email.utils import format_datetime
from typing import Dict, Optional, List
from ieee_2030_5.persistance.points import set_point, get_point

__all__: List[str] = [
    "get_href",
    "add_href",
    "get_href_all_names",
    "get_href_filtered"
]

_log = logging.getLogger(__name__)


@dataclass
class Index:
    href: str
    item: object
    added: str  # Optional[Union[datetime | str]]
    last_written: str  # Optional[Union[datetime | str]]
    last_hash: Optional[int]


@dataclass
class Indexer:
    __items__: Dict = field(default=None)

    def init(self):
        if self.__items__ is None:
            self.__items__ = {}

    @property
    def length(self) -> int:
        self.init()
        return len(self.__items__)

    def add(self, href: str, item: dataclass):
        self.init()

        cached = self.__items__.get(href)
        if cached and cached.item == item:
            _log.debug(f"Item already cached {href}")
        else:
            added = format_datetime(datetime.utcnow())
            serialized_item = pickle.dumps(item)  # serialize_dataclass(item, serialization_type=SerializeType.JSON)
            obj = Index(href, item, added=added, last_written=added, last_hash=hash(serialized_item))
            # serialized_obj = serialize_dataclass(obj, serialization_type=SerializeType.JSON)

            # note storing Index object.
            set_point(href, pickle.dumps(obj))  # serialize_dataclass(obj, serialization_type=SerializeType.JSON))
            self.__items__[href] = obj

    def get(self, href) -> dataclass:
        self.init()
        if href in self.__items__:
            index = pickle.loads(get_point(href))  # pickle.loads(get_point(href))
            # index = pickle.loads(self.__items__.get(href))
            # index = deserialize_dataclass(data, SerializeType.JSON)
            data = index.item
        else:
            data = None

        return data

    def get_all(self) -> List:
        return deepcopy([x.item for x in self.__items__.values()])


__indexer__ = Indexer()


def add_href(href: str, item: dataclass):
    __indexer__.add(href, item)


def get_href(href: str) -> dataclass:
    return __indexer__.get(href)


def get_href_filtered(href_prefix: str) -> List[dataclass] | []:
    if __indexer__.__items__ is None:
        return []
    
    return [v.item for k, v in __indexer__.__items__.items()
            if k.startswith(href_prefix) and v.item is not None]


def get_href_all_names():
    return [x for x in __indexer__.__items__.keys()
            if __indexer__.__items__[x] is not None]
