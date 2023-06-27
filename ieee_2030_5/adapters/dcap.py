import logging
from functools import lru_cache
from typing import List

import ieee_2030_5.hrefs as hrefs
import ieee_2030_5.models as m
from ieee_2030_5.adapters import BaseAdapter
from ieee_2030_5.types_ import Lfdi

_log = logging.getLogger(__name__)


__all__: List[str] = [
    "DeviceCapabilityAdapter"
]

class _DeviceCapabilityAdapter:
    
    def __init__(self) -> None:
        pass
    
    def __after_base_init__(self, sender):
        pass

    @classmethod
    @lru_cache
    def get_default_dcap(cls) -> m.DeviceCapability:
        dcap = m.DeviceCapability(href=hrefs.get_dcap_href(),
                                  pollRate=BaseAdapter.server_config().device_capability_poll_rate)
        dcap.ResponseSetListLink = m.ResponseSetListLink(href=hrefs.get_response_set_href(), all=0)
        dcap.TimeLink = m.TimeLink(href=hrefs.get_time_href())
        dcap.EndDeviceListLink = m.EndDeviceListLink(href=hrefs.get_enddevice_href(hrefs.NO_INDEX),
                                                     all=0)
        dcap.MirrorUsagePointListLink = m.MirrorUsagePointListLink(
            href=hrefs.mirror_usage_point_href())
        dcap.UsagePointListLink = m.UsagePointListLink(href=hrefs.usage_point_href())
        return dcap

    @staticmethod
    def get_by_lfdi(lfdi: Lfdi) -> m.DeviceCapability:
        dc = DeviceCapabilityAdapter.get_default_dcap()
        config = BaseAdapter.get_config_from_lfdi(lfdi)
        if config:
            dc.EndDeviceListLink.all = 1
        return dc

DeviceCapabilityAdapter = _DeviceCapabilityAdapter()
BaseAdapter.after_initialized.connect(DeviceCapabilityAdapter.__after_base_init__)