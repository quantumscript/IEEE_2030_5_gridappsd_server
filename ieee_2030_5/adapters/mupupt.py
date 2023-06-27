import logging
from dataclasses import dataclass, field
from typing import Container, List, Optional, Sized, Tuple

import ieee_2030_5.hrefs as hrefs
import ieee_2030_5.models as m
from ieee_2030_5.adapters import BaseAdapter, ReturnCode
from ieee_2030_5.data.indexer import add_href, get_href

_log = logging.getLogger(__name__)

__all__: List[str] = [
    "MirrorUsagePointAdapter"
]

@dataclass
class _UsagePointWrapper:
    usage_point: m.UsagePoint   
    meter_readings: List[m.MeterReading] = field(default_factory=list)
    mirror_meter_readings: List[m.MirrorMeterReading] = field(default_factory=list)
    
    def fetch_reading_by_mRID(self, mRID) -> m.MeterReading:
        for x in self.meter_readings:
            if x.mRID == mRID:
                return x
        raise StopIteration()
        #return next(filter(lambda x: x.mRID == mRID, self.meter_readings))
    
    def fetch_mirror_meter_reading_index(self, mRID: str) -> int:
        for i, v in enumerate(self.mirror_meter_readings):
            if v.mRID == mRID:
                return i
        raise StopIteration()
        # return next(i for i, v in enumerate(self.mirror_meter_readings) if v.mRID == mRID)
    
    
@dataclass
class _UsagePointContainer(Container, Sized):
    __usage_points__: List[_UsagePointWrapper] = field(default_factory=list)
    
    def create_or_replace_reading(self, usage_point: m.UsagePoint, mirror_meter_reading: m.MirrorMeterReading) -> Tuple[ReturnCode, str]:
        
        assert usage_point in self, "Passed usage_point not contained within container"
        
        try:
            wrapper = self._fetch_wrapper_by_mRID(usage_point.mRID)
        except StopIteration:
            _log.error(f"Wrapper not found for usage point {usage_point}")
        else:
            try:
                mmr_index = wrapper.fetch_mirror_meter_reading_index(mirror_meter_reading.mRID)
                
                mirror_meter_reading.href = wrapper.mirror_meter_readings[mmr_index].href
                wrapper.mirror_meter_readings[mmr_index] = mirror_meter_reading                        
                return ReturnCode.NO_CONTENT, mirror_meter_reading.href
                
            except StopIteration:
                if not mirror_meter_reading.ReadingType:
                    _log.error(f"No ReadingType specified in meter reading.")
                    return ReturnCode.BAD_REQUEST.value, ""
                _log.debug(f"Reading not found for mRID {mirror_meter_reading.mRID}... creating")
                
                mr_href = hrefs.usage_point_href(usage_point.href, True)
                mr_reading_href = hrefs.usage_point_href(usage_point.href, True, len(wrapper.meter_readings))
                mr_type_href = hrefs.usage_point_href(usage_point_index=usage_point.href,
                                                      meter_reading_list = True, 
                                                      meter_reading_index=len(wrapper.meter_readings), 
                                                      meter_reading_type=True)
                meter_reading = m.MeterReading(href=mr_href,
                               ReadingTypeLink=m.ReadingTypeLink(href=mr_type_href),
                               ReadingLink=m.ReadingLink(mr_reading_href))
                mirror_meter_reading.href = mr_reading_href
                
                wrapper.meter_readings.append(meter_reading)                
                wrapper.mirror_meter_readings.append(mirror_meter_reading)
                
                return ReturnCode.CREATED.value, mr_reading_href
                
    
    def create_or_replace(self, mirror_usage_point: m.MirrorUsagePoint) -> m.UsagePoint:
        
        if mirror_usage_point in self:
            
            upt = self.fetch_by_mRID(mirror_usage_point.mRID)
            if not isinstance(upt, m.UsagePoint):
                raise ValueError("blah")
            upt.description=mirror_usage_point.description,
            upt.deviceLFDI=mirror_usage_point.deviceLFDI,
            upt.version=mirror_usage_point.version,
            upt.serviceCategoryKind=mirror_usage_point.serviceCategoryKind,
            upt.status=mirror_usage_point.status
            
        else:
            # 1. Since creating we can use the length of the __usage_points__ for determining the 
            #    next href
            upt = m.UsagePoint(href=hrefs.usage_point_href(len(UsagePointContainer)),
                            description=mirror_usage_point.description,
                            deviceLFDI=mirror_usage_point.deviceLFDI,
                            version=mirror_usage_point.version,
                            mRID=mirror_usage_point.mRID,
                            serviceCategoryKind=mirror_usage_point.serviceCategoryKind,
                            status=mirror_usage_point.status)
                        
            wrapper = _UsagePointWrapper(usage_point=upt)            
            self.__usage_points__.append(wrapper)
            
        if mirror_usage_point.MirrorMeterReading:
            wrapper = self._fetch_wrapper_by_mRID(mirror_usage_point.mRID)
            for reading in mirror_usage_point.MirrorMeterReading:
                self.create_or_replace_reading(upt, reading)
                
        return upt
        
    def fetch_list(self, start: int = 0, after: int = 0, limit: int = -1) -> m.UsagePointList:
        # if limit < 0:
        #     limit = len(self.__usage_points__)
        # elif limit > len(self.__usage_points__):
        #     limit = len(self.__usage_points__)
        
        # points = self.__usage_points__[]
        
        uptl = m.UsagePointList(href=hrefs.usage_point_href(),
                                UsagePoint=[upw.usage_point for upw in self.__usage_points__],
                                all=len(self.__usage_points__),
                                results=len(self.__usage_points__))
        return uptl
    
    def fetch_by_href(self, href: str) -> m.UsagePoint:
        for x in self.__usage_points__:
            if x.usage_point.href == href:
                return x.usage_point
        raise StopIteration()
        # return next(filter(lambda x: x.href == href, [y.usage_point for y in self.__usage_points__]))
    
    def fetch_by_mRID(self, mRID: str) -> m.UsagePoint:
        for x in self.__usage_points__:
            if x.usage_point.mRID == mRID:
                return x.usage_point
        
        raise StopIteration()
        # return next(filter(lambda x: x.mRID == mRID, [y.usage_point for y in self.__usage_points__]))
    
    def _fetch_wrapper_by_mRID(self, mRID: str) -> _UsagePointWrapper:
        for x in self.__usage_points__:
            if x.usage_point.mRID == mRID:
                return x
        
        raise StopIteration()
    
    def _fetch_wrapper_by_href(self, href: str) -> _UsagePointWrapper:
        for x in self.__usage_points__:
            if x.usage_point.href == href:
                return x
        
        raise StopIteration()
        #return next(filter(lambda x: x.usage_point.href == href, self.__usage_points__))

    def __contains__(self, other: object) -> bool:
        for x in self.__usage_points__:
            if x.usage_point.mRID == other.mRID:
                return True
        return False
        # return list(filter(lambda x: x.usage_point.mRID == other.mRID, self.__usage_points__))
    
    def __len__(self) -> int:
        return len(self.__usage_points__)

UsagePointContainer = _UsagePointContainer()

@dataclass
class MirrorUsagePointContainer(Container):
    __mirror_usage_points__: List[m.MirrorUsagePoint] = field(default_factory=list)
    
    def __contains__(self, __x: object) -> bool:
        return list(filter(lambda x: x.mRID == __x.mRID, self.__mirror_usage_points__))


@dataclass
class MeterReadingContainer(Container):
    __meter_readings__: List[m.MeterReading] = field(default_factory=list)
    
    def __contains__(self, __x: object) -> bool:
        return list(filter(lambda x: x.mRID == __x.mRID, self.__meter_readings__))
    
class _MirrorUsagePointAdapter:
    
    def __init__(self):
        self.__upt_container__: _UsagePointContainer = UsagePointContainer
        self.__mirror_usage_points__: List[m.MirrorUsagePoint] = []
    
    def fetch_usage_point_by_href(self, href: str) -> m.UsagePoint:
        return self.__upt_container__.fetch_by_href(href)
    
    def fetch_mirror_usage_point_list(self, start=0, after=0, limit=1) -> m.MirrorUsagePointList:
        return m.MirrorUsagePointList(href=hrefs.mirror_usage_point_href(), all=len(self.__mirror_usage_points__), results=len(self.__mirror_usage_points__),
                                      MirrorUsagePoint=self.__mirror_usage_points__, pollRate=BaseAdapter.server_config().usage_point_post_rate)
    
    def fetch_mirror_usage_by_href(self, href) -> m.MirrorUsagePoint:
        return next(filter(lambda x: x.href == href, self.__mirror_usage_points__))
    
    def get_list(self,start: Optional[int] = None,
                 after: Optional[int] = None,
                 length: Optional[int] = None) -> m.MirrorUsagePointList:
        if start is not None and after is not None:
            # after takes precedence
            index = after + 1 + start
        elif start is not None:
            index = start
        elif after is not None:
            index = after + 1
        else:
            index = 0
        value = get_href(href=hrefs.mirror_usage_point_href(index))

        if not value:
            mupl = m.MirrorUsagePointList(href=hrefs.mirror_usage_point_href())
            mupl.all = 0
            add_href(mupl.href, mupl)

        return get_href(href=hrefs.mirror_usage_point_href(index))

    
    def create(self, mup: m.MirrorUsagePoint) -> Tuple[ReturnCode, str]:
        """Creates a MirrorUsagePoint and its associated usage point
        
        This method creates all of the sub elements of the usage point and
        mirror usage points as well.
        """
        
        before = len(self.__upt_container__)
        upt = self.__upt_container__.create_or_replace(mup)
        after = len(self.__upt_container__)
        if after > before:
            # TODO: Don't hard code here.
            mup.href = upt.href.replace('upt', 'mup')
            mup.postRate = BaseAdapter.server_config().usage_point_post_rate
            self.__mirror_usage_points__.append(mup)
            return ReturnCode.CREATED.value, mup.href
        else:
            for i, o in enumerate(self.__mirror_usage_points__):
                if o.mRID == mup.mRID:
                    mup.href = o.href
                    self.__mirror_usage_points__[i] = mup
                    break
            return ReturnCode.NO_CONTENT.value, mup.href
        
    
    def __len__(self):
        return len(UsagePointContainer.__usage_points__)

    
    def create_reading(self, href: str, data: m.MirrorMeterReading) -> ReturnCode:
        """Create/replace reading passed to the method.
        
        Args:
            
            href: The pathinfo from the http request
            data: MirrorMeterReading to be added.
        """
        
        # 1. The href should be a specific mirror usage point or this should be forbidden.
        #    In addition, we use this as the base url for the upt url that is returned after
        #    the reading is created.
        try:
            #pths = href.split(hrefs.SEP)
            #mup = self.__mirror_usage_points__[pths[1]]
            href = href.replace(hrefs.MUP, hrefs.UTP)
            upt = self.__upt_container__.fetch_by_href(href)
            assert upt
            result = self.__upt_container__.create_or_replace_reading(upt, data)
        except StopIteration:
            # Not found within the list.
            return ReturnCode.BAD_REQUEST.value, ""
        
        return result
        
        # # 2. Attempt to find the mirror reading of the passed data.
        # try:
        #     rdng = next(filter(lambda x: x.mRID==data.mRID, MirrorUsagePointAdapter.__mirror_readings__))
        #     meter_reading: m.MirrorMeterReading = rdng.obj
        # except StopIteration:
        #     # If no ReadingType in the MirrorMeterReading then that is an error to create a new reading. 
        #     if not data.ReadingType:
        #         return ReturnCode.BAD_REQUEST
            
            
            
            
        
            
        
        # # 1. Find the usage point that this reading belongs to
        # mapped_usage_point = None
        # upls = UsagePointAdapter.fetch_all()        
        
        # for up in UsagePointAdapter.fetch_all().UsagePoint:
        #     if up.mRID == data.mRID:
        #         mapped_usage_point = up
        #         break
        
        # # If there is no usage point then the client should create one
        # if not mapped_usage_point:
        #     return ReturnCode.BAD_REQUEST
        
        # # 2. If the meter reading mRID matches an existing meter reading 
        # meter_readings_href = hrefs.SEP.join([mapped_usage_point.href, "mr"])
        # meter_readings = get_href(meter_readings_href)
        
        # if meter_readings is None:
        #     meter_readings = m.MeterReadingList(href=meter_readings_href, all=0)
        
        # next_meter_reading = meter_readings.all + 1
        
        
        # if isinstance(data, m.MeterReading):   
        #     data.href = hrefs.SEP.join([meter_readings_href, str(next_meter_reading)])
        #     meter_readings.MeterReading.append(data)
        # else:
        #     raise NotImplementedError
        
        
        
        # for index, rs in enumerate(data.MirrorReadingSet):
        #     rs_href = hrefs.SEP.join([mapped_usage_point.href, "mr", str(index)])
        #     for reading_index, reading in rs.Reading:
        #         reading_href = hrefs.SEP.join([rs_href], "rs", str(reading_index))
        #         reading.localID = reading_index
                
                
        # # TODO overwrite if reading set not found
        # mr_href = hrefs.SEP.join([mapped_usage_point.href, "mr"])
        # mr = get_href(mr_href)
        
        # if mr is None:
        #     mr = m.MeterReadingList(href=mr_href)                        
        #     mapped_usage_point.MeterReadingListLink = mr_href
        #     add_href(mr_href, mr)
        
        # next_index = len(mr.MeterReading) + 1
        
            
            
        

        
        # usage_point_href = hrefs.usage_point_href(uph.mirror_usage_point_index, meter_reading_list=True)
        
        # upl: m.UsagePointList = get_href(usage_point_href)
        
        
        # #upl.UsagePoint.append()        
        # # Look up the meter reading list
        # mr = get_href(href)
        
        
            
            
        

        # _log.debug(href)
        # _log.debug(data)
        
    
    
    def get_by_mRID(self,mRID: str) -> Optional[m.MirrorUsagePoint]:
        for mup in MirrorUsagePointAdapter.fetch_all().MirrorUsagePoint:
            if mup.mRID == mRID:
                return mup
        return None

    
    def get_by_index(self,index: int) -> m.MirrorUsagePoint:
        return get_href(hrefs.mirror_usage_point_href(index))

    
    def fetch_all(self) -> m.MirrorUsagePointList:
        mupl = get_href(hrefs.mirror_usage_point_href())

        if mupl is None:
            mupl = m.MirrorUsagePointList(href=hrefs.mirror_usage_point_href(),
                                          results=0,
                                          all=0,
                                          pollRate=30)
            add_href(mupl.href, mupl)

        return mupl
    
MirrorUsagePointAdapter = _MirrorUsagePointAdapter()



if __name__ == '__main__':
    
    mup = m.MirrorUsagePoint(mRID="foo",
                             roleFlags="09",
                             serviceCategoryKind=0,
                             status=1,
                             deviceLFDI="lfdididididiidididiididiididid")
    
    print("Creating mirror usage point")
    ret = MirrorUsagePointAdapter.create(mup)

    print("expected 201 and /mup_0")
    print(ret)
    
    mmr = m.MirrorMeterReading(mRID="29403bc10000000f0000d431",
                               description="Reactive Power",
                               lastUpdateTime="1677083028",
                               Reading=m.Reading(timePeriod=m.DateTimeInterval(start=0, duration=0)),
                               ReadingType=m.ReadingType(accumulationBehaviour=12,
                                                         commodity=1,
                                                         dataQualifier=0,
                                                         flowDirection=19,
                                                         kind=37,
                                                         powerOfTenMultiplier=0,
                                                         uom=63))
    
    print("Posting mirror reading to the wrong usage point should get 400, '' as response")
    # We know this is the first usage point created so post to the mirror usage point.
    ret2 = MirrorUsagePointAdapter.create_reading("/upt_0", mmr)
    print(ret2)
    ret3 = MirrorUsagePointAdapter.create_reading("/upt_0", mmr)
    print(ret3)
    
    
    ret3 = MirrorUsagePointAdapter.create(mup)
    
    print(ret2)