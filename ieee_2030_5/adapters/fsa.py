import logging
from functools import lru_cache
from typing import Dict, List

import ieee_2030_5.hrefs as hrefs
import ieee_2030_5.models as m
from ieee_2030_5.adapters import Adapter, AdapterListProtocol, BaseAdapter
from ieee_2030_5.types_ import Lfdi

_log = logging.getLogger(__name__)


__all__: List[str] = [
    "FSAAdapter"
]


FSAAdapter = Adapter[m.FunctionSetAssignments](url_prefix=hrefs.fsa_href(), generic_type=m.FunctionSetAssignments)