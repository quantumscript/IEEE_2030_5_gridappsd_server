from datetime import datetime, timedelta
from flask import Response
import pytz
import tzlocal

from ieee_2030_5.server.base_request import RequestOp
import ieee_2030_5.models as m
from ieee_2030_5.types_ import TimeOffsetType, format_time


class TimeRequest(RequestOp):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def get(self) -> Response:
        # TODO fix for new stuff.
        # local_tz = datetime.now().astimezone().tzinfo
        # now_local = datetime.now().replace(tzinfo=local_tz)

        now_utc = datetime.utcnow().replace(tzinfo=pytz.utc)
        # now_utc = pytz.utc.localize(datetime.utcnow())
        local_tz = pytz.timezone(tzlocal.get_localzone().zone)
        now_local = datetime.now().replace(tzinfo=local_tz)

        start_dst_utc, end_dst_utc = [
            dt for dt in local_tz._utc_transition_times if dt.year == now_local.year
        ]

        utc_offset = local_tz.utcoffset(start_dst_utc - timedelta(days=1))
        dst_offset = local_tz.utcoffset(start_dst_utc + timedelta(days=1)) - utc_offset
        local_but_utc = datetime.now().replace(tzinfo=pytz.utc)

        tm = m.Time(currentTime=format_time(now_utc),
                    dstEndTime=format_time(end_dst_utc.replace(tzinfo=pytz.utc)),
                    dstOffset=TimeOffsetType(int(dst_offset.total_seconds())),
                    localTime=format_time(local_but_utc),
                    quality=None,
                    tzOffset=TimeOffsetType(utc_offset.total_seconds()))

        return self.build_response_from_dataclass(tm)