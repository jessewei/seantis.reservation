from datetime import datetime
from uuid import uuid4 as uuid

from z3c.saconfig import Session
from sqlalchemy.exc import IntegrityError

from seantis.reservation.tests import IntegrationTestCase
from seantis.reservation.models import Allocation


class TestAllocation(IntegrationTestCase):

    def test_simple_add(self):
        # Test a simple add
        allocation = Allocation(raster=15, resource=uuid())
        allocation.start = datetime(2011, 1, 1, 15)
        allocation.end = datetime(2011, 1, 1, 15, 59)
        allocation.group = str(uuid())

        Session.add(allocation)
        self.assertEqual(Session.query(Allocation).count(), 1)

        # Test failing add
        allocation = Allocation(raster=15)

        Session.add(allocation)
        self.assertRaises(IntegrityError, Session.flush)

    def test_date_functions(self):
        allocation = Allocation(raster=60, resource=uuid())
        allocation.start = datetime(2011, 1, 1, 12, 30)
        allocation.end = datetime(2011, 1, 1, 14, 00)

        self.assertEqual(allocation.start.hour, 12)
        self.assertEqual(allocation.start.minute, 0)

        self.assertEqual(allocation.end.hour, 13)
        self.assertEqual(allocation.end.minute, 59)

        start = datetime(2011, 1, 1, 11, 00)
        end = datetime(2011, 1, 1, 12, 05)

        self.assertTrue(allocation.overlaps(start, end))
        self.assertFalse(allocation.contains(start, end))

        start = datetime(2011, 1, 1, 13, 00)
        end = datetime(2011, 1, 1, 15, 00)
        
        self.assertTrue(allocation.overlaps(start, end))
        self.assertFalse(allocation.contains(start, end))