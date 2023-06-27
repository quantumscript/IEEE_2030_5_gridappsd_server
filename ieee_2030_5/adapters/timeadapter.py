import time
from datetime import datetime
from threading import Thread

from blinker import Signal


class _TimeAdapter(Thread):
    tick = Signal("tick")
            
    @staticmethod
    def user_readable(timestamp: int) -> str:
        dt = datetime.fromtimestamp(timestamp)
        return dt.isoformat() # .strftime("%m/%d/%Y, %H:%M:%S")
    
    @staticmethod
    def from_iso(iso_fmt_date: str) -> int:
        dt = datetime.strptime(iso_fmt_date, "%Y-%m-%dT%H:%M:%S")
        return int(time.mktime(dt.timetuple()))
    
    def run(self) -> None:
        
        while True:
            self._tick = int(time.mktime(datetime.utcnow().timetuple()))
            _TimeAdapter.tick.send(self._tick)
            time.sleep(1)
        
    
TimeAdapter = _TimeAdapter()
TimeAdapter.daemon = True
TimeAdapter.start()
