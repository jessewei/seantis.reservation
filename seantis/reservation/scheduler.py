from z3c.saconfig import Session
from sqlalchemy.sql import and_, or_

from seantis.reservation.models import DefinedTimeSpan
from seantis.reservation.models import ReservedTimeSlot
from seantis.reservation.error import DefinitionConflict

class Scheduler(object):

    def __init__(self, resource_uuid):
        self.resource = resource_uuid

    def define(self, dates, group=None, raster=15):
        # TODO add locking here

        # Make sure that this span does not overlap another
        for start, end in dates:
            existing = self.any_defined_in_range(start, end)
            if existing:
                raise DefinitionConflict(start, end, existing)

        defines = []

        for start, end in dates:
            span = DefinedTimeSpan()
            span.raster = raster
            span.start = start
            span.end = end
            span.group = group
            span.resource = self.resource

            defines.append(span)

        Session.add_all(defines)

        return defines

    def any_defined_in_range(self, start, end):
        for defined in self.defined_in_range(start, end):
            return defined

        return None

    def defined_in_range(self, start, end):
        # Query version of DefinedTimeSpan.overlaps
        query = Session.query(DefinedTimeSpan).filter(
            or_(
                and_(
                    DefinedTimeSpan._start <= start,
                    start <= DefinedTimeSpan._end
                ),
                and_(
                    start <= DefinedTimeSpan._start,
                    DefinedTimeSpan._start <= end
                )
            ),
        )

        query = query.filter(DefinedTimeSpan.resource == self.resource)

        for result in query:
            yield result

    def reserve(self, dates):
        slots_to_reserve = []
        for start, end in dates:
            for span in self.defined_in_range(start, end):
                for slot_start, slot_end in span.possible_dates(start, end):
                    slot = ReservedTimeSlot()
                    slot.start = slot_start
                    slot.end = slot_end
                    slot.defined_timespan = span
                    slot.resource = self.resource

                    slots_to_reserve.append(slot)
        
        Session.add_all(slots_to_reserve)
        return slots_to_reserve