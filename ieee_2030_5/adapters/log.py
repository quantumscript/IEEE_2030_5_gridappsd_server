import logging
from typing import List

import ieee_2030_5.models as m
from ieee_2030_5.adapters import BaseAdapter
from ieee_2030_5.data.indexer import add_href, get_href

__all__: List[str] = [
    "LogAdapter"
]

_log = logging.getLogger(__name__)
class _LogAdapter:
    
    def __init__(self):
        pass        
    
    def __after_base_init__(self, sender):        
        print("after base init")
        print(sender)

    @staticmethod
    def store(path: str, logevent: m.LogEvent):
        """Store a logevent to the given path.
        
        The 2030.5 Logevent is based upon a specific device so /edev/edevid/log is the event
        list that should be stored.  The store method only stores a single event at a time.  The
        2030.5 standard says we should hold at least 10 logs per logevent level."""
        event_list: m.LogEventList = get_href(path)
        if event_list is None:
            event_list = m.LogEventList(
                href=path, pollRate=BaseAdapter.server_config().log_event_list_poll_rate)
            event_list.LogEvent = []

        event_list.LogEvent.append(logevent)
        event_list.LogEvent = sorted(event_list.LogEvent, key="createdDateTime")
        add_href(path, event_list)

    @staticmethod
    def fetch_list(path: str, start: int = 0, after: int = 0, limit: int = 1) -> m.LogEventList:
        # TODO: implement start length
        event_list: m.LogEventList = get_href(path)

        if event_list is None:
            return m.LogEventList(href=path,
                                  all=0,
                                  results=0,
                                  pollRate=BaseAdapter.server_config().log_event_list_poll_rate)

        event_list.all = len(event_list.LogEvent)
        event_list.results = len(event_list.LogEvent)

        return event_list

LogAdapter = _LogAdapter()
BaseAdapter.after_initialized.connect(LogAdapter.__after_base_init__)